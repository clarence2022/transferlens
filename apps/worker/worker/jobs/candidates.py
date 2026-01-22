"""
Candidate Destination Generation
================================

Generates realistic destination candidate sets for transfer prediction.

Sources (in priority order):
1. League candidates - Top clubs from same league (excluding current)
2. Social candidates - Clubs with recent social co-mention spikes
3. User attention candidates - Clubs with user destination cooccurrence
4. Constraint-fit candidates - Clubs matching position need + affordability
5. Random negatives - For calibration

All candidates are stored in candidate_sets table for auditability.

Run with: python -m worker.cli candidates:generate --as-of <timestamp>
"""

import json
import random
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Set, Tuple, Any
from uuid import UUID, uuid4
from dataclasses import dataclass, asdict
from enum import Enum

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table
from sqlalchemy import text
from sqlalchemy.orm import Session

from worker.database import get_sync_session
from worker.config import settings
from worker.time_guards import get_signal_value_strict

console = Console()


# =============================================================================
# CONFIGURATION
# =============================================================================

class CandidateSource(str, Enum):
    """Source of candidate club."""
    LEAGUE = "league"
    SOCIAL = "social"
    USER_ATTENTION = "user_attention"
    CONSTRAINT_FIT = "constraint_fit"
    RANDOM = "random"


@dataclass
class CandidateClub:
    """A candidate destination club with metadata."""
    club_id: UUID
    source: CandidateSource
    score: float  # Relevance score (0-1)
    reason: str  # Human-readable explanation
    
    def to_dict(self) -> Dict:
        return {
            "club_id": str(self.club_id),
            "source": self.source.value,
            "score": self.score,
            "reason": self.reason,
        }


@dataclass
class CandidateConfig:
    """Configuration for candidate generation."""
    # League candidates
    league_top_n: int = 8
    include_top_5_leagues: bool = True
    
    # Social candidates
    social_mention_threshold: float = 2.0  # Velocity multiplier vs baseline
    social_max_candidates: int = 5
    
    # User attention candidates
    user_cooccurrence_threshold: float = 3.0  # Min cooccurrence score
    user_max_candidates: int = 5
    
    # Constraint-fit candidates
    constraint_max_candidates: int = 5
    wage_affordability_ratio: float = 3.0  # Club can afford up to 3x player wage
    fee_affordability_ratio: float = 0.3  # Club can afford up to 30% of net spend
    
    # Random candidates (for calibration)
    random_candidates: int = 5
    
    # Total cap
    max_total_candidates: int = 20


# =============================================================================
# LEAGUE CANDIDATES
# =============================================================================

