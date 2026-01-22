"""
Clubs Router
============

Club-related endpoints including:
- Club detail with squad and probabilities
- Squad listing
- Transfer activity
"""

from datetime import datetime, timedelta
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.dependencies import get_db
from app.models import (
    Club, Competition, Player, TransferEvent, PredictionSnapshot,
    SignalEvent, SignalTypeEnum, EntityType
)
from app.schemas import (
    ClubDetail, ClubBrief, CompetitionBrief, PlayerBrief,
    ProbabilityRow, TransferBrief
)
from app.services import calculate_age

router = APIRouter(prefix="/clubs", tags=["Clubs"])


@router.get("/{club_id}", response_model=ClubDetail)
async def get_club(
    club_id: UUID,
    db: AsyncSession = Depends(get_db)
) -> ClubDetail:
    """
    Get detailed club information.
    
    Returns:
    - Basic club profile
    - Competition info
    - Current squad
    - Outgoing transfer probabilities (players likely to leave)
    - Incoming transfer probabilities (players likely to join)
    - Recent transfers in/out
    """
    # Fetch club with competition
    stmt = (
        select(Club)
        .options(selectinload(Club.competition))
        .where(Club.id == club_id)
    )
    result = await db.execute(stmt)
    club = result.scalar_one_or_none()
    
    if not club:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Club {club_id} not found"
        )
    
    # Get squad (players with this club as current)
    squad_stmt = (
        select(Player)
        .where(
            and_(
                Player.current_club_id == club_id,
                Player.is_active == True
            )
        )
        .order_by(Player.position, Player.name)
    )
    squad_result = await db.execute(squad_stmt)
    squad_players = squad_result.scalars().all()
    
    squad = [
        PlayerBrief(
            id=p.id,
            name=p.name,
            position=p.position,
            nationality=p.nationality,
            photo_url=p.photo_url,
            current_club_id=p.current_club_id
        )
        for p in squad_players
    ]
    
    # Get outgoing probabilities (players at this club with high transfer probability)
    outgoing_stmt = (
        select(
            PredictionSnapshot,
            Player.name.label("player_name"),
            Player.position.label("player_position"),
            Player.nationality.label("player_nationality"),
            Player.photo_url.label("player_photo_url"),
            Player.date_of_birth.label("player_dob"),
            Club.name.label("to_club_name"),
            Club.logo_url.label("to_club_logo_url")
        )
        .join(Player, PredictionSnapshot.player_id == Player.id)
        .outerjoin(Club, PredictionSnapshot.to_club_id == Club.id)
        .where(PredictionSnapshot.from_club_id == club_id)
        .order_by(PredictionSnapshot.probability.desc())
        .limit(10)
    )
    outgoing_result = await db.execute(outgoing_stmt)
    
    outgoing_probabilities = []
    for row in outgoing_result:
        outgoing_probabilities.append(ProbabilityRow(
            player_id=row.PredictionSnapshot.player_id,
            player_name=row.player_name,
            player_position=row.player_position,
            player_nationality=row.player_nationality,
            player_photo_url=row.player_photo_url,
            player_age=calculate_age(row.player_dob),
            from_club_id=club_id,
            from_club_name=club.name,
            from_club_logo_url=club.logo_url,
            to_club_id=row.PredictionSnapshot.to_club_id,
            to_club_name=row.to_club_name,
            to_club_logo_url=row.to_club_logo_url,
            horizon_days=row.PredictionSnapshot.horizon_days,
            probability=row.PredictionSnapshot.probability,
            drivers_json=row.PredictionSnapshot.drivers_json,
            market_value=None,  # Could fetch from signals
            contract_months_remaining=None,
            as_of=row.PredictionSnapshot.as_of,
            window_end=row.PredictionSnapshot.window_end
        ))
    
    # Get incoming probabilities (predictions where to_club is this club)
    incoming_stmt = (
        select(
            PredictionSnapshot,
            Player.name.label("player_name"),
            Player.position.label("player_position"),
            Player.nationality.label("player_nationality"),
            Player.photo_url.label("player_photo_url"),
            Player.date_of_birth.label("player_dob"),
            Club.name.label("from_club_name"),
            Club.logo_url.label("from_club_logo_url")
        )
        .join(Player, PredictionSnapshot.player_id == Player.id)
        .outerjoin(Club, PredictionSnapshot.from_club_id == Club.id)
        .where(PredictionSnapshot.to_club_id == club_id)
        .order_by(PredictionSnapshot.probability.desc())
        .limit(10)
    )
    incoming_result = await db.execute(incoming_stmt)
    
    incoming_probabilities = []
    for row in incoming_result:
        incoming_probabilities.append(ProbabilityRow(
            player_id=row.PredictionSnapshot.player_id,
            player_name=row.player_name,
            player_position=row.player_position,
            player_nationality=row.player_nationality,
            player_photo_url=row.player_photo_url,
            player_age=calculate_age(row.player_dob),
            from_club_id=row.PredictionSnapshot.from_club_id,
            from_club_name=row.from_club_name,
            from_club_logo_url=row.from_club_logo_url,
            to_club_id=club_id,
            to_club_name=club.name,
            to_club_logo_url=club.logo_url,
            horizon_days=row.PredictionSnapshot.horizon_days,
            probability=row.PredictionSnapshot.probability,
            drivers_json=row.PredictionSnapshot.drivers_json,
            market_value=None,
            contract_months_remaining=None,
            as_of=row.PredictionSnapshot.as_of,
            window_end=row.PredictionSnapshot.window_end
        ))
    
    # Get recent transfers in (last year)
    one_year_ago = datetime.utcnow().date() - timedelta(days=365)
    
    transfers_in_stmt = (
        select(TransferEvent, Player.name.label("player_name"), Club.name.label("from_club_name"))
        .join(Player, TransferEvent.player_id == Player.id)
        .outerjoin(Club, TransferEvent.from_club_id == Club.id)
        .where(
            and_(
                TransferEvent.to_club_id == club_id,
                TransferEvent.is_superseded == False,
                TransferEvent.transfer_date >= one_year_ago
            )
        )
        .order_by(TransferEvent.transfer_date.desc())
        .limit(10)
    )
    transfers_in_result = await db.execute(transfers_in_stmt)
    
    recent_transfers_in = [
        TransferBrief(
            id=row.TransferEvent.id,
            event_id=row.TransferEvent.event_id,
            player_id=row.TransferEvent.player_id,
            player_name=row.player_name,
            from_club_id=row.TransferEvent.from_club_id,
            from_club_name=row.from_club_name,
            to_club_id=row.TransferEvent.to_club_id,
            to_club_name=club.name,
            transfer_type=row.TransferEvent.transfer_type,
            transfer_date=row.TransferEvent.transfer_date,
            fee_amount_eur=row.TransferEvent.fee_amount_eur
        )
        for row in transfers_in_result
    ]
    
    # Get recent transfers out
    transfers_out_stmt = (
        select(TransferEvent, Player.name.label("player_name"), Club.name.label("to_club_name"))
        .join(Player, TransferEvent.player_id == Player.id)
        .join(Club, TransferEvent.to_club_id == Club.id)
        .where(
            and_(
                TransferEvent.from_club_id == club_id,
                TransferEvent.is_superseded == False,
                TransferEvent.transfer_date >= one_year_ago
            )
        )
        .order_by(TransferEvent.transfer_date.desc())
        .limit(10)
    )
    transfers_out_result = await db.execute(transfers_out_stmt)
    
    recent_transfers_out = [
        TransferBrief(
            id=row.TransferEvent.id,
            event_id=row.TransferEvent.event_id,
            player_id=row.TransferEvent.player_id,
            player_name=row.player_name,
            from_club_id=row.TransferEvent.from_club_id,
            from_club_name=club.name,
            to_club_id=row.TransferEvent.to_club_id,
            to_club_name=row.to_club_name,
            transfer_type=row.TransferEvent.transfer_type,
            transfer_date=row.TransferEvent.transfer_date,
            fee_amount_eur=row.TransferEvent.fee_amount_eur
        )
        for row in transfers_out_result
    ]
    
    # Build competition info
    competition = None
    if club.competition:
        competition = CompetitionBrief(
            id=club.competition.id,
            name=club.competition.name,
            short_name=club.competition.short_name,
            country=club.competition.country
        )
    
    return ClubDetail(
        id=club.id,
        name=club.name,
        short_name=club.short_name,
        country=club.country,
        city=club.city,
        stadium=club.stadium,
        stadium_capacity=club.stadium_capacity,
        founded_year=club.founded_year,
        logo_url=club.logo_url,
        primary_color=club.primary_color,
        secondary_color=club.secondary_color,
        competition_id=club.competition_id,
        is_active=club.is_active,
        created_at=club.created_at,
        competition=competition,
        squad=squad,
        squad_count=len(squad),
        outgoing_probabilities=outgoing_probabilities,
        incoming_probabilities=incoming_probabilities,
        recent_transfers_in=recent_transfers_in,
        recent_transfers_out=recent_transfers_out
    )
