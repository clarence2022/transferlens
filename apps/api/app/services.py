"""
TransferLens Business Logic Services
====================================

Contains core business logic including:
- "What Changed" signal delta detection
- Search ranking
- Signal aggregation
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID

from sqlalchemy import select, func, and_, or_, desc, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    Player, Club, Competition, SignalEvent, PredictionSnapshot, TransferEvent,
    SignalTypeEnum, EntityType
)
from app.schemas import SignalDelta, SearchResult, SearchResultType


# =============================================================================
# WHAT CHANGED SERVICE
# =============================================================================

# Thresholds for detecting significant changes
CHANGE_THRESHOLDS = {
    SignalTypeEnum.CONTRACT_MONTHS_REMAINING: {
        "threshold": 6,  # Alert when crossing 6 months
        "severity_mapping": lambda old, new: "alert" if new <= 6 else "warning"
    },
    SignalTypeEnum.MARKET_VALUE: {
        "percent_change": 10,  # 10% change is significant
        "severity_mapping": lambda old, new: "alert" if abs((new - old) / old * 100) > 20 else "warning"
    },
    SignalTypeEnum.INJURIES_STATUS: {
        "any_change": True,
        "severity_mapping": lambda old, new: "alert" if new != "fit" else "info"
    },
    SignalTypeEnum.SOCIAL_MENTION_VELOCITY: {
        "percent_change": 50,  # 50% spike is significant
        "severity_mapping": lambda old, new: "alert" if new > old * 2 else "warning"
    },
    SignalTypeEnum.USER_ATTENTION_VELOCITY: {
        "percent_change": 100,  # Doubling is significant
        "severity_mapping": lambda old, new: "alert" if new > old * 3 else "warning"
    },
    SignalTypeEnum.GOALS_LAST_10: {
        "absolute_change": 2,
        "severity_mapping": lambda old, new: "info"
    },
    SignalTypeEnum.ASSISTS_LAST_10: {
        "absolute_change": 2,
        "severity_mapping": lambda old, new: "info"
    },
    SignalTypeEnum.CLUB_LEAGUE_POSITION: {
        "absolute_change": 3,
        "severity_mapping": lambda old, new: "warning" if abs(new - old) >= 5 else "info"
    },
}


async def get_what_changed(
    db: AsyncSession,
    player_id: UUID,
    days: int = 7
) -> List[SignalDelta]:
    """
    Detect significant signal changes for a player over the last N days.
    
    Returns a list of SignalDelta objects describing what changed.
    """
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    # Get signals from the period, ordered by effective_from
    stmt = (
        select(SignalEvent)
        .where(
            and_(
                SignalEvent.player_id == player_id,
                SignalEvent.entity_type == EntityType.PLAYER,
                SignalEvent.effective_from >= cutoff
            )
        )
        .order_by(SignalEvent.signal_type, SignalEvent.effective_from)
    )
    
    result = await db.execute(stmt)
    signals = result.scalars().all()
    
    # Group signals by type
    by_type: Dict[SignalTypeEnum, List[SignalEvent]] = {}
    for signal in signals:
        if signal.signal_type not in by_type:
            by_type[signal.signal_type] = []
        by_type[signal.signal_type].append(signal)
    
    deltas: List[SignalDelta] = []
    
    for signal_type, signal_list in by_type.items():
        if len(signal_list) < 2:
            continue
        
        # Get oldest and newest in the period
        oldest = signal_list[0]
        newest = signal_list[-1]
        
        delta = _detect_delta(signal_type, oldest, newest)
        if delta:
            deltas.append(delta)
    
    # Also check for signals that just appeared (no prior value)
    for signal_type, signal_list in by_type.items():
        if len(signal_list) == 1:
            signal = signal_list[0]
            # Check if this is a new injury or status change
            if signal_type == SignalTypeEnum.INJURIES_STATUS:
                value = signal.value_text
                if value and value != "fit":
                    deltas.append(SignalDelta(
                        signal_type=signal_type,
                        description=f"New injury status: {value}",
                        old_value=None,
                        new_value=value,
                        severity="alert",
                        observed_at=signal.observed_at
                    ))
    
    # Sort by severity (alert > warning > info) then by time
    severity_order = {"alert": 0, "warning": 1, "info": 2}
    deltas.sort(key=lambda d: (severity_order.get(d.severity, 3), -d.observed_at.timestamp()))
    
    return deltas[:10]  # Return top 10 changes


def _detect_delta(
    signal_type: SignalTypeEnum,
    old_signal: SignalEvent,
    new_signal: SignalEvent
) -> Optional[SignalDelta]:
    """Detect if there's a significant change between two signals."""
    
    config = CHANGE_THRESHOLDS.get(signal_type)
    if not config:
        return None
    
    # Get values
    old_val = _get_signal_value(old_signal)
    new_val = _get_signal_value(new_signal)
    
    if old_val is None or new_val is None:
        return None
    
    # Check for any change (text values like injury status)
    if config.get("any_change"):
        if old_val != new_val:
            return SignalDelta(
                signal_type=signal_type,
                description=_format_change_description(signal_type, old_val, new_val),
                old_value=old_val,
                new_value=new_val,
                severity=config["severity_mapping"](old_val, new_val),
                observed_at=new_signal.observed_at
            )
        return None
    
    # Numeric comparisons
    try:
        old_num = float(old_val) if old_val else 0
        new_num = float(new_val) if new_val else 0
    except (ValueError, TypeError):
        return None
    
    # Check threshold crossing
    if "threshold" in config:
        threshold = config["threshold"]
        if old_num > threshold >= new_num:
            return SignalDelta(
                signal_type=signal_type,
                description=_format_change_description(signal_type, old_val, new_val),
                old_value=old_val,
                new_value=new_val,
                severity=config["severity_mapping"](old_num, new_num),
                observed_at=new_signal.observed_at
            )
    
    # Check percent change
    if "percent_change" in config and old_num != 0:
        pct_change = abs((new_num - old_num) / old_num * 100)
        if pct_change >= config["percent_change"]:
            return SignalDelta(
                signal_type=signal_type,
                description=_format_change_description(signal_type, old_val, new_val),
                old_value=old_val,
                new_value=new_val,
                change_percent=round(pct_change, 1),
                severity=config["severity_mapping"](old_num, new_num),
                observed_at=new_signal.observed_at
            )
    
    # Check absolute change
    if "absolute_change" in config:
        abs_change = abs(new_num - old_num)
        if abs_change >= config["absolute_change"]:
            return SignalDelta(
                signal_type=signal_type,
                description=_format_change_description(signal_type, old_val, new_val),
                old_value=old_val,
                new_value=new_val,
                severity=config["severity_mapping"](old_num, new_num),
                observed_at=new_signal.observed_at
            )
    
    return None


