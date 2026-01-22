"""
Events Router
=============

User event ingestion for the UX layer.
"""

from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models import UserEvent
from app.schemas import UserEventCreate, UserEventResponse

router = APIRouter(prefix="/events", tags=["Events"])


@router.post("/user", response_model=UserEventResponse, status_code=status.HTTP_201_CREATED)
async def create_user_event(
    event: UserEventCreate,
    db: AsyncSession = Depends(get_db)
) -> UserEventResponse:
    """
    Record a user event for analytics and weak signal derivation.
    
    Events are used to:
    - Track user behavior for product analytics
    - Derive weak signals (e.g., "user attention velocity" spikes)
    - Identify trending players and clubs
    
    **Event types:**
    - `page_view` - User viewed a page
    - `player_view` - User viewed a player profile
    - `club_view` - User viewed a club profile
    - `transfer_view` - User viewed a transfer
    - `prediction_view` - User viewed a prediction
    - `watchlist_add` - User added to watchlist
    - `watchlist_remove` - User removed from watchlist
    - `search` - User performed a search
    - `share` - User shared content
    - `filter_apply` - User applied filters
    - `comparison_view` - User compared players/clubs
    
    **Example request:**
    ```json
    {
        "user_anon_id": "anon_abc123",
        "session_id": "sess_xyz789",
        "event_type": "player_view",
        "player_id": "uuid-here",
        "event_props_json": {
            "page_url": "/players/uuid-here",
            "referrer": "search"
        }
    }
    ```
    """
    # Create the event
    db_event = UserEvent(
        id=uuid4(),
        user_anon_id=event.user_anon_id,
        session_id=event.session_id,
        event_type=event.event_type,
        event_props_json=event.event_props_json,
        player_id=event.player_id,
        club_id=event.club_id,
        occurred_at=event.occurred_at or datetime.utcnow(),
        device_type=event.device_type,
        country_code=event.country_code
    )
    
    db.add(db_event)
    
    try:
        await db.commit()
        await db.refresh(db_event)
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record event: {str(e)}"
        )
    
    return UserEventResponse(
        success=True,
        event_id=db_event.id
    )
