"""
Signal Derivation from User Events
==================================

Derives weak signals from user behavior:
- user_attention_velocity: How quickly attention is increasing for a player
- user_destination_cooccurrence: Which clubs users view together with a player

These signals have lower confidence (0.6) but can be leading indicators.

Run with: python -m worker.cli signals:derive --window 24h
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from uuid import uuid4
from collections import defaultdict

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from sqlalchemy import text
from sqlalchemy.orm import Session

from worker.database import get_sync_session
from worker.config import settings

console = Console()


def parse_window(window: str) -> timedelta:
    """Parse window string like '24h', '7d' into timedelta."""
    if window.endswith('h'):
        return timedelta(hours=int(window[:-1]))
    elif window.endswith('d'):
        return timedelta(days=int(window[:-1]))
    elif window.endswith('m'):
        return timedelta(minutes=int(window[:-1]))
    else:
        return timedelta(hours=24)


def compute_attention_velocity(
    session: Session,
    window: timedelta,
    as_of: datetime
) -> List[Dict[str, Any]]:
    """
    Compute user_attention_velocity for each player.
    
    Velocity = (views in recent half) / (views in older half)
    High velocity means increasing attention.
    """
    window_start = as_of - window
    midpoint = as_of - (window / 2)
    
    # Count views in recent vs older half of window
    view_counts = session.execute(
        text("""
            SELECT 
                player_id,
                COUNT(*) FILTER (WHERE occurred_at >= :midpoint) as recent_views,
                COUNT(*) FILTER (WHERE occurred_at < :midpoint) as older_views,
                COUNT(*) as total_views
            FROM user_events
            WHERE player_id IS NOT NULL
            AND event_type IN ('player_view', 'watchlist_add', 'share')
            AND occurred_at >= :window_start
            AND occurred_at <= :as_of
            GROUP BY player_id
            HAVING COUNT(*) >= 3
        """),
        {"window_start": window_start, "midpoint": midpoint, "as_of": as_of}
    ).fetchall()
    
    velocities = []
    for row in view_counts:
        recent = row.recent_views or 0
        older = row.older_views or 1  # Avoid division by zero
        
        # Velocity is ratio of recent to older, capped at 10
        velocity = min(10.0, (recent + 1) / (older + 1))
        
        # Normalize to 0-1000 scale for storage
        normalized_velocity = int(velocity * 100)
        
        velocities.append({
            "player_id": row.player_id,
            "velocity": normalized_velocity,
            "recent_views": recent,
            "older_views": older,
            "total_views": row.total_views,
        })
    
    return velocities


def compute_destination_cooccurrence(
    session: Session,
    window: timedelta,
    as_of: datetime
) -> List[Dict[str, Any]]:
    """
    Compute user_destination_cooccurrence for (player, club) pairs.
    
    Looks at sessions where users viewed both a player and a club,
    suggesting interest in that player moving to that club.
    """
    window_start = as_of - window
    
    # Find sessions with both player and club views
    cooccurrences = session.execute(
        text("""
            WITH player_sessions AS (
                SELECT DISTINCT session_id, player_id
                FROM user_events
                WHERE player_id IS NOT NULL
                AND event_type IN ('player_view', 'watchlist_add')
                AND occurred_at >= :window_start
                AND occurred_at <= :as_of
            ),
            club_sessions AS (
                SELECT DISTINCT session_id, club_id
                FROM user_events
                WHERE club_id IS NOT NULL
                AND event_type IN ('club_view')
                AND occurred_at >= :window_start
                AND occurred_at <= :as_of
            )
            SELECT 
                ps.player_id,
                cs.club_id,
                COUNT(DISTINCT ps.session_id) as session_count
            FROM player_sessions ps
            JOIN club_sessions cs ON ps.session_id = cs.session_id
            GROUP BY ps.player_id, cs.club_id
            HAVING COUNT(DISTINCT ps.session_id) >= 2
        """),
        {"window_start": window_start, "as_of": as_of}
    ).fetchall()
    
    results = []
    for row in cooccurrences:
        # Normalize session count to 0-100 scale
        normalized_score = min(100, row.session_count * 10)
        
        results.append({
            "player_id": row.player_id,
            "club_id": row.club_id,
            "session_count": row.session_count,
            "score": normalized_score,
        })
    
    return results


def write_signal_event(
    session: Session,
    entity_type: str,
    player_id: Optional[str],
    club_id: Optional[str],
    signal_type: str,
    value_num: float,
    observed_at: datetime,
    effective_from: datetime,
) -> None:
    """Write a derived signal event to the database."""
    session.execute(
        text("""
            INSERT INTO signal_events (
                id, entity_type, player_id, club_id, signal_type,
                value_num, source, confidence, observed_at, effective_from
            ) VALUES (
                :id, :entity_type, :player_id, :club_id, :signal_type,
                :value_num, 'tl_user_derived', :confidence, :observed_at, :effective_from
            )
        """),
        {
            "id": uuid4(),
            "entity_type": entity_type,
            "player_id": player_id,
            "club_id": club_id,
            "signal_type": signal_type,
            "value_num": value_num,
            "confidence": settings.derived_signal_confidence,
            "observed_at": observed_at,
            "effective_from": effective_from,
        }
    )


def run_signal_derivation(
    window: str = "24h",
    as_of: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Derive user signals from recent user events.
    
    Args:
        window: Time window to analyze (e.g., '24h', '7d')
        as_of: Timestamp for derivation (defaults to now)
        
    Returns:
        dict with derivation stats
    """
    if as_of is None:
        as_of = datetime.utcnow()
    
    window_delta = parse_window(window)
    
    console.print(f"[bold blue]📊 Deriving user signals...[/bold blue]")
    console.print(f"  • Window: {window} ({window_delta})")
    console.print(f"  • As of: {as_of.isoformat()}")
    
    stats = {
        "window": window,
        "as_of": as_of.isoformat(),
        "attention_signals": 0,
        "cooccurrence_signals": 0,
        "errors": 0,
    }
    
    with get_sync_session() as session:
        # Compute attention velocities
        console.print("\n[bold]Computing attention velocities...[/bold]")
        velocities = compute_attention_velocity(session, window_delta, as_of)
        console.print(f"  Found {len(velocities)} players with sufficient activity")
        
        # Write attention signals
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console,
        ) as progress:
            task = progress.add_task("Writing attention signals...", total=len(velocities))
            
            for vel in velocities:
                try:
                    write_signal_event(
                        session,
                        entity_type="player",
                        player_id=str(vel["player_id"]),
                        club_id=None,
                        signal_type="user_attention_velocity",
                        value_num=vel["velocity"],
                        observed_at=as_of,
                        effective_from=as_of,
                    )
                    stats["attention_signals"] += 1
                except Exception as e:
                    console.print(f"[red]Error writing attention signal: {e}[/red]")
                    stats["errors"] += 1
                
                progress.update(task, advance=1)
        
        session.commit()
        console.print(f"  Created {stats['attention_signals']} attention velocity signals")
        
        # Compute destination co-occurrences
        console.print("\n[bold]Computing destination co-occurrences...[/bold]")
        cooccurrences = compute_destination_cooccurrence(session, window_delta * 7, as_of)  # Use 7x window for co-occurrence
        console.print(f"  Found {len(cooccurrences)} (player, club) pairs with co-occurrence")
        
        # Write co-occurrence signals
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console,
        ) as progress:
            task = progress.add_task("Writing co-occurrence signals...", total=len(cooccurrences))
            
            for cooc in cooccurrences:
                try:
                    write_signal_event(
                        session,
                        entity_type="club_player_pair",
                        player_id=str(cooc["player_id"]),
                        club_id=str(cooc["club_id"]),
                        signal_type="user_destination_cooccurrence",
                        value_num=cooc["score"],
                        observed_at=as_of,
                        effective_from=as_of,
                    )
                    stats["cooccurrence_signals"] += 1
                except Exception as e:
                    console.print(f"[red]Error writing co-occurrence signal: {e}[/red]")
                    stats["errors"] += 1
                
                progress.update(task, advance=1)
        
        session.commit()
        console.print(f"  Created {stats['cooccurrence_signals']} co-occurrence signals")
    
    console.print("\n[bold green]✅ Signal derivation complete![/bold green]")
    console.print(f"  • Attention signals: {stats['attention_signals']}")
    console.print(f"  • Co-occurrence signals: {stats['cooccurrence_signals']}")
    console.print(f"  • Errors: {stats['errors']}")
    
    return stats


def derive_watchlist_adds(
    session: Session,
    window: timedelta,
    as_of: datetime
) -> List[Dict[str, Any]]:
    """
    Compute user_watchlist_adds signal - count of watchlist additions.
    """
    window_start = as_of - window
    
    adds = session.execute(
        text("""
            SELECT 
                player_id,
                COUNT(*) as add_count
            FROM user_events
            WHERE player_id IS NOT NULL
            AND event_type = 'watchlist_add'
            AND occurred_at >= :window_start
            AND occurred_at <= :as_of
            GROUP BY player_id
        """),
        {"window_start": window_start, "as_of": as_of}
    ).fetchall()
    
    return [{"player_id": row.player_id, "count": row.add_count} for row in adds]
