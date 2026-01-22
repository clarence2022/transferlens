"""
Market Router
=============

Market layer endpoints for transfer probability table.
"""

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, and_, desc, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models import (
    PredictionSnapshot, Player, Club, Competition,
    SignalEvent, SignalTypeEnum, EntityType
)
from app.schemas import MarketLatestResponse, ProbabilityRow
from app.services import calculate_age

router = APIRouter(prefix="/market", tags=["Market"])


@router.get("/latest", response_model=MarketLatestResponse)
async def get_market_latest(
    competition_id: Optional[UUID] = Query(None, description="Filter by competition"),
    club_id: Optional[UUID] = Query(None, description="Filter by club (from or to)"),
    horizon_days: Optional[int] = Query(None, description="Filter by prediction horizon (30, 90, 180)"),
    min_probability: Optional[float] = Query(None, ge=0, le=1, description="Minimum probability threshold"),
    limit: int = Query(50, ge=1, le=200, description="Maximum results"),
    db: AsyncSession = Depends(get_db)
) -> MarketLatestResponse:
    """
    Get the latest transfer probability table.
    
    Returns the most recent predictions for each player-destination pair,
    ranked by probability. Supports filtering by competition, club, and horizon.
    
    **Examples:**
    - `/market/latest` - Top 50 transfer probabilities
    - `/market/latest?competition_id=xxx` - Predictions for Premier League clubs
    - `/market/latest?club_id=xxx` - Predictions involving Man City
    - `/market/latest?horizon_days=90&min_probability=0.5` - 90-day predictions above 50%
    
    **Response includes:**
    - Player info (name, position, age, nationality)
    - From/To club info
    - Probability score
    - Driver explanations
    - Market value and contract info
    """
    # Try to use materialized view first, fall back to query if not available
    try:
        # Check if materialized view exists
        check_view = await db.execute(text(
            "SELECT 1 FROM information_schema.tables WHERE table_name = 'player_market_view'"
        ))
        view_exists = check_view.scalar_one_or_none()
        
        if view_exists:
            return await _get_from_materialized_view(
                db, competition_id, club_id, horizon_days, min_probability, limit
            )
    except Exception:
        pass
    
    # Fall back to direct query
    return await _get_from_direct_query(
        db, competition_id, club_id, horizon_days, min_probability, limit
    )


async def _get_from_materialized_view(
    db: AsyncSession,
    competition_id: Optional[UUID],
    club_id: Optional[UUID],
    horizon_days: Optional[int],
    min_probability: Optional[float],
    limit: int
) -> MarketLatestResponse:
    """Query the materialized view for fast reads."""
    conditions = []
    
    if horizon_days:
        conditions.append(f"horizon_days = {horizon_days}")
    
    if min_probability:
        conditions.append(f"probability >= {min_probability}")
    
    # Club filter needs to check both from and to clubs
    # This would need to be done via joins with competition
    # For now, skip competition filter on materialized view
    
    where_clause = " AND ".join(conditions) if conditions else "1=1"
    
    query = text(f"""
        SELECT 
            player_id, player_name, player_position, player_nationality,
            player_photo_url, player_dob,
            from_club_id, from_club_name, from_club_logo_url,
            to_club_id, to_club_name, to_club_logo_url,
            horizon_days, probability, drivers_json,
            market_value, contract_months_remaining,
            as_of, window_end
        FROM player_market_view
        WHERE {where_clause}
        ORDER BY probability DESC
        LIMIT :limit
    """)
    
    result = await db.execute(query, {"limit": limit})
    rows = result.fetchall()
    
    predictions = []
    for row in rows:
        predictions.append(ProbabilityRow(
            player_id=row.player_id,
            player_name=row.player_name,
            player_position=row.player_position,
            player_nationality=row.player_nationality,
            player_photo_url=row.player_photo_url,
            player_age=calculate_age(row.player_dob) if row.player_dob else None,
            from_club_id=row.from_club_id,
            from_club_name=row.from_club_name,
            from_club_logo_url=row.from_club_logo_url,
            to_club_id=row.to_club_id,
            to_club_name=row.to_club_name,
            to_club_logo_url=row.to_club_logo_url,
            horizon_days=row.horizon_days,
            probability=row.probability,
            drivers_json=row.drivers_json or {},
            market_value=row.market_value,
            contract_months_remaining=int(row.contract_months_remaining) if row.contract_months_remaining else None,
            as_of=row.as_of,
            window_end=row.window_end
        ))
    
    return MarketLatestResponse(
        predictions=predictions,
        total=len(predictions),
        as_of=datetime.utcnow(),
        filters_applied={
            "competition_id": str(competition_id) if competition_id else None,
            "club_id": str(club_id) if club_id else None,
            "horizon_days": horizon_days,
            "min_probability": min_probability
        }
    )