def get_league_candidates(
    session: Session,
    player_id: UUID,
    current_club_id: UUID,
    as_of: datetime,
    config: CandidateConfig,
) -> List[CandidateClub]:
    """
    Get top clubs from player's current league.
    
    Logic:
    - Get top N clubs by league position (excluding current club)
    - Optionally include top clubs from other major leagues
    """
    candidates = []
    
    # Get current club's competition
    current_club = session.execute(
        text("""
            SELECT c.competition_id, comp.country, comp.tier, comp.name as comp_name
            FROM clubs c
            JOIN competitions comp ON c.competition_id = comp.id
            WHERE c.id = :club_id
        """),
        {"club_id": current_club_id}
    ).first()
    
    if not current_club:
        return candidates
    
    # Get top clubs from same league by league position signal
    same_league_clubs = session.execute(
        text("""
            SELECT DISTINCT c.id, c.name,
                   COALESCE(
                       (SELECT value_num FROM signal_events 
                        WHERE club_id = c.id 
                        AND signal_type = 'club_league_position'
                        AND observed_at <= :as_of
                        AND effective_from <= :as_of
                        ORDER BY effective_from DESC LIMIT 1),
                       99
                   ) as league_position
            FROM clubs c
            WHERE c.competition_id = :comp_id
            AND c.id != :current_club_id
            AND c.is_active = true
            ORDER BY league_position ASC
            LIMIT :limit
        """),
        {
            "comp_id": current_club.competition_id,
            "current_club_id": current_club_id,
            "as_of": as_of,
            "limit": config.league_top_n,
        }
    ).fetchall()
    
    for club in same_league_clubs:
        candidates.append(CandidateClub(
            club_id=club.id,
            source=CandidateSource.LEAGUE,
            score=1.0 - (club.league_position / 20),  # Higher position = higher score
            reason=f"Top {int(club.league_position)} in {current_club.comp_name}",
        ))
    
    # Optionally include top clubs from other major leagues
    if config.include_top_5_leagues:
        top_5_leagues = ['Premier League', 'La Liga', 'Bundesliga', 'Serie A', 'Ligue 1']
        
        other_league_clubs = session.execute(
            text("""
                SELECT DISTINCT c.id, c.name, comp.name as comp_name,
                       COALESCE(
                           (SELECT value_num FROM signal_events 
                            WHERE club_id = c.id 
                            AND signal_type = 'club_league_position'
                            AND observed_at <= :as_of
                            AND effective_from <= :as_of
                            ORDER BY effective_from DESC LIMIT 1),
                           99
                       ) as league_position
                FROM clubs c
                JOIN competitions comp ON c.competition_id = comp.id
                WHERE comp.name = ANY(:leagues)
                AND c.competition_id != :current_comp_id
                AND c.id != :current_club_id
                AND c.is_active = true
                AND COALESCE(
                    (SELECT value_num FROM signal_events 
                     WHERE club_id = c.id 
                     AND signal_type = 'club_league_position'
                     AND observed_at <= :as_of
                     AND effective_from <= :as_of
                     ORDER BY effective_from DESC LIMIT 1),
                    99
                ) <= 6
                ORDER BY league_position ASC
                LIMIT 10
            """),
            {
                "leagues": top_5_leagues,
                "current_comp_id": current_club.competition_id,
                "current_club_id": current_club_id,
                "as_of": as_of,
            }
        ).fetchall()
        
        for club in other_league_clubs:
            candidates.append(CandidateClub(
                club_id=club.id,
                source=CandidateSource.LEAGUE,
                score=0.8 - (club.league_position / 30),  # Slightly lower than same league
                reason=f"Top {int(club.league_position)} in {club.comp_name}",
            ))
    
    return candidates


# =============================================================================
# SOCIAL CANDIDATES
# =============================================================================

def get_social_candidates(
    session: Session,
    player_id: UUID,
    current_club_id: UUID,
    as_of: datetime,
    config: CandidateConfig,
) -> List[CandidateClub]:
    """
    Get clubs with social co-mention spikes.
    
    Logic:
    - Look at social_mention_velocity for (player, club) pairs
    - Compare recent velocity to baseline
    - Include clubs with significant spikes
    """
    candidates = []
    
    # Get clubs with high co-mention velocity
    # This requires pair-level signals (player_id + club_id)
    social_signals = session.execute(
        text("""
            SELECT DISTINCT ON (s.club_id)
                s.club_id,
                c.name as club_name,
                s.value_num as velocity,
                s.observed_at
            FROM signal_events s
            JOIN clubs c ON s.club_id = c.id
            WHERE s.player_id = :player_id
            AND s.signal_type = 'social_mention_velocity'
            AND s.club_id IS NOT NULL
            AND s.club_id != :current_club_id
            AND s.observed_at <= :as_of
            AND s.effective_from <= :as_of
            AND s.value_num >= :threshold
            ORDER BY s.club_id, s.effective_from DESC
        """),
        {
            "player_id": player_id,
            "current_club_id": current_club_id,
            "as_of": as_of,
            "threshold": config.social_mention_threshold,
        }
    ).fetchall()
    
    # Sort by velocity and take top N
    social_signals = sorted(social_signals, key=lambda x: x.velocity or 0, reverse=True)
    
    for signal in social_signals[:config.social_max_candidates]:
        velocity = signal.velocity or 0
        candidates.append(CandidateClub(
            club_id=signal.club_id,
            source=CandidateSource.SOCIAL,
            score=min(velocity / 10, 1.0),  # Normalize to 0-1
            reason=f"Social co-mention velocity: {velocity:.1f}x",
        ))
    
    return candidates


# =============================================================================
# USER ATTENTION CANDIDATES
# =============================================================================

