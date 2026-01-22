"""
Admin Router
============

Admin-only endpoints for data management.
Protected by API key authentication.
"""

import time
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_admin_api_key
from app.models import TransferEvent, SignalEvent, EntityType
from app.schemas import (
    TransferEventCreate, TransferEventRead,
    SignalEventCreate, SignalEventRead,
    AdminResponse, MaterializedViewRefreshResponse
)

router = APIRouter(prefix="/admin", tags=["Admin"])


def generate_event_id(transfer_date, player_id, from_club_id) -> str:
    """Generate unique event ID: TL-YYYYMMDD-PLAYERID-FROMCLUBID"""
    date_str = transfer_date.strftime("%Y%m%d")
    player_short = str(player_id)[:8]
    from_short = str(from_club_id)[:8] if from_club_id else "ORIGIN"
    return f"TL-{date_str}-{player_short}-{from_short}"


def generate_snapshot_id(player_id, to_club_id, horizon, as_of) -> str:
    """Generate unique snapshot ID"""
    player_short = str(player_id)[:8]
    to_short = str(to_club_id)[:8] if to_club_id else "ANY"
    ts = as_of.strftime("%Y%m%d%H%M%S")
    return f"SNAP-{player_short}-{to_short}-H{horizon}-{ts}"


@router.post(
    "/transfer_events",
    response_model=TransferEventRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(get_admin_api_key)]
)
async def create_transfer_event(
    transfer: TransferEventCreate,
    db: AsyncSession = Depends(get_db)
) -> TransferEventRead:
    """
    Create a new transfer event in the ledger.
    
    **Requires API key authentication** via `X-API-Key` header.
    
    Transfer events are immutable once created. Corrections should be
    made by marking the original as superseded and creating a new event.
    
    **Example request:**
    ```json
    {
        "player_id": "uuid",
        "from_club_id": "uuid",
        "to_club_id": "uuid",
        "transfer_type": "permanent",
        "transfer_date": "2025-01-15",
        "fee_amount": 50000000,
        "fee_currency": "EUR",
        "fee_type": "confirmed",
        "contract_start": "2025-01-15",
        "contract_end": "2029-06-30",
        "source": "official",
        "source_confidence": 1.0
    }
    ```
    """
    # Generate event ID
    event_id = generate_event_id(
        transfer.transfer_date,
        transfer.player_id,
        transfer.from_club_id
    )
    
    # Check for duplicate
    existing = await db.execute(
        text("SELECT id FROM transfer_events WHERE event_id = :event_id"),
        {"event_id": event_id}
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Transfer event {event_id} already exists"
        )
    
    # Create the transfer event
    db_transfer = TransferEvent(
        id=uuid4(),
        event_id=event_id,
        player_id=transfer.player_id,
        from_club_id=transfer.from_club_id,
        to_club_id=transfer.to_club_id,
        transfer_type=transfer.transfer_type,
        transfer_date=transfer.transfer_date,
        announced_date=transfer.announced_date,
        fee_amount=transfer.fee_amount,
        fee_currency=transfer.fee_currency,
        fee_amount_eur=transfer.fee_amount,  # Assume EUR for now
        fee_type=transfer.fee_type,
        add_ons_amount=transfer.add_ons_amount,
        contract_start=transfer.contract_start,
        contract_end=transfer.contract_end,
        loan_end_date=transfer.loan_end_date,
        option_to_buy=transfer.option_to_buy,
        option_to_buy_amount=transfer.option_to_buy_amount,
        sell_on_percent=transfer.sell_on_percent,
        source=transfer.source,
        source_url=transfer.source_url,
        source_confidence=transfer.source_confidence,
        notes=transfer.notes,
        metadata=transfer.metadata,
        is_superseded=False
    )
    
    db.add(db_transfer)
    
    try:
        await db.commit()
        await db.refresh(db_transfer)
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create transfer event: {str(e)}"
        )
    
    return TransferEventRead(
        id=db_transfer.id,
        event_id=db_transfer.event_id,
        player_id=db_transfer.player_id,
        from_club_id=db_transfer.from_club_id,
        to_club_id=db_transfer.to_club_id,
        transfer_type=db_transfer.transfer_type,
        transfer_date=db_transfer.transfer_date,
        announced_date=db_transfer.announced_date,
        fee_amount=db_transfer.fee_amount,
        fee_currency=db_transfer.fee_currency,
        fee_amount_eur=db_transfer.fee_amount_eur,
        fee_type=db_transfer.fee_type,
        add_ons_amount=db_transfer.add_ons_amount,
        contract_start=db_transfer.contract_start,
        contract_end=db_transfer.contract_end,
        loan_end_date=db_transfer.loan_end_date,
        option_to_buy=db_transfer.option_to_buy,
        option_to_buy_amount=db_transfer.option_to_buy_amount,
        sell_on_percent=db_transfer.sell_on_percent,
        source=db_transfer.source,
        source_url=db_transfer.source_url,
        source_confidence=db_transfer.source_confidence,
        notes=db_transfer.notes,
        is_superseded=db_transfer.is_superseded,
        created_at=db_transfer.created_at
    )


