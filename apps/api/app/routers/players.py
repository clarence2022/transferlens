"""
Players Router
==============

Player-related endpoints including:
- Player detail with signals and predictions
- Signal history with time-travel
- Prediction history
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.dependencies import get_db
from app.models import (
    Player, Club, SignalEvent, PredictionSnapshot, TransferEvent,
    SignalTypeEnum, EntityType
)
from app.schemas import (
    PlayerDetail, PlayerBrief, ClubBrief, SignalDelta,
    SignalEventRead, SignalTimeSeries, PredictionBrief, TransferBrief,
    PaginatedResponse
)
from app.services import get_what_changed, get_latest_player_signals, calculate_age
from app.config import settings

router = APIRouter(prefix="/players", tags=["Players"])


@router.get("/{player_id}", response_model=PlayerDetail)
async def get_player(
    player_id: UUID,
    db: AsyncSession = Depends(get_db)
) -> PlayerDetail:
    """
    Get detailed player information.
    
    Returns:
    - Basic player profile
    - Current club info
    - Key stats (latest signals)
    - Latest transfer predictions
    - "What Changed" - significant signal changes in last 7 days
    - Transfer history
    
    **Performance target: <200ms locally**
    """
    # Fetch player with current club in single query
    stmt = (
        select(Player)
        .options(selectinload(Player.current_club))
        .where(Player.id == player_id)
    )
    result = await db.execute(stmt)
    player = result.scalar_one_or_none()
    
    if not player:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Player {player_id} not found"
        )
    
    # Get latest signals (optimized query)
    latest_signals = await get_latest_player_signals(db, player_id)
    
    # Get latest predictions (limit 5 destinations)
    predictions_stmt = (
        select(PredictionSnapshot, Club.name.label("to_club_name"))
        .outerjoin(Club, PredictionSnapshot.to_club_id == Club.id)
        .where(PredictionSnapshot.player_id == player_id)
        .order_by(PredictionSnapshot.as_of.desc())
        .distinct(PredictionSnapshot.to_club_id, PredictionSnapshot.horizon_days)
        .limit(10)
    )
    pred_result = await db.execute(predictions_stmt)
    predictions_rows = pred_result.all()
    
    latest_predictions = [
        PredictionBrief(
            id=row.PredictionSnapshot.id,
            to_club_id=row.PredictionSnapshot.to_club_id,
            to_club_name=row.to_club_name,
            horizon_days=row.PredictionSnapshot.horizon_days,
            probability=row.PredictionSnapshot.probability,
            drivers_json=row.PredictionSnapshot.drivers_json,
            as_of=row.PredictionSnapshot.as_of,
            window_end=row.PredictionSnapshot.window_end
        )
        for row in predictions_rows
    ]
    
    # Get what changed (last 7 days)
    what_changed = await get_what_changed(db, player_id, days=7)
    
    # Get transfer history (last 10)
    transfers_stmt = (
        select(
            TransferEvent,
            Player.name.label("player_name"),
            Club.name.label("from_club_name"),
        )
        .join(Player, TransferEvent.player_id == Player.id)
        .outerjoin(Club, TransferEvent.from_club_id == Club.id)
        .where(
            and_(
                TransferEvent.player_id == player_id,
                TransferEvent.is_superseded == False
            )
        )
        .order_by(TransferEvent.transfer_date.desc())
        .limit(10)
    )
    transfers_result = await db.execute(transfers_stmt)
    
    # Need to get to_club separately
    transfers_data = []
    for row in transfers_result:
        to_club_stmt = select(Club.name).where(Club.id == row.TransferEvent.to_club_id)
        to_club_result = await db.execute(to_club_stmt)
        to_club_name = to_club_result.scalar_one_or_none()
        
        transfers_data.append(TransferBrief(
            id=row.TransferEvent.id,
            event_id=row.TransferEvent.event_id,
            player_id=row.TransferEvent.player_id,
            player_name=row.player_name,
            from_club_id=row.TransferEvent.from_club_id,
            from_club_name=row.from_club_name,
            to_club_id=row.TransferEvent.to_club_id,
            to_club_name=to_club_name,
            transfer_type=row.TransferEvent.transfer_type,
            transfer_date=row.TransferEvent.transfer_date,
            fee_amount_eur=row.TransferEvent.fee_amount_eur
        ))
    
    # Build response
    current_club = None
    if player.current_club:
        current_club = ClubBrief(
            id=player.current_club.id,
            name=player.current_club.name,
            short_name=player.current_club.short_name,
            country=player.current_club.country,
            logo_url=player.current_club.logo_url
        )
    
    return PlayerDetail(
        id=player.id,
        name=player.name,
        full_name=player.full_name,
        date_of_birth=player.date_of_birth,
        nationality=player.nationality,
        secondary_nationality=player.secondary_nationality,
        position=player.position,
        secondary_position=player.secondary_position,
        foot=player.foot,
        height_cm=player.height_cm,
        weight_kg=player.weight_kg,
        photo_url=player.photo_url,
        current_club_id=player.current_club_id,
        shirt_number=player.shirt_number,
        contract_until=player.contract_until,
        is_active=player.is_active,
        created_at=player.created_at,
        current_club=current_club,
        age=calculate_age(player.date_of_birth),
        # Key stats from latest signals
        market_value=latest_signals.get(SignalTypeEnum.MARKET_VALUE),
        contract_months_remaining=int(latest_signals.get(SignalTypeEnum.CONTRACT_MONTHS_REMAINING, 0)) if latest_signals.get(SignalTypeEnum.CONTRACT_MONTHS_REMAINING) else None,
        wage_estimate=latest_signals.get(SignalTypeEnum.WAGE_ESTIMATE),
        goals_last_10=int(latest_signals.get(SignalTypeEnum.GOALS_LAST_10, 0)) if latest_signals.get(SignalTypeEnum.GOALS_LAST_10) else None,
        assists_last_10=int(latest_signals.get(SignalTypeEnum.ASSISTS_LAST_10, 0)) if latest_signals.get(SignalTypeEnum.ASSISTS_LAST_10) else None,
        minutes_last_5=int(latest_signals.get(SignalTypeEnum.MINUTES_LAST_5, 0)) if latest_signals.get(SignalTypeEnum.MINUTES_LAST_5) else None,
        latest_predictions=latest_predictions,
        what_changed=what_changed,
        transfer_history=transfers_data
    )


@router.get("/{player_id}/signals", response_model=List[SignalEventRead])
async def get_player_signals(
    player_id: UUID,
    as_of: Optional[datetime] = Query(None, description="Time-travel: get signals as of this timestamp"),
    signal_type: Optional[SignalTypeEnum] = Query(None, description="Filter by signal type"),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db)
) -> List[SignalEventRead]:
    """
    Get signal history for a player.
    
    Supports time-travel queries via `as_of` parameter.
    
    **Examples:**
    - `/players/{id}/signals` - All recent signals
    - `/players/{id}/signals?as_of=2025-01-01T00:00:00Z` - Signals as of Jan 1
    - `/players/{id}/signals?signal_type=market_value` - Only market value signals
    """
    # Verify player exists
    player_check = await db.execute(select(Player.id).where(Player.id == player_id))
    if not player_check.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Player {player_id} not found"
        )
    
    # Build query
    conditions = [
        SignalEvent.player_id == player_id,
        SignalEvent.entity_type == EntityType.PLAYER
    ]
    
    if as_of:
        conditions.append(SignalEvent.effective_from <= as_of)
    
    if signal_type:
        conditions.append(SignalEvent.signal_type == signal_type)
    
    stmt = (
        select(SignalEvent)
        .where(and_(*conditions))
        .order_by(SignalEvent.effective_from.desc())
        .limit(limit)
    )
    
    result = await db.execute(stmt)
    signals = result.scalars().all()
    
    return [
        SignalEventRead(
            id=s.id,
            entity_type=s.entity_type,
            player_id=s.player_id,
            club_id=s.club_id,
            signal_type=s.signal_type,
            value_json=s.value_json,
            value_num=s.value_num,
            value_text=s.value_text,
            source=s.source,
            source_id=s.source_id,
            confidence=s.confidence,
            observed_at=s.observed_at,
            effective_from=s.effective_from,
            effective_to=s.effective_to,
            created_at=s.created_at
        )
        for s in signals
    ]


@router.get("/{player_id}/predictions", response_model=List[PredictionBrief])
async def get_player_predictions(
    player_id: UUID,
    as_of: Optional[datetime] = Query(None, description="Time-travel: get predictions as of this timestamp"),
    horizon_days: Optional[int] = Query(None, description="Filter by prediction horizon (30, 90, 180)"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db)
) -> List[PredictionBrief]:
    """
    Get prediction history for a player.
    
    Supports time-travel queries via `as_of` parameter.
    
    **Examples:**
    - `/players/{id}/predictions` - All recent predictions
    - `/players/{id}/predictions?as_of=2025-01-01T00:00:00Z` - Predictions as of Jan 1
    - `/players/{id}/predictions?horizon_days=90` - Only 90-day horizon predictions
    """
    # Verify player exists
    player_check = await db.execute(select(Player.id).where(Player.id == player_id))
    if not player_check.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Player {player_id} not found"
        )
    
    # Build query
    conditions = [PredictionSnapshot.player_id == player_id]
    
    if as_of:
        conditions.append(PredictionSnapshot.as_of <= as_of)
    
    if horizon_days:
        conditions.append(PredictionSnapshot.horizon_days == horizon_days)
    
    stmt = (
        select(PredictionSnapshot, Club.name.label("to_club_name"))
        .outerjoin(Club, PredictionSnapshot.to_club_id == Club.id)
        .where(and_(*conditions))
        .order_by(PredictionSnapshot.as_of.desc())
        .limit(limit)
    )
    
    result = await db.execute(stmt)
    
    return [
        PredictionBrief(
            id=row.PredictionSnapshot.id,
            to_club_id=row.PredictionSnapshot.to_club_id,
            to_club_name=row.to_club_name,
            horizon_days=row.PredictionSnapshot.horizon_days,
            probability=row.PredictionSnapshot.probability,
            drivers_json=row.PredictionSnapshot.drivers_json,
            as_of=row.PredictionSnapshot.as_of,
            window_end=row.PredictionSnapshot.window_end
        )
        for row in result
    ]