def get_user_attention_candidates(
    session: Session,
    player_id: UUID,
    current_club_id: UUID,
    as_of: datetime,
    config: CandidateConfig,
) -> List[CandidateClub]:
    """
    Get clubs with user destination cooccurrence spikes.
    
    Logic:
    - Look at user_destination_cooccurrence signals
    - These indicate users frequently view both the player and club together
    - High cooccurrence suggests perceived transfer interest
    """
    candidates = []
    
    # Get clubs with high cooccurrence scores
    cooccurrence_signals = session.execute(
        text("""
            SELECT DISTINCT ON (s.club_id)
                s.club_id,
                c.name as club_name,
                s.value_num as cooccurrence_score,
                s.observed_at
            FROM signal_events s
            JOIN clubs c ON s.club_id = c.id
            WHERE s.player_id = :player_id
            AND s.signal_type = 'user_destination_cooccurrence'
            AND s.club_id IS NOT NULL
            AND s.club_id != :current_club_id
            AND s.observed_at <= :as_of
            AND s.effective_from <= :as_of
            AND s.value_num >= :threshold
            ORDER BY s.club_id, s.effective_from DESC
        """),
        {
            "player_id": player_id,
            "current_club_id": current_club_id,
            "as_of": as_of,
            "threshold": config.user_cooccurrence_threshold,
        }
    ).fetchall()
    
    # Sort by cooccurrence and take top N
    cooccurrence_signals = sorted(
        cooccurrence_signals, 
        key=lambda x: x.cooccurrence_score or 0, 
        reverse=True
    )
    
    for signal in cooccurrence_signals[:config.user_max_candidates]:
        score = signal.cooccurrence_score or 0
        candidates.append(CandidateClub(
            club_id=signal.club_id,
            source=CandidateSource.USER_ATTENTION,
            score=min(score / 100, 1.0),  # Normalize
            reason=f"User attention cooccurrence: {score:.1f}",
        ))
    
    return candidates


# =============================================================================
# CONSTRAINT-FIT CANDIDATES
# =============================================================================

def get_constraint_fit_candidates(
    session: Session,
    player_id: UUID,
    current_club_id: UUID,
    as_of: datetime,
    config: CandidateConfig,
) -> List[CandidateClub]:
    """
    Get clubs that match basic transfer constraints.
    
    Constraints:
    1. Position need - Club has few players in that position or aging squad
    2. Wage affordability - Club can afford player's estimated wage
    3. Fee affordability - Club has enough net spend budget
    """
    candidates = []
    
    # Get player info
    player = session.execute(
        text("""
            SELECT p.position, p.date_of_birth,
                   (SELECT value_num FROM signal_events 
                    WHERE player_id = p.id 
                    AND signal_type = 'market_value'
                    AND observed_at <= :as_of
                    AND effective_from <= :as_of
                    ORDER BY effective_from DESC LIMIT 1) as market_value,
                   (SELECT value_num FROM signal_events 
                    WHERE player_id = p.id 
                    AND signal_type = 'wage_estimate'
                    AND observed_at <= :as_of
                    AND effective_from <= :as_of
                    ORDER BY effective_from DESC LIMIT 1) as wage_estimate
            FROM players p
            WHERE p.id = :player_id
        """),
        {"player_id": player_id, "as_of": as_of}
    ).first()
    
    if not player:
        return candidates
    
    player_position = player.position
    player_value = player.market_value or 0
    player_wage = player.wage_estimate or 50000  # Default weekly wage
    
    # Get clubs that could afford this player and might need this position
    potential_clubs = session.execute(
        text("""
            SELECT c.id, c.name, comp.tier,
                   (SELECT value_num FROM signal_events 
                    WHERE club_id = c.id 
                    AND signal_type = 'club_net_spend_12m'
                    AND observed_at <= :as_of
                    AND effective_from <= :as_of
                    ORDER BY effective_from DESC LIMIT 1) as net_spend,
                   (SELECT COUNT(*) FROM players p2 
                    WHERE p2.current_club_id = c.id 
                    AND p2.position = :position
                    AND p2.is_active = true) as position_count,
                   (SELECT AVG(EXTRACT(YEAR FROM AGE(:as_of_date, p2.date_of_birth)))
                    FROM players p2 
                    WHERE p2.current_club_id = c.id 
                    AND p2.position = :position
                    AND p2.is_active = true
                    AND p2.date_of_birth IS NOT NULL) as avg_position_age
            FROM clubs c
            JOIN competitions comp ON c.competition_id = comp.id
            WHERE c.id != :current_club_id
            AND c.is_active = true
            AND comp.tier <= 2
        """),
        {
            "current_club_id": current_club_id,
            "as_of": as_of,
            "as_of_date": as_of.date(),
            "position": player_position,
        }
    ).fetchall()
    
    scored_clubs = []
    
    for club in potential_clubs:
        score = 0.0
        reasons = []
        
        # Position need scoring
        position_count = club.position_count or 0
        avg_age = club.avg_position_age or 0
        
        if position_count <= 2:
            score += 0.4
            reasons.append(f"Only {position_count} {player_position}s")
        elif position_count <= 3:
            score += 0.2
            reasons.append(f"Few {player_position}s ({position_count})")
        
        if avg_age and avg_age >= 30:
            score += 0.3
            reasons.append(f"Aging {player_position}s (avg {avg_age:.1f})")
        
        # Affordability scoring
        net_spend = club.net_spend or 0
        
        # Positive net spend means club has been selling (has budget)
        # Negative net spend means club has been buying
        if net_spend > 0:
            # Club has sold more than bought - likely has budget
            if player_value <= net_spend * config.fee_affordability_ratio:
                score += 0.3
                reasons.append(f"Budget available (net spend €{net_spend/1e6:.1f}M)")
        elif abs(net_spend) < player_value * 2:
            # Club hasn't overspent relative to player value
            score += 0.1
            reasons.append("Within typical spend")
        
        # Tier matching
        if club.tier == 1:
            score += 0.1
            reasons.append("Top tier club")
        
        if score > 0.3 and reasons:
            scored_clubs.append((club, score, "; ".join(reasons)))
    
    # Sort by score and take top N
    scored_clubs.sort(key=lambda x: x[1], reverse=True)
    
    for club, score, reason in scored_clubs[:config.constraint_max_candidates]:
        candidates.append(CandidateClub(
            club_id=club.id,
            source=CandidateSource.CONSTRAINT_FIT,
            score=min(score, 1.0),
            reason=reason,
        ))
    
    return candidates


