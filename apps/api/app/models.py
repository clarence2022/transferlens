"""
TransferLens Database Models
============================

Implements the four-layer architecture:
- Ledger Layer: Immutable completed transfers (transfer_events)
- Signals Layer: Time-stamped signals with provenance (signal_events)
- Market Layer: Probability snapshots and model outputs (prediction_snapshots)
- UX Layer: User events for weak signal derivation (user_events, watchlists)

All tables use time-travel correctness:
- observed_at: when the signal/event was observed in the real world
- effective_from/effective_to: when the fact was true
- created_at: when row was inserted into our database

Never overwrite historical data. Append-only patterns throughout.
"""

import enum
from datetime import datetime, date
from decimal import Decimal
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


# =============================================================================
# ENUMS
# =============================================================================

class EntityType(str, enum.Enum):
    """Types of entities that can have signals."""
    PLAYER = "player"
    CLUB = "club"
    CLUB_PLAYER_PAIR = "club_player_pair"


class SignalTypeEnum(str, enum.Enum):
    """Categories of signals tracked in the system."""
    # Performance signals
    MINUTES_LAST_5 = "minutes_last_5"
    INJURIES_STATUS = "injuries_status"
    GOALS_LAST_10 = "goals_last_10"
    ASSISTS_LAST_10 = "assists_last_10"
    
    # Club signals
    CLUB_LEAGUE_POSITION = "club_league_position"
    CLUB_POINTS_PER_GAME = "club_points_per_game"
    CLUB_NET_SPEND_12M = "club_net_spend_12m"
    
    # Contract/Finance signals
    CONTRACT_MONTHS_REMAINING = "contract_months_remaining"
    WAGE_ESTIMATE = "wage_estimate"
    MARKET_VALUE = "market_value"
    RELEASE_CLAUSE = "release_clause"
    
    # Social signals
    SOCIAL_MENTION_VELOCITY = "social_mention_velocity"
    SOCIAL_SENTIMENT = "social_sentiment"
    
    # User-derived signals (weak signals from UX layer)
    USER_ATTENTION_VELOCITY = "user_attention_velocity"
    USER_DESTINATION_COOCCURRENCE = "user_destination_cooccurrence"
    USER_WATCHLIST_ADDS = "user_watchlist_adds"


class TransferType(str, enum.Enum):
    """Types of transfers."""
    PERMANENT = "permanent"
    LOAN = "loan"
    LOAN_WITH_OPTION = "loan_with_option"
    LOAN_WITH_OBLIGATION = "loan_with_obligation"
    FREE_TRANSFER = "free_transfer"
    CONTRACT_EXPIRY = "contract_expiry"
    YOUTH_PROMOTION = "youth_promotion"
    RETIREMENT = "retirement"


class FeeType(str, enum.Enum):
    """How fee was reported."""
    CONFIRMED = "confirmed"
    REPORTED = "reported"
    ESTIMATED = "estimated"
    UNDISCLOSED = "undisclosed"
    FREE = "free"


class UserEventType(str, enum.Enum):
    """Types of user events tracked."""
    PAGE_VIEW = "page_view"
    PLAYER_VIEW = "player_view"
    CLUB_VIEW = "club_view"
    TRANSFER_VIEW = "transfer_view"
    PREDICTION_VIEW = "prediction_view"
    WATCHLIST_ADD = "watchlist_add"
    WATCHLIST_REMOVE = "watchlist_remove"
    SEARCH = "search"
    SHARE = "share"
    FILTER_APPLY = "filter_apply"
    COMPARISON_VIEW = "comparison_view"


class CorrectionType(str, enum.Enum):
    """Types of data corrections."""
    INSERT = "insert"
    UPDATE = "update"
    DELETE = "delete"
    MERGE = "merge"  # Merging duplicate entities


# =============================================================================
# CORE ENTITIES - Reference Data
# =============================================================================

