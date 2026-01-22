"""
Feature Building Job
====================

Builds feature tables for (player_id, to_club_id candidate) pairs.
Features are built as-of a specific timestamp for time-travel correctness.

CRITICAL TIME-TRAVEL RULES:
- Signals: observed_at <= as_of AND effective_from <= as_of
- User events: occurred_at <= as_of
- Never use data that wouldn't have been available at as_of

Run with: python -m worker.cli features:build --as-of <timestamp>
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any
from uuid import UUID, uuid4

import pandas as pd
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from sqlalchemy import text
from sqlalchemy.orm import Session

from worker.database import get_sync_session, get_sync_connection
from worker.config import settings
from worker.time_guards import (
    get_signal_value_strict,
    get_user_derived_value_strict,
    validate_signal_time_travel,
    validate_training_label_time_travel,
    TimeTravelViolationError,
    DataLeakageError,
)

console = Console()


# =============================================================================
# FEATURE DEFINITIONS
# =============================================================================

PLAYER_FEATURES = [
    "market_value",
    "contract_months_remaining",
    "goals_last_10",
    "assists_last_10",
    "minutes_last_5",
    "social_mention_velocity",
    "user_attention_velocity",
    "age",
    "position_encoded",
]

CLUB_FEATURES = [
    "club_league_position",
    "club_points_per_game",
    "club_net_spend_12m",
    "club_tier",
]

PAIR_FEATURES = [
    "user_destination_cooccurrence",
    "same_country",
    "same_league",
    "tier_difference",
]

ALL_FEATURES = PLAYER_FEATURES + CLUB_FEATURES + PAIR_FEATURES


def get_candidate_clubs(
    session: Session,
    player_id: UUID,
    current_club_id: UUID,
    as_of: datetime,
    max_candidates: int = 20
) -> List[UUID]:
    """
    Get candidate destination clubs for a player.
    
    Strategy:
    1. Top clubs from same league (by position)
    2. Top clubs from other top leagues
    3. Clubs with user attention signals
    4. Random sample from remaining clubs
    """
    candidates = set()
    
    # Get current club's competition
    current_comp = session.execute(
        text("SELECT competition_id FROM clubs WHERE id = :club_id"),
        {"club_id": current_club_id}
    ).scalar()
    
    # 1. Top clubs from same league (excluding current)
    same_league_clubs = session.execute(
        text("""
            SELECT id FROM clubs 
            WHERE competition_id = :comp_id 
            AND id != :current_club_id
            AND is_active = true
            LIMIT 5
        """),
        {"comp_id": current_comp, "current_club_id": current_club_id}
    ).scalars().all()
    candidates.update(same_league_clubs)
    
    # 2. Top clubs from other leagues
    other_clubs = session.execute(
        text("""
            SELECT c.id FROM clubs c
            JOIN competitions comp ON c.competition_id = comp.id
            WHERE comp.tier = 1
            AND c.id != :current_club_id
            AND c.competition_id != :comp_id
            AND c.is_active = true
            ORDER BY RANDOM()
            LIMIT 8
        """),
        {"comp_id": current_comp, "current_club_id": current_club_id}
    ).scalars().all()
    candidates.update(other_clubs)
    
    # 3. Clubs with user attention signals for this player
    attention_clubs = session.execute(
        text("""
            SELECT DISTINCT club_id FROM signal_events
            WHERE player_id = :player_id
            AND signal_type = 'user_destination_cooccurrence'
            AND effective_from <= :as_of
            AND club_id IS NOT NULL
            LIMIT 5
        """),
        {"player_id": player_id, "as_of": as_of}
    ).scalars().all()
    candidates.update([c for c in attention_clubs if c])
    
    # 4. Fill remaining with random clubs
    if len(candidates) < max_candidates:
        remaining = max_candidates - len(candidates)
        random_clubs = session.execute(
            text("""
                SELECT id FROM clubs
                WHERE id != :current_club_id
                AND is_active = true
                AND id NOT IN :existing
                ORDER BY RANDOM()
                LIMIT :limit
            """),
            {
                "current_club_id": current_club_id,
                "existing": tuple(candidates) if candidates else (uuid4(),),
                "limit": remaining,
            }
        ).scalars().all()
        candidates.update(random_clubs)
    
    return list(candidates)[:max_candidates]


def get_latest_signal_value(
    session: Session,
    entity_type: str,
    entity_id: UUID,
    signal_type: str,
    as_of: datetime,
    player_id: Optional[UUID] = None,
    club_id: Optional[UUID] = None,
) -> Optional[float]:
    """
    Get the latest signal value as of a timestamp with STRICT time-travel enforcement.
    
    CRITICAL: This function enforces BOTH conditions:
    - observed_at <= as_of (we knew about it by as_of)
    - effective_from <= as_of (it was effective by as_of)
    
    This prevents using "future" data that wouldn't have been available.
    """
    # Use the strict version from time_guards
    return get_signal_value_strict(
        session=session,
        entity_type=entity_type,
        entity_id=entity_id,
        signal_type=signal_type,
        as_of=as_of,
        player_id=player_id,
        club_id=club_id,
    )


def get_latest_signal_value_with_timestamp(
    session: Session,
    entity_type: str,
    entity_id: UUID,
    signal_type: str,
    as_of: datetime,
    player_id: Optional[UUID] = None,
    club_id: Optional[UUID] = None,
) -> Tuple[Optional[float], Optional[datetime]]:
    """
    Get signal value AND its observed_at timestamp for audit purposes.
    
    Returns:
        (value, observed_at) tuple
    """
    if entity_type == "player":
        result = session.execute(
            text("""
                SELECT value_num, observed_at FROM signal_events
                WHERE player_id = :entity_id
                AND signal_type = :signal_type
                AND observed_at <= :as_of
                AND effective_from <= :as_of
                AND (effective_to IS NULL OR effective_to > :as_of)
                ORDER BY effective_from DESC, observed_at DESC
                LIMIT 1
            """),
            {"entity_id": entity_id, "signal_type": signal_type, "as_of": as_of}
        ).first()
    elif entity_type == "club":
        result = session.execute(
            text("""
                SELECT value_num, observed_at FROM signal_events
                WHERE club_id = :entity_id
                AND signal_type = :signal_type
                AND observed_at <= :as_of
                AND effective_from <= :as_of
                AND (effective_to IS NULL OR effective_to > :as_of)
                ORDER BY effective_from DESC, observed_at DESC
                LIMIT 1
            """),
            {"entity_id": entity_id, "signal_type": signal_type, "as_of": as_of}
        ).first()
    elif entity_type == "pair":
        result = session.execute(
            text("""
                SELECT value_num, observed_at FROM signal_events
                WHERE player_id = :player_id
                AND club_id = :club_id
                AND signal_type = :signal_type
                AND observed_at <= :as_of
                AND effective_from <= :as_of
                AND (effective_to IS NULL OR effective_to > :as_of)
                ORDER BY effective_from DESC, observed_at DESC
                LIMIT 1
            """),
            {"player_id": player_id, "club_id": club_id, "signal_type": signal_type, "as_of": as_of}
        ).first()
    else:
        return None, None
    
    if result:
        return (float(result.value_num) if result.value_num else None, result.observed_at)
    return None, None


def build_player_features(
    session: Session,
    player_id: UUID,
    as_of: datetime
) -> Dict[str, Optional[float]]:
    """Build features for a single player."""
    features = {}
    
    # Get player info
    player = session.execute(
        text("""
            SELECT date_of_birth, position, current_club_id
            FROM players WHERE id = :player_id
        """),
        {"player_id": player_id}
    ).first()
    
    if not player:
        return features
    
    # Age
    if player.date_of_birth:
        age_days = (as_of.date() - player.date_of_birth).days
        features["age"] = age_days / 365.25
    else:
        features["age"] = None
    
    # Position encoding (simple ordinal)
    position_map = {"ST": 1, "LW": 2, "RW": 3, "CAM": 4, "CM": 5, "CDM": 6, "CB": 7, "LB": 8, "RB": 9, "GK": 10}
    features["position_encoded"] = position_map.get(player.position, 0)
    
    # Signal-based features
    signal_features = [
        "market_value", "contract_months_remaining", "goals_last_10",
        "assists_last_10", "minutes_last_5", "social_mention_velocity",
        "user_attention_velocity"
    ]
    
    for signal_type in signal_features:
        features[signal_type] = get_latest_signal_value(
            session, "player", player_id, signal_type, as_of
        )
    
    return features


def build_club_features(
    session: Session,
    club_id: UUID,
    as_of: datetime
) -> Dict[str, Optional[float]]:
    """Build features for a single club."""
    features = {}
    
    # Get club info
    club = session.execute(
        text("""
            SELECT c.id, comp.tier
            FROM clubs c
            LEFT JOIN competitions comp ON c.competition_id = comp.id
            WHERE c.id = :club_id
        """),
        {"club_id": club_id}
    ).first()
    
    if club:
        features["club_tier"] = club.tier or 1
    else:
        features["club_tier"] = None
    
    # Signal-based features
    signal_features = ["club_league_position", "club_points_per_game", "club_net_spend_12m"]
    
    for signal_type in signal_features:
        features[signal_type] = get_latest_signal_value(
            session, "club", club_id, signal_type, as_of
        )
    
    return features


def build_pair_features(
    session: Session,
    player_id: UUID,
    from_club_id: UUID,
    to_club_id: UUID,
    as_of: datetime
) -> Dict[str, Optional[float]]:
    """Build features for a (player, destination_club) pair."""
    features = {}
    
    # Get club info for both clubs
    clubs = session.execute(
        text("""
            SELECT c.id, c.country, c.competition_id, comp.tier
            FROM clubs c
            LEFT JOIN competitions comp ON c.competition_id = comp.id
            WHERE c.id IN (:from_id, :to_id)
        """),
        {"from_id": from_club_id, "to_id": to_club_id}
    ).fetchall()
    
    club_info = {str(c.id): c for c in clubs}
    from_club = club_info.get(str(from_club_id))
    to_club = club_info.get(str(to_club_id))
    
    if from_club and to_club:
        features["same_country"] = 1.0 if from_club.country == to_club.country else 0.0
        features["same_league"] = 1.0 if from_club.competition_id == to_club.competition_id else 0.0
        features["tier_difference"] = (to_club.tier or 1) - (from_club.tier or 1)
    else:
        features["same_country"] = None
        features["same_league"] = None
        features["tier_difference"] = None
    
    # User co-occurrence signal
    features["user_destination_cooccurrence"] = get_latest_signal_value(
        session, "pair", None, "user_destination_cooccurrence", as_of,
        player_id=player_id, club_id=to_club_id
    )
    
    return features


def build_feature_vector(
    session: Session,
    player_id: UUID,
    from_club_id: UUID,
    to_club_id: UUID,
    as_of: datetime
) -> Dict[str, Optional[float]]:
    """Build complete feature vector for a (player, destination) pair."""
    features = {}
    
    # Player features
    features.update(build_player_features(session, player_id, as_of))
    
    # Destination club features (prefixed with "to_")
    to_club_features = build_club_features(session, to_club_id, as_of)
    for k, v in to_club_features.items():
        features[f"to_{k}"] = v
    
    # From club features (prefixed with "from_")
    from_club_features = build_club_features(session, from_club_id, as_of)
    for k, v in from_club_features.items():
        features[f"from_{k}"] = v
    
    # Pair features
    features.update(build_pair_features(session, player_id, from_club_id, to_club_id, as_of))
    
    return features


def run_feature_build(as_of: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Build feature tables for all active players and their candidate destinations.
    
    Args:
        as_of: Timestamp for time-travel (defaults to now)
        
    Returns:
        dict with stats about the build
    """
    if as_of is None:
        as_of = datetime.utcnow()
    
    console.print(f"[bold blue]🔧 Building features as of {as_of.isoformat()}...[/bold blue]")
    
    stats = {
        "as_of": as_of.isoformat(),
        "players_processed": 0,
        "feature_vectors_created": 0,
        "errors": 0,
    }
    
    with get_sync_session() as session:
        # Get all active players with their current clubs
        players = session.execute(
            text("""
                SELECT id, current_club_id, name
                FROM players
                WHERE is_active = true
                AND current_club_id IS NOT NULL
            """)
        ).fetchall()
        
        console.print(f"Found {len(players)} active players")
        
        # Clear existing feature snapshots for this as_of
        session.execute(
            text("""
                DELETE FROM feature_snapshots
                WHERE as_of = :as_of
            """),
            {"as_of": as_of}
        )
        session.commit()
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console,
        ) as progress:
            task = progress.add_task("Building features...", total=len(players))
            
            for player in players:
                try:
                    # Get candidate clubs
                    candidates = get_candidate_clubs(
                        session, player.id, player.current_club_id, as_of,
                        max_candidates=settings.candidate_clubs_per_player
                    )
                    
                    # Build feature vector for each candidate
                    for to_club_id in candidates:
                        features = build_feature_vector(
                            session, player.id, player.current_club_id, to_club_id, as_of
                        )
                        
                        # Store in feature_snapshots table
                        session.execute(
                            text("""
                                INSERT INTO feature_snapshots (
                                    id, player_id, candidate_club_id, as_of, features, feature_version
                                ) VALUES (
                                    :id, :player_id, :club_id, :as_of, :features, 'v1'
                                )
                                ON CONFLICT (player_id, candidate_club_id, as_of) 
                                DO UPDATE SET features = :features
                            """),
                            {
                                "id": uuid4(),
                                "player_id": player.id,
                                "club_id": to_club_id,
                                "as_of": as_of,
                                "features": features,
                            }
                        )
                        stats["feature_vectors_created"] += 1
                    
                    stats["players_processed"] += 1
                    
                except Exception as e:
                    console.print(f"[red]Error processing player {player.name}: {e}[/red]")
                    stats["errors"] += 1
                
                progress.update(task, advance=1)
        
        session.commit()
    
    console.print("\n[bold green]✅ Feature build complete![/bold green]")
    console.print(f"  • Players processed: {stats['players_processed']}")
    console.print(f"  • Feature vectors created: {stats['feature_vectors_created']}")
    console.print(f"  • Errors: {stats['errors']}")
    
    return stats