# =============================================================================
# RANDOM CANDIDATES
# =============================================================================

def get_random_candidates(
    session: Session,
    player_id: UUID,
    current_club_id: UUID,
    existing_candidate_ids: Set[UUID],
    config: CandidateConfig,
) -> List[CandidateClub]:
    """
    Get random clubs for calibration.
    
    Important for:
    - Preventing overfitting to "obvious" candidates
    - Ensuring model learns to reject unlikely destinations
    - Maintaining calibration across probability range
    """
    candidates = []
    
    # Get random clubs not already in candidate set
    random_clubs = session.execute(
        text("""
            SELECT c.id, c.name
            FROM clubs c
            JOIN competitions comp ON c.competition_id = comp.id
            WHERE c.id != :current_club_id
            AND c.is_active = true
            AND comp.tier <= 3
            ORDER BY RANDOM()
            LIMIT :limit
        """),
        {
            "current_club_id": current_club_id,
            "limit": config.random_candidates * 3,  # Get more to filter
        }
    ).fetchall()
    
    # Filter out existing candidates
    for club in random_clubs:
        if club.id not in existing_candidate_ids:
            candidates.append(CandidateClub(
                club_id=club.id,
                source=CandidateSource.RANDOM,
                score=0.1,  # Low score for random
                reason="Random calibration sample",
            ))
            if len(candidates) >= config.random_candidates:
                break
    
    return candidates


# =============================================================================
# MAIN CANDIDATE GENERATION
# =============================================================================