class Competition(Base):
    """Football competition/league reference."""
    __tablename__ = "competitions"
    
    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    short_name: Mapped[Optional[str]] = mapped_column(String(50))
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    competition_type: Mapped[str] = mapped_column(String(50), default="league")  # league, cup, international
    tier: Mapped[int] = mapped_column(Integer, default=1)  # 1 = top flight
    
    # External IDs
    transfermarkt_id: Mapped[Optional[str]] = mapped_column(String(50))
    sofascore_id: Mapped[Optional[str]] = mapped_column(String(50))
    
    # Media
    logo_url: Mapped[Optional[str]] = mapped_column(String(500))
    
    # Metadata
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    clubs: Mapped[list["Club"]] = relationship(back_populates="competition")
    seasons: Mapped[list["Season"]] = relationship(back_populates="competition")
    
    __table_args__ = (
        UniqueConstraint("name", "country", name="uq_competition_name_country"),
        Index("ix_competitions_country", "country"),
    )


class Season(Base):
    """Season reference for a competition."""
    __tablename__ = "seasons"
    
    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    competition_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("competitions.id"), nullable=False)
    
    # Season identifier (e.g., "2024-25" or "2024")
    name: Mapped[str] = mapped_column(String(20), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    competition: Mapped["Competition"] = relationship(back_populates="seasons")
    
    __table_args__ = (
        UniqueConstraint("competition_id", "name", name="uq_season_competition_name"),
        Index("ix_seasons_competition", "competition_id"),
        Index("ix_seasons_current", "is_current"),
    )


class Club(Base):
    """Football club reference."""
    __tablename__ = "clubs"
    
    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    short_name: Mapped[Optional[str]] = mapped_column(String(50))
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    city: Mapped[Optional[str]] = mapped_column(String(100))
    
    # Current competition (can change between seasons)
    competition_id: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("competitions.id"))
    
    # Club details
    founded_year: Mapped[Optional[int]] = mapped_column(Integer)
    stadium: Mapped[Optional[str]] = mapped_column(String(255))
    stadium_capacity: Mapped[Optional[int]] = mapped_column(Integer)
    
    # External IDs
    transfermarkt_id: Mapped[Optional[str]] = mapped_column(String(50))
    sofascore_id: Mapped[Optional[str]] = mapped_column(String(50))
    
    # Media
    logo_url: Mapped[Optional[str]] = mapped_column(String(500))
    primary_color: Mapped[Optional[str]] = mapped_column(String(7))  # Hex color
    secondary_color: Mapped[Optional[str]] = mapped_column(String(7))
    
    # Metadata
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    competition: Mapped[Optional["Competition"]] = relationship(back_populates="clubs")
    players: Mapped[list["Player"]] = relationship(back_populates="current_club", foreign_keys="Player.current_club_id")
    
    __table_args__ = (
        Index("ix_clubs_name", "name"),
        Index("ix_clubs_country", "country"),
        Index("ix_clubs_competition", "competition_id"),
    )


class Player(Base):
    """Football player reference."""
    __tablename__ = "players"
    
    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Identity
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(500))
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date)
    
    # Nationality
    nationality: Mapped[Optional[str]] = mapped_column(String(100))
    secondary_nationality: Mapped[Optional[str]] = mapped_column(String(100))
    
    # Playing profile
    position: Mapped[Optional[str]] = mapped_column(String(50))  # GK, CB, LB, RB, CDM, CM, CAM, LW, RW, ST
    secondary_position: Mapped[Optional[str]] = mapped_column(String(50))
    foot: Mapped[Optional[str]] = mapped_column(String(10))  # left, right, both
    height_cm: Mapped[Optional[int]] = mapped_column(Integer)
    weight_kg: Mapped[Optional[int]] = mapped_column(Integer)
    
    # Current club (denormalized for fast queries)
    current_club_id: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("clubs.id"))
    shirt_number: Mapped[Optional[int]] = mapped_column(Integer)
    joined_club_date: Mapped[Optional[date]] = mapped_column(Date)
    contract_until: Mapped[Optional[date]] = mapped_column(Date)
    
    # External IDs for data linking
    transfermarkt_id: Mapped[Optional[str]] = mapped_column(String(50))
    sofascore_id: Mapped[Optional[str]] = mapped_column(String(50))
    fbref_id: Mapped[Optional[str]] = mapped_column(String(50))
    
    # Media
    photo_url: Mapped[Optional[str]] = mapped_column(String(500))
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)  # False if retired
    
    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    current_club: Mapped[Optional["Club"]] = relationship(back_populates="players", foreign_keys=[current_club_id])
    
    __table_args__ = (
        Index("ix_players_name", "name"),
        Index("ix_players_current_club", "current_club_id"),
        Index("ix_players_nationality", "nationality"),
        Index("ix_players_position", "position"),
        Index("ix_players_contract_until", "contract_until"),
    )