def _get_signal_value(signal: SignalEvent) -> Any:
    """Extract the value from a signal event."""
    if signal.value_num is not None:
        return signal.value_num
    if signal.value_text is not None:
        return signal.value_text
    if signal.value_json is not None:
        return signal.value_json
    return None


def _format_change_description(signal_type: SignalTypeEnum, old_val: Any, new_val: Any) -> str:
    """Format a human-readable description of the change."""
    type_name = signal_type.value.replace("_", " ").title()
    
    if signal_type == SignalTypeEnum.CONTRACT_MONTHS_REMAINING:
        return f"Contract down to {new_val} months remaining"
    
    if signal_type == SignalTypeEnum.MARKET_VALUE:
        old_m = float(old_val) / 1_000_000 if old_val else 0
        new_m = float(new_val) / 1_000_000 if new_val else 0
        direction = "up" if new_m > old_m else "down"
        return f"Market value {direction} to €{new_m:.1f}M"
    
    if signal_type == SignalTypeEnum.INJURIES_STATUS:
        return f"Injury status changed to: {new_val}"
    
    if signal_type == SignalTypeEnum.SOCIAL_MENTION_VELOCITY:
        return f"Social media velocity spiked to {new_val}"
    
    if signal_type == SignalTypeEnum.USER_ATTENTION_VELOCITY:
        return f"User attention increased to {new_val}"
    
    if signal_type == SignalTypeEnum.GOALS_LAST_10:
        return f"Goals in last 10 games: {old_val} → {new_val}"
    
    if signal_type == SignalTypeEnum.ASSISTS_LAST_10:
        return f"Assists in last 10 games: {old_val} → {new_val}"
    
    return f"{type_name}: {old_val} → {new_val}"


# =============================================================================
# SEARCH SERVICE
# =============================================================================