def generate_candidates_for_player(
    session: Session,
    player_id: UUID,
    as_of: datetime,
    horizon_days: int = 90,
    config: Optional[CandidateConfig] = None,
    save_to_db: bool = True,
) -> Dict[str, Any]:
    """
    Generate complete candidate set for a player.
    
    Args:
        session: Database session
        player_id: Player to generate candidates for
        as_of: Point-in-time for generation
        horizon_days: Prediction horizon
        config: Generation configuration
        save_to_db: Whether to save to candidate_sets table
        
    Returns:
        Dict with candidate set and metadata
    """
    if config is None:
        config = CandidateConfig()
    
    # Get player's current club
    player = session.execute(
        text("""
            SELECT p.name, p.current_club_id, p.position, p.date_of_birth,
                   c.name as club_name
            FROM players p
            LEFT JOIN clubs c ON p.current_club_id = c.id
            WHERE p.id = :player_id
        """),
        {"player_id": player_id}
    ).first()
    
    if not player or not player.current_club_id:
        return {"error": "Player not found or has no current club"}
    
    current_club_id = player.current_club_id
    all_candidates: List[CandidateClub] = []
    seen_club_ids: Set[UUID] = set()
    
    # 1. League candidates
    league_candidates = get_league_candidates(
        session, player_id, current_club_id, as_of, config
    )
    for c in league_candidates:
        if c.club_id not in seen_club_ids:
            all_candidates.append(c)
            seen_club_ids.add(c.club_id)
    
    # 2. Social candidates
    social_candidates = get_social_candidates(
        session, player_id, current_club_id, as_of, config
    )
    for c in social_candidates:
        if c.club_id not in seen_club_ids:
            all_candidates.append(c)
            seen_club_ids.add(c.club_id)
    
    # 3. User attention candidates
    user_candidates = get_user_attention_candidates(
        session, player_id, current_club_id, as_of, config
    )
    for c in user_candidates:
        if c.club_id not in seen_club_ids:
            all_candidates.append(c)
            seen_club_ids.add(c.club_id)
    
    # 4. Constraint-fit candidates
    constraint_candidates = get_constraint_fit_candidates(
        session, player_id, current_club_id, as_of, config
    )
    for c in constraint_candidates:
        if c.club_id not in seen_club_ids:
            all_candidates.append(c)
            seen_club_ids.add(c.club_id)
    
    # 5. Random candidates (for calibration)
    random_candidates = get_random_candidates(
        session, player_id, current_club_id, seen_club_ids, config
    )
    for c in random_candidates:
        if c.club_id not in seen_club_ids:
            all_candidates.append(c)
            seen_club_ids.add(c.club_id)
    
    # Limit to max candidates, prioritizing by score
    all_candidates.sort(key=lambda x: x.score, reverse=True)
    all_candidates = all_candidates[:config.max_total_candidates]
    
    # Get player context
    player_context = {
        "name": player.name,
        "position": player.position,
        "club": player.club_name,
        "age": None,
    }
    
    if player.date_of_birth:
        age_days = (as_of.date() - player.date_of_birth).days
        player_context["age"] = round(age_days / 365.25, 1)
    
    # Get market value and contract
    market_value = get_signal_value_strict(
        session, "player", player_id, "market_value", as_of
    )
    contract_months = get_signal_value_strict(
        session, "player", player_id, "contract_months_remaining", as_of
    )
    
    player_context["market_value"] = market_value
    player_context["contract_months_remaining"] = contract_months
    
    # Count by source
    source_counts = {
        "league": sum(1 for c in all_candidates if c.source == CandidateSource.LEAGUE),
        "social": sum(1 for c in all_candidates if c.source == CandidateSource.SOCIAL),
        "user_attention": sum(1 for c in all_candidates if c.source == CandidateSource.USER_ATTENTION),
        "constraint_fit": sum(1 for c in all_candidates if c.source == CandidateSource.CONSTRAINT_FIT),
        "random": sum(1 for c in all_candidates if c.source == CandidateSource.RANDOM),
    }
    
    result = {
        "player_id": str(player_id),
        "player_name": player.name,
        "from_club_id": str(current_club_id),
        "as_of": as_of.isoformat(),
        "horizon_days": horizon_days,
        "total_candidates": len(all_candidates),
        "source_counts": source_counts,
        "candidates": [c.to_dict() for c in all_candidates],
        "player_context": player_context,
    }
    
    # Save to database
    if save_to_db:
        candidate_set_id = uuid4()
        session.execute(
            text("""
                INSERT INTO candidate_sets (
                    id, player_id, as_of, horizon_days, from_club_id,
                    total_candidates, league_candidates, social_candidates,
                    user_attention_candidates, constraint_fit_candidates, random_candidates,
                    candidates_json, player_context_json, generation_version
                ) VALUES (
                    :id, :player_id, :as_of, :horizon_days, :from_club_id,
                    :total, :league, :social, :user_attention, :constraint_fit, :random,
                    :candidates_json, :player_context_json, :version
                )
                ON CONFLICT (player_id, as_of, horizon_days)
                DO UPDATE SET
                    candidates_json = :candidates_json,
                    player_context_json = :player_context_json,
                    total_candidates = :total
            """),
            {
                "id": candidate_set_id,
                "player_id": player_id,
                "as_of": as_of,
                "horizon_days": horizon_days,
                "from_club_id": current_club_id,
                "total": len(all_candidates),
                "league": source_counts["league"],
                "social": source_counts["social"],
                "user_attention": source_counts["user_attention"],
                "constraint_fit": source_counts["constraint_fit"],
                "random": source_counts["random"],
                "candidates_json": json.dumps([c.to_dict() for c in all_candidates]),
                "player_context_json": json.dumps(player_context),
                "version": "v1",
            }
        )
        result["candidate_set_id"] = str(candidate_set_id)
    
    return result