# =============================================================================
# LEDGER LAYER - Immutable Transfer Event Facts
# =============================================================================

class TransferEvent(Base):
    """
    Immutable transfer event ledger.
    
    This table is APPEND-ONLY. Completed transfers are facts.
    No rumors, no speculation - only confirmed moves.
    
    Corrections are handled via data_corrections table with full audit trail.
    """
    __tablename__ = "transfer_events"
    
    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Unique event identifier: TL-YYYYMMDD-PLAYERID-FROMCLUBID
    event_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    
    # Transfer parties
    player_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("players.id"), nullable=False)
    from_club_id: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("clubs.id"))  # Null for youth/unknown origin
    to_club_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clubs.id"), nullable=False)
    
    # Transfer type and date
    transfer_type: Mapped[TransferType] = mapped_column(Enum(TransferType), nullable=False)
    transfer_date: Mapped[date] = mapped_column(Date, nullable=False)
    announced_date: Mapped[Optional[date]] = mapped_column(Date)
    
    # Fee details
    fee_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2))
    fee_currency: Mapped[Optional[str]] = mapped_column(String(3), default="EUR")
    fee_amount_eur: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2))  # Normalized to EUR
    fee_type: Mapped[FeeType] = mapped_column(Enum(FeeType), default=FeeType.REPORTED)
    
    # Add-ons and bonuses
    add_ons_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2))
    add_ons_details: Mapped[Optional[str]] = mapped_column(Text)
    
    # Contract details
    contract_start: Mapped[Optional[date]] = mapped_column(Date)
    contract_end: Mapped[Optional[date]] = mapped_column(Date)
    contract_years: Mapped[Optional[Decimal]] = mapped_column(Numeric(3, 1))
    
    # Loan specifics
    loan_end_date: Mapped[Optional[date]] = mapped_column(Date)
    option_to_buy: Mapped[Optional[bool]] = mapped_column(Boolean)
    option_to_buy_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2))
    obligation_to_buy: Mapped[Optional[bool]] = mapped_column(Boolean)
    obligation_conditions: Mapped[Optional[str]] = mapped_column(Text)
    loan_fee: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2))
    
    # Sell-on clause
    sell_on_percent: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    sell_on_details: Mapped[Optional[str]] = mapped_column(Text)
    
    # Buy-back clause
    buy_back_clause: Mapped[Optional[bool]] = mapped_column(Boolean)
    buy_back_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2))
    buy_back_expiry: Mapped[Optional[date]] = mapped_column(Date)
    
    # Source and confidence
    source: Mapped[str] = mapped_column(String(255), nullable=False)  # e.g., "official", "transfermarkt", "fabrizio_romano"
    source_url: Mapped[Optional[str]] = mapped_column(String(1000))
    source_confidence: Mapped[Decimal] = mapped_column(Numeric(3, 2), default=Decimal("1.00"))  # 1.0 = official confirmation
    
    # Additional metadata
    notes: Mapped[Optional[str]] = mapped_column(Text)
    metadata: Mapped[Optional[dict]] = mapped_column(JSONB)
    
    # Audit fields (immutable row)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by: Mapped[Optional[str]] = mapped_column(String(100))  # System or admin user
    
    # Soft delete for corrections (row stays, but is_superseded = True)
    is_superseded: Mapped[bool] = mapped_column(Boolean, default=False)
    superseded_by: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("transfer_events.id"))
    superseded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Relationships
    player: Mapped["Player"] = relationship(foreign_keys=[player_id])
    from_club: Mapped[Optional["Club"]] = relationship(foreign_keys=[from_club_id])
    to_club: Mapped["Club"] = relationship(foreign_keys=[to_club_id])
    
    __table_args__ = (
        Index("ix_transfer_events_player", "player_id"),
        Index("ix_transfer_events_from_club", "from_club_id"),
        Index("ix_transfer_events_to_club", "to_club_id"),
        Index("ix_transfer_events_date", "transfer_date"),
        Index("ix_transfer_events_type", "transfer_type"),
        Index("ix_transfer_events_created_at", "created_at"),
        Index("ix_transfer_events_active", "is_superseded"),  # For filtering active records
        CheckConstraint(
            "source_confidence >= 0 AND source_confidence <= 1",
            name="ck_transfer_source_confidence_range"
        ),
        CheckConstraint(
            "sell_on_percent IS NULL OR (sell_on_percent >= 0 AND sell_on_percent <= 100)",
            name="ck_transfer_sell_on_percent_range"
        ),
    )