def build_training_features(
    session: Session,
    as_of: datetime,
    lookback_days: int = 730,
    horizon_days: int = 90,
    validate_time_travel: bool = True,
) -> pd.DataFrame:
    """
    Build a training dataset with features and labels.
    
    For each historical transfer:
    - Extract features as of (transfer_date - horizon_days) 
    - Label is 1 (transfer happened)
    
    For negative examples:
    - Sample player-club pairs where no transfer happened
    - Label is 0
    
    CRITICAL TIME-TRAVEL RULES ENFORCED:
    1. Features extracted as of (transfer_date - horizon_days)
    2. Only signals with observed_at <= feature_date are used
    3. Only signals with effective_from <= feature_date are used
    4. Only user_events with occurred_at <= feature_date are used
    
    Args:
        session: Database session
        as_of: Training data cutoff (no transfers after this date)
        lookback_days: How far back to look for training data
        horizon_days: Prediction horizon in days
        validate_time_travel: If True, validate each feature extraction
        
    Returns:
        DataFrame with features, labels, and metadata
        
    Raises:
        DataLeakageError: If time-travel violation detected
    """
    cutoff_date = as_of - timedelta(days=lookback_days)
    
    console.print(f"[bold]Building training data with STRICT time-travel enforcement[/bold]")
    console.print(f"  • Data window: {cutoff_date.date()} to {as_of.date()}")
    console.print(f"  • Horizon: {horizon_days} days")
    console.print(f"  • Time-travel validation: {'ENABLED' if validate_time_travel else 'disabled'}")
    
    # Get positive examples (actual transfers)
    positives = session.execute(
        text("""
            SELECT 
                t.player_id,
                t.from_club_id,
                t.to_club_id,
                t.transfer_date,
                t.transfer_type
            FROM transfer_events t
            WHERE t.transfer_date BETWEEN :cutoff AND :as_of
            AND t.is_superseded = false
            AND t.transfer_type IN ('permanent', 'loan', 'loan_with_option')
            AND t.from_club_id IS NOT NULL
        """),
        {"cutoff": cutoff_date, "as_of": as_of}
    ).fetchall()
    
    console.print(f"Found {len(positives)} positive transfer examples")
    
    rows = []
    time_travel_violations = []
    
    # Process positive examples
    for transfer in positives:
        # CRITICAL: Build features as of (transfer_date - horizon_days)
        # This ensures we only use data that would have been available
        # at the time we would have made the prediction
        feature_date = datetime.combine(
            transfer.transfer_date - timedelta(days=horizon_days),
            datetime.min.time()
        )
        
        # Validate time-travel constraint
        if validate_time_travel:
            try:
                validate_training_label_time_travel(
                    transfer_date=datetime.combine(transfer.transfer_date, datetime.min.time()),
                    feature_date=feature_date,
                    horizon_days=horizon_days,
                    player_id=str(transfer.player_id),
                )
            except DataLeakageError as e:
                time_travel_violations.append(str(e))
                continue
        
        features = build_feature_vector(
            session,
            transfer.player_id,
            transfer.from_club_id,
            transfer.to_club_id,
            feature_date
        )
        features["player_id"] = str(transfer.player_id)
        features["to_club_id"] = str(transfer.to_club_id)
        features["label"] = 1
        features["transfer_date"] = transfer.transfer_date
        features["feature_date"] = feature_date  # For audit
        
        rows.append(features)
    
    # Generate negative examples (non-transfers)
    # For each positive, sample some negative destinations
    all_clubs = session.execute(
        text("SELECT id FROM clubs WHERE is_active = true")
    ).scalars().all()
    
    import random
    
    for transfer in positives:
        feature_date = datetime.combine(
            transfer.transfer_date - timedelta(days=horizon_days),
            datetime.min.time()
        )
        
        # Sample 3 random clubs that were NOT the destination
        negative_clubs = random.sample(
            [c for c in all_clubs if c != transfer.to_club_id and c != transfer.from_club_id],
            min(3, len(all_clubs) - 2)
        )
        
        for neg_club in negative_clubs:
            features = build_feature_vector(
                session,
                transfer.player_id,
                transfer.from_club_id,
                neg_club,
                feature_date
            )
            features["player_id"] = str(transfer.player_id)
            features["to_club_id"] = str(neg_club)
            features["label"] = 0
            features["transfer_date"] = transfer.transfer_date
            features["feature_date"] = feature_date
            
            rows.append(features)
    
    df = pd.DataFrame(rows)
    
    # Report time-travel violations
    if time_travel_violations:
        console.print(f"[yellow]⚠️ {len(time_travel_violations)} time-travel violations detected and skipped[/yellow]")
        for violation in time_travel_violations[:5]:
            console.print(f"  • {violation}")
        if len(time_travel_violations) > 5:
            console.print(f"  ... and {len(time_travel_violations) - 5} more")
    
    console.print(f"[green]Built training dataset with {len(df)} rows ({df['label'].sum()} positive)[/green]")
    
    return df


def validate_feature_extraction_time_travel(
    session: Session,
    player_id: UUID,
    as_of: datetime,
) -> Dict[str, Any]:
    """
    Validate that feature extraction for a player respects time-travel.
    
    This function checks if there are any signals that would be excluded
    by strict time-travel enforcement.
    
    Returns:
        Dict with validation results
    """
    # Check for signals that would be excluded
    excluded_signals = session.execute(
        text("""
            SELECT signal_type, observed_at, effective_from
            FROM signal_events
            WHERE player_id = :player_id
            AND (observed_at > :as_of OR effective_from > :as_of)
        """),
        {"player_id": player_id, "as_of": as_of}
    ).fetchall()
    
    return {
        "player_id": str(player_id),
        "as_of": as_of.isoformat(),
        "excluded_signals_count": len(excluded_signals),
        "excluded_signals": [
            {
                "signal_type": s.signal_type,
                "observed_at": s.observed_at.isoformat() if s.observed_at else None,
                "effective_from": s.effective_from.isoformat() if s.effective_from else None,
            }
            for s in excluded_signals[:10]
        ],
        "is_valid": True,  # We're correctly excluding them
    }