@router.post(
    "/signal_events",
    response_model=SignalEventRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(get_admin_api_key)]
)
async def create_signal_event(
    signal: SignalEventCreate,
    db: AsyncSession = Depends(get_db)
) -> SignalEventRead:
    """
    Create a new signal event.
    
    **Requires API key authentication** via `X-API-Key` header.
    
    Signals are append-only. New values create new rows; old values are never modified.
    
    **Entity types:**
    - `player` - Signal about a player (requires player_id)
    - `club` - Signal about a club (requires club_id)
    - `club_player_pair` - Signal linking player and club (requires both)
    
    **Example request:**
    ```json
    {
        "entity_type": "player",
        "player_id": "uuid",
        "signal_type": "market_value",
        "value_num": 100000000,
        "source": "transfermarkt",
        "confidence": 0.95,
        "observed_at": "2025-01-15T10:00:00Z",
        "effective_from": "2025-01-15T00:00:00Z"
    }
    ```
    """
    # Validate entity type consistency
    if signal.entity_type == EntityType.PLAYER:
        if not signal.player_id or signal.club_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Entity type 'player' requires player_id and no club_id"
            )
    elif signal.entity_type == EntityType.CLUB:
        if not signal.club_id or signal.player_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Entity type 'club' requires club_id and no player_id"
            )
    elif signal.entity_type == EntityType.CLUB_PLAYER_PAIR:
        if not signal.player_id or not signal.club_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Entity type 'club_player_pair' requires both player_id and club_id"
            )
    
    # Create the signal event
    db_signal = SignalEvent(
        id=uuid4(),
        entity_type=signal.entity_type,
        player_id=signal.player_id,
        club_id=signal.club_id,
        signal_type=signal.signal_type,
        value_json=signal.value_json,
        value_num=signal.value_num,
        value_text=signal.value_text,
        source=signal.source,
        source_id=signal.source_id,
        confidence=signal.confidence,
        observed_at=signal.observed_at,
        effective_from=signal.effective_from,
        effective_to=signal.effective_to,
        metadata=signal.metadata
    )
    
    db.add(db_signal)
    
    try:
        await db.commit()
        await db.refresh(db_signal)
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create signal event: {str(e)}"
        )
    
    return SignalEventRead(
        id=db_signal.id,
        entity_type=db_signal.entity_type,
        player_id=db_signal.player_id,
        club_id=db_signal.club_id,
        signal_type=db_signal.signal_type,
        value_json=db_signal.value_json,
        value_num=db_signal.value_num,
        value_text=db_signal.value_text,
        source=db_signal.source,
        source_id=db_signal.source_id,
        confidence=db_signal.confidence,
        observed_at=db_signal.observed_at,
        effective_from=db_signal.effective_from,
        effective_to=db_signal.effective_to,
        created_at=db_signal.created_at
    )


@router.post(
    "/rebuild/materialized",
    response_model=MaterializedViewRefreshResponse,
    dependencies=[Depends(get_admin_api_key)]
)
async def refresh_materialized_views(
    db: AsyncSession = Depends(get_db)
) -> MaterializedViewRefreshResponse:
    """
    Refresh all materialized views.
    
    **Requires API key authentication** via `X-API-Key` header.
    
    This refreshes the `player_market_view` materialized view which
    provides fast reads for the probability table.
    
    **Note:** This can take several seconds for large datasets.
    Consider running during low-traffic periods.
    """
    start_time = time.time()
    views_refreshed = []
    
    try:
        # Refresh player_market_view
        await db.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY player_market_view"))
        views_refreshed.append("player_market_view")
        await db.commit()
    except Exception as e:
        await db.rollback()
        # View might not exist or not have unique index for concurrent refresh
        try:
            await db.execute(text("REFRESH MATERIALIZED VIEW player_market_view"))
            views_refreshed.append("player_market_view")
            await db.commit()
        except Exception as e2:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to refresh materialized views: {str(e2)}"
            )
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    return MaterializedViewRefreshResponse(
        success=True,
        views_refreshed=views_refreshed,
        duration_ms=duration_ms
    )