# =============================================================================
# SIGNALS LAYER - Time-Stamped Signal Events
# =============================================================================

class SignalEvent(Base):
    """
    Generic signal events table.
    
    Signals are NEVER overwritten. New signals are appended.
    This enables perfect time-travel queries.
    
    Supports three entity types:
    - player: signals about a specific player
    - club: signals about a specific club
    - club_player_pair: signals linking player to a potential club (e.g., rumor interest)
    """
    __tablename__ = "signal_events"
    
    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Entity identification
    entity_type: Mapped[EntityType] = mapped_column(Enum(EntityType), nullable=False)
    player_id: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("players.id"))
    club_id: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("clubs.id"))
    # For club_player_pair, both player_id and club_id are set
    
    # Signal classification
    signal_type: Mapped[SignalTypeEnum] = mapped_column(Enum(SignalTypeEnum), nullable=False)
    
    # Signal values (use appropriate field based on data type)
    value_json: Mapped[Optional[dict]] = mapped_column(JSONB)  # Complex structured data
    value_num: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 6))  # Numeric values
    value_text: Mapped[Optional[str]] = mapped_column(Text)  # Text values
    
    # Provenance
    source: Mapped[str] = mapped_column(String(255), nullable=False)  # e.g., "transfermarkt", "sofascore", "twitter_api"
    source_id: Mapped[Optional[str]] = mapped_column(String(255))  # ID in source system
    confidence: Mapped[Decimal] = mapped_column(Numeric(3, 2), default=Decimal("1.00"))  # 0.00 to 1.00
    
    # Time-travel correctness
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)  # When signal was observed in real world
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)  # When signal became true
    effective_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))  # When signal stopped being true (null = still true)
    
    # Audit
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Optional metadata
    metadata: Mapped[Optional[dict]] = mapped_column(JSONB)
    
    __table_args__ = (
        # Efficient as-of queries
        Index("ix_signal_events_player_type_effective", "player_id", "signal_type", "effective_from"),
        Index("ix_signal_events_club_type_effective", "club_id", "signal_type", "effective_from"),
        Index("ix_signal_events_effective_from", "effective_from"),
        Index("ix_signal_events_observed_at", "observed_at"),
        Index("ix_signal_events_created_at", "created_at"),
        Index("ix_signal_events_entity_type", "entity_type"),
        Index("ix_signal_events_signal_type", "signal_type"),
        
        # Composite for as-of time-travel
        Index("ix_signal_events_player_asof", "player_id", "signal_type", "effective_from", "effective_to"),
        Index("ix_signal_events_club_asof", "club_id", "signal_type", "effective_from", "effective_to"),
        
        # Entity validation
        CheckConstraint(
            """
            (entity_type = 'player' AND player_id IS NOT NULL AND club_id IS NULL) OR
            (entity_type = 'club' AND club_id IS NOT NULL AND player_id IS NULL) OR
            (entity_type = 'club_player_pair' AND player_id IS NOT NULL AND club_id IS NOT NULL)
            """,
            name="ck_signal_entity_consistency"
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_signal_confidence_range"
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_to > effective_from",
            name="ck_signal_effective_range"
        ),
    )


