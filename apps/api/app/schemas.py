"""
TransferLens API Schemas
========================

Pydantic schemas for request/response validation.
Matches the four-layer architecture:
- Core entities (Competition, Club, Player)
- Ledger (TransferEvent)
- Signals (SignalEvent)
- Market (PredictionSnapshot)
- UX (UserEvent, Watchlist)
"""

from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Dict, Any, Generic, TypeVar
from uuid import UUID
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict

from app.models import (
    EntityType, SignalTypeEnum, TransferType, FeeType, 
    UserEventType, CorrectionType
)


# =============================================================================
# GENERIC TYPES
# =============================================================================

T = TypeVar('T')


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard paginated response wrapper."""
    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int
    
    @classmethod
    def create(cls, items: List[T], total: int, page: int, page_size: int):
        total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )


# =============================================================================
# BASE SCHEMAS
# =============================================================================

class BaseSchema(BaseModel):
    """Base schema with common configuration."""
    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# HEALTH & STATUS
# =============================================================================

class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    timestamp: datetime
    database: str
    redis: str
    environment: str


class ReadyResponse(BaseModel):
    """Readiness probe response."""
    ready: bool
    checks: Dict[str, bool]


# =============================================================================
# COMPETITION SCHEMAS
# =============================================================================

class CompetitionBase(BaseModel):
    name: str
    short_name: Optional[str] = None
    country: str
    competition_type: str = "league"
    tier: int = 1
    logo_url: Optional[str] = None


class CompetitionRead(CompetitionBase, BaseSchema):
    id: UUID
    is_active: bool
    created_at: datetime


class CompetitionBrief(BaseSchema):
    """Minimal competition info."""
    id: UUID
    name: str
    short_name: Optional[str] = None
    country: str


# =============================================================================
# CLUB SCHEMAS
# =============================================================================

class ClubBase(BaseModel):
    name: str
    short_name: Optional[str] = None
    country: str
    city: Optional[str] = None
    stadium: Optional[str] = None
    stadium_capacity: Optional[int] = None
    founded_year: Optional[int] = None
    logo_url: Optional[str] = None
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None


class ClubCreate(ClubBase):
    competition_id: Optional[UUID] = None


class ClubRead(ClubBase, BaseSchema):
    id: UUID
    competition_id: Optional[UUID] = None
    is_active: bool
    created_at: datetime


class ClubBrief(BaseSchema):
    """Minimal club info for lists and references."""
    id: UUID
    name: str
    short_name: Optional[str] = None
    country: str
    logo_url: Optional[str] = None


class ClubDetail(ClubRead):
    """Full club detail with squad and probabilities."""
    competition: Optional[CompetitionBrief] = None
    squad: List["PlayerBrief"] = []
    squad_count: int = 0
    outgoing_probabilities: List["ProbabilityRow"] = []
    incoming_probabilities: List["ProbabilityRow"] = []
    recent_transfers_in: List["TransferBrief"] = []
    recent_transfers_out: List["TransferBrief"] = []


# =============================================================================
# PLAYER SCHEMAS
# =============================================================================

class PlayerBase(BaseModel):
    name: str
    full_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    nationality: Optional[str] = None
    secondary_nationality: Optional[str] = None
    position: Optional[str] = None
    secondary_position: Optional[str] = None
    foot: Optional[str] = None
    height_cm: Optional[int] = None
    weight_kg: Optional[int] = None
    photo_url: Optional[str] = None


class PlayerCreate(PlayerBase):
    current_club_id: Optional[UUID] = None
    shirt_number: Optional[int] = None
    contract_until: Optional[date] = None


class PlayerRead(PlayerBase, BaseSchema):
    id: UUID
    current_club_id: Optional[UUID] = None
    shirt_number: Optional[int] = None
    contract_until: Optional[date] = None
    is_active: bool
    created_at: datetime


class PlayerBrief(BaseSchema):
    """Minimal player info for lists."""
    id: UUID
    name: str
    position: Optional[str] = None
    nationality: Optional[str] = None
    photo_url: Optional[str] = None
    current_club_id: Optional[UUID] = None


class PlayerWithClub(PlayerBrief):
    """Player with current club info."""
    current_club: Optional[ClubBrief] = None
    age: Optional[int] = None
    contract_until: Optional[date] = None


class SignalDelta(BaseModel):
    """A change in a signal value."""
    signal_type: SignalTypeEnum
    description: str
    old_value: Optional[Any] = None
    new_value: Optional[Any] = None
    change_percent: Optional[float] = None
    severity: str = "info"  # info, warning, alert
    observed_at: datetime


class PlayerDetail(PlayerRead):
    """Full player detail for player page."""
    current_club: Optional[ClubBrief] = None
    age: Optional[int] = None
    
    # Key stats (latest signals)
    market_value: Optional[Decimal] = None
    contract_months_remaining: Optional[int] = None
    wage_estimate: Optional[Decimal] = None
    goals_last_10: Optional[int] = None
    assists_last_10: Optional[int] = None
    minutes_last_5: Optional[int] = None
    
    # Latest predictions
    latest_predictions: List["PredictionBrief"] = []
    
    # What changed (last 7 days)
    what_changed: List[SignalDelta] = []
    
    # Transfer history
    transfer_history: List["TransferBrief"] = []


# =============================================================================
# SEARCH SCHEMAS
# =============================================================================

class SearchResultType(str, Enum):
    PLAYER = "player"
    CLUB = "club"


class SearchResult(BaseModel):
    """Single search result."""
    type: SearchResultType
    id: UUID
    name: str
    subtitle: Optional[str] = None  # e.g., "ST • Norway" or "Premier League • England"
    image_url: Optional[str] = None
    score: float = 0.0


class SearchResponse(BaseModel):
    """Search response with ranked results."""
    query: str
    results: List[SearchResult]
    total: int


# =============================================================================
# TRANSFER EVENT SCHEMAS (Ledger Layer)
# =============================================================================

class TransferEventBase(BaseModel):
    player_id: UUID
    from_club_id: Optional[UUID] = None
    to_club_id: UUID
    transfer_type: TransferType
    transfer_date: date
    announced_date: Optional[date] = None
    fee_amount: Optional[Decimal] = None
    fee_currency: str = "EUR"
    fee_type: FeeType = FeeType.REPORTED
    add_ons_amount: Optional[Decimal] = None
    contract_start: Optional[date] = None
    contract_end: Optional[date] = None
    loan_end_date: Optional[date] = None
    option_to_buy: Optional[bool] = None
    option_to_buy_amount: Optional[Decimal] = None
    sell_on_percent: Optional[Decimal] = None
    source: str
    source_url: Optional[str] = None
    source_confidence: Decimal = Decimal("1.00")
    notes: Optional[str] = None


class TransferEventCreate(TransferEventBase):
    """Create a new transfer event."""
    metadata: Optional[Dict[str, Any]] = None


class TransferEventRead(TransferEventBase, BaseSchema):
    id: UUID
    event_id: str
    fee_amount_eur: Optional[Decimal] = None
    is_superseded: bool
    created_at: datetime


class TransferBrief(BaseSchema):
    """Brief transfer for lists."""
    id: UUID
    event_id: str
    player_id: UUID
    player_name: Optional[str] = None
    from_club_id: Optional[UUID] = None
    from_club_name: Optional[str] = None
    to_club_id: UUID
    to_club_name: Optional[str] = None
    transfer_type: TransferType
    transfer_date: date
    fee_amount_eur: Optional[Decimal] = None


class TransferDetail(TransferEventRead):
    """Full transfer with relationships."""
    player: PlayerBrief
    from_club: Optional[ClubBrief] = None
    to_club: ClubBrief


# =============================================================================
# SIGNAL EVENT SCHEMAS (Signals Layer)
# =============================================================================

class SignalEventBase(BaseModel):
    entity_type: EntityType
    player_id: Optional[UUID] = None
    club_id: Optional[UUID] = None
    signal_type: SignalTypeEnum
    value_json: Optional[Dict[str, Any]] = None
    value_num: Optional[Decimal] = None
    value_text: Optional[str] = None
    source: str
    source_id: Optional[str] = None
    confidence: Decimal = Decimal("1.00")
    observed_at: datetime
    effective_from: datetime
    effective_to: Optional[datetime] = None


class SignalEventCreate(SignalEventBase):
    """Create a new signal event."""
    metadata: Optional[Dict[str, Any]] = None


class SignalEventRead(SignalEventBase, BaseSchema):
    id: UUID
    created_at: datetime


class SignalLatest(BaseModel):
    """Latest signal value for a type."""
    signal_type: SignalTypeEnum
    value: Any  # Could be numeric, text, or json
    source: str
    confidence: Decimal
    observed_at: datetime
    effective_from: datetime


class SignalTimeSeries(BaseModel):
    """Signal values over time for charting."""
    signal_type: SignalTypeEnum
    data_points: List[Dict[str, Any]]  # [{effective_from: ..., value: ..., source: ...}, ...]


# =============================================================================
# PREDICTION SNAPSHOT SCHEMAS (Market Layer)
# =============================================================================

class PredictionSnapshotBase(BaseModel):
    player_id: UUID
    from_club_id: Optional[UUID] = None
    to_club_id: Optional[UUID] = None
    horizon_days: int
    probability: Decimal = Field(ge=0, le=1)
    model_version: str
    model_name: str
    drivers_json: Dict[str, float]
    as_of: datetime
    window_start: date
    window_end: date


class PredictionSnapshotCreate(PredictionSnapshotBase):
    """Create a new prediction snapshot."""
    features_json: Optional[Dict[str, Any]] = None


class PredictionSnapshotRead(PredictionSnapshotBase, BaseSchema):
    id: UUID
    snapshot_id: str
    created_at: datetime


class PredictionBrief(BaseModel):
    """Brief prediction for player page."""
    id: UUID
    to_club_id: Optional[UUID] = None
    to_club_name: Optional[str] = None
    horizon_days: int
    probability: Decimal
    drivers_json: Dict[str, float]
    as_of: datetime
    window_end: date


class ProbabilityRow(BaseModel):
    """Row in the probability table (market/latest)."""
    player_id: UUID
    player_name: str
    player_position: Optional[str] = None
    player_nationality: Optional[str] = None
    player_photo_url: Optional[str] = None
    player_age: Optional[int] = None
    
    from_club_id: Optional[UUID] = None
    from_club_name: Optional[str] = None
    from_club_logo_url: Optional[str] = None
    
    to_club_id: Optional[UUID] = None
    to_club_name: Optional[str] = None
    to_club_logo_url: Optional[str] = None
    
    horizon_days: int
    probability: Decimal
    drivers_json: Dict[str, float]
    
    market_value: Optional[Decimal] = None
    contract_months_remaining: Optional[int] = None
    
    as_of: datetime
    window_end: date


class MarketLatestResponse(BaseModel):
    """Response for /market/latest endpoint."""
    predictions: List[ProbabilityRow]
    total: int
    as_of: datetime
    filters_applied: Dict[str, Any]


# =============================================================================
# USER EVENT SCHEMAS (UX Layer)
# =============================================================================

class UserEventCreate(BaseModel):
    """Create a user event."""
    user_anon_id: str
    session_id: str
    event_type: UserEventType
    event_props_json: Optional[Dict[str, Any]] = None
    player_id: Optional[UUID] = None
    club_id: Optional[UUID] = None
    occurred_at: Optional[datetime] = None  # Defaults to now
    device_type: Optional[str] = None
    country_code: Optional[str] = None


class UserEventRead(BaseSchema):
    id: UUID
    user_anon_id: str
    session_id: str
    event_type: UserEventType
    player_id: Optional[UUID] = None
    club_id: Optional[UUID] = None
    occurred_at: datetime


class UserEventResponse(BaseModel):
    """Response after creating user event."""
    success: bool
    event_id: UUID


# =============================================================================
# ADMIN SCHEMAS
# =============================================================================

class AdminResponse(BaseModel):
    """Generic admin operation response."""
    success: bool
    message: str
    details: Optional[Dict[str, Any]] = None


class MaterializedViewRefreshResponse(BaseModel):
    """Response for materialized view refresh."""
    success: bool
    views_refreshed: List[str]
    duration_ms: int


# =============================================================================
# ERROR SCHEMAS
# =============================================================================

class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    message: str
    details: Optional[Dict[str, Any]] = None


class ValidationErrorDetail(BaseModel):
    """Validation error detail."""
    loc: List[str]
    msg: str
    type: str


class ValidationErrorResponse(BaseModel):
    """Validation error response."""
    error: str = "validation_error"
    message: str = "Request validation failed"
    details: List[ValidationErrorDetail]


# =============================================================================
# FORWARD REFERENCES
# =============================================================================

# Rebuild models that have forward references
ClubDetail.model_rebuild()
PlayerDetail.model_rebuild()