async def search_entities(
    db: AsyncSession,
    query: str,
    limit: int = 20
) -> List[SearchResult]:
    """
    Search players and clubs by name.
    
    Uses PostgreSQL trigram similarity for fuzzy matching.
    Results are ranked by similarity score.
    """
    if not query or len(query) < 2:
        return []
    
    query_lower = query.lower()
    results: List[SearchResult] = []
    
    # Search players
    player_stmt = (
        select(
            Player.id,
            Player.name,
            Player.position,
            Player.nationality,
            Player.photo_url,
            func.similarity(func.lower(Player.name), query_lower).label("score")
        )
        .where(
            and_(
                Player.is_active == True,
                or_(
                    func.lower(Player.name).contains(query_lower),
                    func.similarity(func.lower(Player.name), query_lower) > 0.1
                )
            )
        )
        .order_by(desc("score"))
        .limit(limit)
    )
    
    player_result = await db.execute(player_stmt)
    for row in player_result:
        subtitle_parts = []
        if row.position:
            subtitle_parts.append(row.position)
        if row.nationality:
            subtitle_parts.append(row.nationality)
        
        results.append(SearchResult(
            type=SearchResultType.PLAYER,
            id=row.id,
            name=row.name,
            subtitle=" • ".join(subtitle_parts) if subtitle_parts else None,
            image_url=row.photo_url,
            score=float(row.score) if row.score else 0.0
        ))
    
    # Search clubs
    club_stmt = (
        select(
            Club.id,
            Club.name,
            Club.country,
            Club.logo_url,
            func.similarity(func.lower(Club.name), query_lower).label("score")
        )
        .where(
            and_(
                Club.is_active == True,
                or_(
                    func.lower(Club.name).contains(query_lower),
                    func.similarity(func.lower(Club.name), query_lower) > 0.1
                )
            )
        )
        .order_by(desc("score"))
        .limit(limit)
    )
    
    club_result = await db.execute(club_stmt)
    for row in club_result:
        results.append(SearchResult(
            type=SearchResultType.CLUB,
            id=row.id,
            name=row.name,
            subtitle=row.country,
            image_url=row.logo_url,
            score=float(row.score) if row.score else 0.0
        ))
    
    # Sort combined results by score
    results.sort(key=lambda r: r.score, reverse=True)
    
    return results[:limit]


# =============================================================================
# LATEST SIGNALS SERVICE
# =============================================================================

async def get_latest_player_signals(
    db: AsyncSession,
    player_id: UUID,
    as_of: Optional[datetime] = None
) -> Dict[SignalTypeEnum, Any]:
    """
    Get the latest signal value for each signal type for a player.
    
    If as_of is provided, returns the latest value as of that timestamp.
    """
    if as_of is None:
        as_of = datetime.utcnow()
    
    # Use window function to get latest per signal type
    subquery = (
        select(
            SignalEvent.signal_type,
            SignalEvent.value_num,
            SignalEvent.value_text,
            SignalEvent.value_json,
            SignalEvent.observed_at,
            func.row_number().over(
                partition_by=SignalEvent.signal_type,
                order_by=SignalEvent.effective_from.desc()
            ).label("rn")
        )
        .where(
            and_(
                SignalEvent.player_id == player_id,
                SignalEvent.entity_type == EntityType.PLAYER,
                SignalEvent.effective_from <= as_of
            )
        )
        .subquery()
    )
    
    stmt = select(subquery).where(subquery.c.rn == 1)
    result = await db.execute(stmt)
    
    signals: Dict[SignalTypeEnum, Any] = {}
    for row in result:
        signal_type = row.signal_type
        if row.value_num is not None:
            signals[signal_type] = row.value_num
        elif row.value_text is not None:
            signals[signal_type] = row.value_text
        elif row.value_json is not None:
            signals[signal_type] = row.value_json
    
    return signals


# =============================================================================
# PLAYER AGE CALCULATION
# =============================================================================

def calculate_age(date_of_birth: Optional[Any]) -> Optional[int]:
    """Calculate age from date of birth."""
    if not date_of_birth:
        return None
    
    today = datetime.today().date()
    
    # Handle both date and datetime objects
    if hasattr(date_of_birth, 'date'):
        dob = date_of_birth.date()
    else:
        dob = date_of_birth
    
    age = today.year - dob.year
    if (today.month, today.day) < (dob.month, dob.day):
        age -= 1
    
    return age