# =============================================================================
# MARKET LAYER - Model Outputs and Predictions
# =============================================================================

class PredictionSnapshot(Base):
    """
    Probability snapshots from prediction models.
    
    Each snapshot represents a point-in-time probability estimate
    for a potential transfer. Snapshots are NEVER overwritten;
    new snapshots are appended with updated as_of times.
    
    Supports multiple prediction horizons (30/90/180 days).
    """
    __tablename__ = "prediction_snapshots"
    
    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Unique snapshot identifier
    snapshot_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    
    # Model information
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # Prediction target
    player_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("players.id"), nullable=False)
    from_club_id: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("clubs.id"))  # Current club at prediction time
    to_club_id: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("clubs.id"))  # Specific destination, or null for "any move"
    
    # Prediction horizon
    horizon_days: Mapped[int] = mapped_column(Integer, nullable=False)  # 30, 90, 180, etc.
    
    # Probability score
    probability: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)  # 0.0000 to 1.0000
    
    # Explanation drivers (what contributed to this prediction)
    drivers_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # Example: {"contract_months_remaining": 0.35, "market_value_trend": 0.20, "social_velocity": 0.15}
    
    # Feature snapshot (for model reproducibility)
    features_json: Mapped[Optional[dict]] = mapped_column(JSONB)
    
    # As-of timestamp (prediction based on signals up to this time)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
    # Prediction window
    window_start: Mapped[date] = mapped_column(Date, nullable=False)
    window_end: Mapped[date] = mapped_column(Date, nullable=False)
    
    # Audit
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    player: Mapped["Player"] = relationship(foreign_keys=[player_id])
    from_club: Mapped[Optional["Club"]] = relationship(foreign_keys=[from_club_id])
    to_club: Mapped[Optional["Club"]] = relationship(foreign_keys=[to_club_id])
    
    __table_args__ = (
        Index("ix_prediction_snapshots_player", "player_id"),
        Index("ix_prediction_snapshots_player_as_of", "player_id", "as_of"),
        Index("ix_prediction_snapshots_player_horizon", "player_id", "horizon_days"),
        Index("ix_prediction_snapshots_to_club", "to_club_id"),
        Index("ix_prediction_snapshots_probability", "probability"),
        Index("ix_prediction_snapshots_as_of", "as_of"),
        Index("ix_prediction_snapshots_horizon", "horizon_days"),
        Index("ix_prediction_snapshots_created_at", "created_at"),
        
        # For player market view (latest predictions)
        Index("ix_prediction_snapshots_latest", "player_id", "to_club_id", "horizon_days", "as_of"),
        
        CheckConstraint(
            "probability >= 0 AND probability <= 1",
            name="ck_prediction_probability_range"
        ),
        CheckConstraint(
            "horizon_days > 0",
            name="ck_prediction_horizon_positive"
        ),
        CheckConstraint(
            "window_end > window_start",
            name="ck_prediction_window_valid"
        ),
    )


# =============================================================================
# UX LAYER - User Events for Weak Signal Derivation
# =============================================================================

class UserEvent(Base):
    """
    User behavior event log.
    
    Tracks user interactions for:
    - Analytics and product improvement
    - Deriving weak signals (e.g., sudden interest in a player)
    
    These are aggregated into user_derived signals by the worker.
    Privacy-first: only anonymous IDs, no PII.
    """
    __tablename__ = "user_events"
    
    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Anonymous user tracking (no PII)
    user_anon_id: Mapped[str] = mapped_column(String(100), nullable=False)  # Persistent anonymous ID
    session_id: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # Event details
    event_type: Mapped[UserEventType] = mapped_column(Enum(UserEventType), nullable=False)
    event_props_json: Mapped[Optional[dict]] = mapped_column(JSONB)
    # Example: {"page_url": "/players/123", "search_query": "Mbappe", "referrer": "twitter"}
    
    # What did they interact with? (optional - depends on event type)
    player_id: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("players.id"))
    club_id: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("clubs.id"))
    
    # Timing
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
    # Technical context (for analytics, not user tracking)
    device_type: Mapped[Optional[str]] = mapped_column(String(20))  # mobile, tablet, desktop
    country_code: Mapped[Optional[str]] = mapped_column(String(2))  # ISO country code
    
    __table_args__ = (
        Index("ix_user_events_type", "event_type"),
        Index("ix_user_events_player", "player_id"),
        Index("ix_user_events_club", "club_id"),
        Index("ix_user_events_occurred_at", "occurred_at"),
        Index("ix_user_events_session", "session_id"),
        Index("ix_user_events_user_anon", "user_anon_id"),
        
        # For aggregating signals
        Index("ix_user_events_player_time", "player_id", "event_type", "occurred_at"),
        Index("ix_user_events_club_time", "club_id", "event_type", "occurred_at"),
    )