async def _get_from_direct_query(
    db: AsyncSession,
    competition_id: Optional[UUID],
    club_id: Optional[UUID],
    horizon_days: Optional[int],
    min_probability: Optional[float],
    limit: int
) -> MarketLatestResponse:
    """Direct query fallback when materialized view is not available."""
    
    # Aliases for from/to clubs
    FromClub = Club.__table__.alias("from_club")
    ToClub = Club.__table__.alias("to_club")
    
    # Build query
    conditions = []
    
    if horizon_days:
        conditions.append(PredictionSnapshot.horizon_days == horizon_days)
    
    if min_probability:
        conditions.append(PredictionSnapshot.probability >= min_probability)
    
    if club_id:
        conditions.append(
            (PredictionSnapshot.from_club_id == club_id) | 
            (PredictionSnapshot.to_club_id == club_id)
        )
    
    # Build the main query
    stmt = (
        select(
            PredictionSnapshot,
            Player.name.label("player_name"),
            Player.position.label("player_position"),
            Player.nationality.label("player_nationality"),
            Player.photo_url.label("player_photo_url"),
            Player.date_of_birth.label("player_dob"),
        )
        .join(Player, PredictionSnapshot.player_id == Player.id)
        .where(and_(*conditions) if conditions else True)
        .order_by(PredictionSnapshot.probability.desc())
        .limit(limit)
    )
    
    result = await db.execute(stmt)
    rows = result.all()
    
    # Fetch club names separately (to avoid complex joins)
    predictions = []
    for row in rows:
        ps = row.PredictionSnapshot
        
        # Get from club name
        from_club_name = None
        from_club_logo = None
        if ps.from_club_id:
            from_club_result = await db.execute(
                select(Club.name, Club.logo_url).where(Club.id == ps.from_club_id)
            )
            from_club_row = from_club_result.first()
            if from_club_row:
                from_club_name = from_club_row.name
                from_club_logo = from_club_row.logo_url
        
        # Get to club name
        to_club_name = None
        to_club_logo = None
        if ps.to_club_id:
            to_club_result = await db.execute(
                select(Club.name, Club.logo_url).where(Club.id == ps.to_club_id)
            )
            to_club_row = to_club_result.first()
            if to_club_row:
                to_club_name = to_club_row.name
                to_club_logo = to_club_row.logo_url
        
        # Get latest market value and contract signals
        market_value = None
        contract_months = None
        
        signals_result = await db.execute(
            select(SignalEvent.signal_type, SignalEvent.value_num)
            .where(
                and_(
                    SignalEvent.player_id == ps.player_id,
                    SignalEvent.entity_type == EntityType.PLAYER,
                    SignalEvent.signal_type.in_([
                        SignalTypeEnum.MARKET_VALUE,
                        SignalTypeEnum.CONTRACT_MONTHS_REMAINING
                    ])
                )
            )
            .order_by(SignalEvent.effective_from.desc())
            .limit(2)
        )
        for sig_row in signals_result:
            if sig_row.signal_type == SignalTypeEnum.MARKET_VALUE:
                market_value = sig_row.value_num
            elif sig_row.signal_type == SignalTypeEnum.CONTRACT_MONTHS_REMAINING:
                contract_months = int(sig_row.value_num) if sig_row.value_num else None
        
        predictions.append(ProbabilityRow(
            player_id=ps.player_id,
            player_name=row.player_name,
            player_position=row.player_position,
            player_nationality=row.player_nationality,
            player_photo_url=row.player_photo_url,
            player_age=calculate_age(row.player_dob),
            from_club_id=ps.from_club_id,
            from_club_name=from_club_name,
            from_club_logo_url=from_club_logo,
            to_club_id=ps.to_club_id,
            to_club_name=to_club_name,
            to_club_logo_url=to_club_logo,
            horizon_days=ps.horizon_days,
            probability=ps.probability,
            drivers_json=ps.drivers_json,
            market_value=market_value,
            contract_months_remaining=contract_months,
            as_of=ps.as_of,
            window_end=ps.window_end
        ))
    
    return MarketLatestResponse(
        predictions=predictions,
        total=len(predictions),
        as_of=datetime.utcnow(),
        filters_applied={
            "competition_id": str(competition_id) if competition_id else None,
            "club_id": str(club_id) if club_id else None,
            "horizon_days": horizon_days,
            "min_probability": min_probability
        }
    )