def run_candidate_generation(
    as_of: Optional[datetime] = None,
    horizon_days: int = 90,
    player_ids: Optional[List[str]] = None,
    save_to_db: bool = True,
) -> Dict[str, Any]:
    """
    Generate candidate sets for all active players (or specified players).
    
    Args:
        as_of: Point-in-time for generation (defaults to now)
        horizon_days: Prediction horizon
        player_ids: Specific players to process (or None for all)
        save_to_db: Whether to save to database
        
    Returns:
        Dict with generation stats
    """
    if as_of is None:
        as_of = datetime.utcnow()
    
    console.print(f"[bold blue]🎯 Generating Candidate Sets[/bold blue]")
    console.print(f"  • As of: {as_of.isoformat()}")
    console.print(f"  • Horizon: {horizon_days} days")
    
    config = CandidateConfig()
    stats = {
        "as_of": as_of.isoformat(),
        "horizon_days": horizon_days,
        "players_processed": 0,
        "total_candidates_generated": 0,
        "source_totals": {
            "league": 0,
            "social": 0,
            "user_attention": 0,
            "constraint_fit": 0,
            "random": 0,
        },
        "errors": 0,
    }
    
    with get_sync_session() as session:
        # Get players to process
        if player_ids:
            players = session.execute(
                text("""
                    SELECT id, name FROM players
                    WHERE id = ANY(:ids) AND is_active = true
                """),
                {"ids": [UUID(p) for p in player_ids]}
            ).fetchall()
        else:
            players = session.execute(
                text("""
                    SELECT id, name FROM players
                    WHERE is_active = true AND current_club_id IS NOT NULL
                """)
            ).fetchall()
        
        console.print(f"\nProcessing {len(players)} players...")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console,
        ) as progress:
            task = progress.add_task("Generating candidates...", total=len(players))
            
            for player in players:
                try:
                    result = generate_candidates_for_player(
                        session,
                        player.id,
                        as_of,
                        horizon_days,
                        config,
                        save_to_db,
                    )
                    
                    if "error" not in result:
                        stats["players_processed"] += 1
                        stats["total_candidates_generated"] += result["total_candidates"]
                        
                        for source, count in result["source_counts"].items():
                            stats["source_totals"][source] += count
                    else:
                        stats["errors"] += 1
                        
                except Exception as e:
                    console.print(f"[red]Error for {player.name}: {e}[/red]")
                    stats["errors"] += 1
                
                progress.update(task, advance=1)
        
        if save_to_db:
            session.commit()
    
    # Display results
    console.print("\n[bold green]✅ Candidate Generation Complete![/bold green]")
    console.print(f"  • Players processed: {stats['players_processed']}")
    console.print(f"  • Total candidates: {stats['total_candidates_generated']}")
    console.print(f"  • Avg per player: {stats['total_candidates_generated'] / max(stats['players_processed'], 1):.1f}")
    
    # Source breakdown
    console.print("\n[bold]Candidates by Source:[/bold]")
    for source, count in stats["source_totals"].items():
        pct = (count / max(stats["total_candidates_generated"], 1)) * 100
        console.print(f"  • {source}: {count} ({pct:.1f}%)")
    
    if stats["errors"]:
        console.print(f"\n[yellow]⚠️ Errors: {stats['errors']}[/yellow]")
    
    return stats


def get_candidates_for_prediction(
    session: Session,
    player_id: UUID,
    as_of: datetime,
    horizon_days: int = 90,
) -> List[UUID]:
    """
    Get candidate club IDs for prediction.
    
    First checks candidate_sets table, falls back to generation if not found.
    
    Returns:
        List of candidate club UUIDs
    """
    # Try to get from cached candidate set
    cached = session.execute(
        text("""
            SELECT candidates_json FROM candidate_sets
            WHERE player_id = :player_id
            AND as_of = :as_of
            AND horizon_days = :horizon_days
        """),
        {"player_id": player_id, "as_of": as_of, "horizon_days": horizon_days}
    ).first()
    
    if cached:
        candidates_data = json.loads(cached.candidates_json)
        return [UUID(c["club_id"]) for c in candidates_data]
    
    # Generate on-demand
    result = generate_candidates_for_player(
        session, player_id, as_of, horizon_days, save_to_db=True
    )
    
    if "error" in result:
        return []
    
    return [UUID(c["club_id"]) for c in result["candidates"]]