# =============================================================================
# USER FEATURES - Watchlists
# =============================================================================

class Watchlist(Base):
    """User watchlist container."""
    __tablename__ = "watchlists"
    
    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # User identification (stub for now - magic link auth later)
    user_id: Mapped[str] = mapped_column(String(100), nullable=False)  # Anonymous or authenticated user ID
    
    # Watchlist metadata
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="My Watchlist")
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Sharing
    share_token: Mapped[Optional[str]] = mapped_column(String(100), unique=True)  # For shareable links
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    items: Mapped[list["WatchlistItem"]] = relationship(back_populates="watchlist", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("ix_watchlists_user", "user_id"),
        Index("ix_watchlists_share_token", "share_token"),
    )


class WatchlistItem(Base):
    """Item in a user's watchlist."""
    __tablename__ = "watchlist_items"
    
    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    
    watchlist_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("watchlists.id", ondelete="CASCADE"), nullable=False)
    player_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("players.id"), nullable=False)
    
    # Optional notes
    notes: Mapped[Optional[str]] = mapped_column(Text)
    
    # Alert preferences
    alert_on_transfer: Mapped[bool] = mapped_column(Boolean, default=True)
    alert_on_probability_change: Mapped[bool] = mapped_column(Boolean, default=True)
    probability_threshold: Mapped[Optional[Decimal]] = mapped_column(Numeric(3, 2))  # Alert if prob goes above this
    
    # Timestamps
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    watchlist: Mapped["Watchlist"] = relationship(back_populates="items")
    player: Mapped["Player"] = relationship()
    
    __table_args__ = (
        UniqueConstraint("watchlist_id", "player_id", name="uq_watchlist_item_player"),
        Index("ix_watchlist_items_watchlist", "watchlist_id"),
        Index("ix_watchlist_items_player", "player_id"),
    )


# =============================================================================
# AUDIT - Data Corrections
# =============================================================================

class DataCorrection(Base):
    """
    Audit table for any manual data corrections.
    
    When data needs to be corrected (e.g., wrong transfer fee),
    the original row is NOT modified. Instead:
    1. A correction record is created here
    2. The original row is marked is_superseded=True (for transfer_events)
    3. A new row with correct data is inserted
    """
    __tablename__ = "data_corrections"
    
    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # What was corrected
    table_name: Mapped[str] = mapped_column(String(100), nullable=False)
    record_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    
    # Correction details
    correction_type: Mapped[CorrectionType] = mapped_column(Enum(CorrectionType), nullable=False)
    field_name: Mapped[Optional[str]] = mapped_column(String(100))  # Specific field corrected
    old_value: Mapped[Optional[dict]] = mapped_column(JSONB)  # Previous value(s)
    new_value: Mapped[Optional[dict]] = mapped_column(JSONB)  # Corrected value(s)
    
    # New record reference (if correction created a new row)
    new_record_id: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True))
    
    # Reason and source
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[Optional[str]] = mapped_column(String(255))  # Source of correct information
    source_url: Mapped[Optional[str]] = mapped_column(String(1000))
    
    # Who made the correction
    corrected_by: Mapped[str] = mapped_column(String(100), nullable=False)
    corrected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Review status
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(100))
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    __table_args__ = (
        Index("ix_data_corrections_table_record", "table_name", "record_id"),
        Index("ix_data_corrections_corrected_at", "corrected_at"),
    )
