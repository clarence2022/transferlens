"""
Database Models for Worker
==========================

Mirrors the API models for database operations.
Also includes the ModelVersion table for tracking trained models.
"""

import enum
from datetime import datetime, date
from decimal import Decimal
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean, CheckConstraint, Date, DateTime, Enum, ForeignKey,
    Index, Integer, Numeric, String, Text, UniqueConstraint, text,
    Column, Table, MetaData
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


# =============================================================================
# ENUMS (must match API models)
# =============================================================================

class EntityType(str, enum.Enum):
    PLAYER = "player"
    CLUB = "club"
    CLUB_PLAYER_PAIR = "club_player_pair"


class SignalTypeEnum(str, enum.Enum):
    MINUTES_LAST_5 = "minutes_last_5"
    INJURIES_STATUS = "injuries_status"
    GOALS_LAST_10 = "goals_last_10"
    ASSISTS_LAST_10 = "assists_last_10"
    CLUB_LEAGUE_POSITION = "club_league_position"
    CLUB_POINTS_PER_GAME = "club_points_per_game"
    CLUB_NET_SPEND_12M = "club_net_spend_12m"
    CONTRACT_MONTHS_REMAINING = "contract_months_remaining"
    WAGE_ESTIMATE = "wage_estimate"
    MARKET_VALUE = "market_value"
    RELEASE_CLAUSE = "release_clause"
    SOCIAL_MENTION_VELOCITY = "social_mention_velocity"
    SOCIAL_SENTIMENT = "social_sentiment"
    USER_ATTENTION_VELOCITY = "user_attention_velocity"
    USER_DESTINATION_COOCCURRENCE = "user_destination_cooccurrence"
    USER_WATCHLIST_ADDS = "user_watchlist_adds"


class TransferType(str, enum.Enum):
    PERMANENT = "permanent"
    LOAN = "loan"
    LOAN_WITH_OPTION = "loan_with_option"
    LOAN_WITH_OBLIGATION = "loan_with_obligation"
    FREE_TRANSFER = "free_transfer"
    CONTRACT_EXPIRY = "contract_expiry"
    YOUTH_PROMOTION = "youth_promotion"
    RETIREMENT = "retirement"


class FeeType(str, enum.Enum):
    CONFIRMED = "confirmed"
    REPORTED = "reported"
    ESTIMATED = "estimated"
    UNDISCLOSED = "undisclosed"
    FREE = "free"


class UserEventType(str, enum.Enum):
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


class ModelStatus(str, enum.Enum):
    """Model training status."""
    TRAINING = "training"
    COMPLETED = "completed"
    FAILED = "failed"
    DEPLOYED = "deployed"
    ARCHIVED = "archived"


# =============================================================================
# MODEL VERSION TABLE (New for worker)
# =============================================================================

class ModelVersion(Base):
    """
    Tracks trained model versions and their metadata.
    
    Used to:
    - Store model artifacts location
    - Track training parameters
    - Record performance metrics
    - Manage model deployment
    """
    __tablename__ = "model_versions"
    
    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Model identification
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # Training parameters
    horizon_days: Mapped[int] = mapped_column(Integer, nullable=False)
    training_as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
    # Training data info
    training_samples: Mapped[int] = mapped_column(Integer, nullable=False)
    positive_samples: Mapped[int] = mapped_column(Integer, nullable=False)
    negative_samples: Mapped[int] = mapped_column(Integer, nullable=False)
    feature_count: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Feature list
    features_used: Mapped[Optional[dict]] = mapped_column(JSONB)  # List of feature names
    
    # Performance metrics
    metrics: Mapped[Optional[dict]] = mapped_column(JSONB)
    # Example: {"accuracy": 0.85, "precision": 0.72, "recall": 0.68, "auc_roc": 0.88}
    
    # Feature importances
    feature_importances: Mapped[Optional[dict]] = mapped_column(JSONB)
    # Example: {"contract_months_remaining": 0.25, "market_value": 0.18, ...}
    
    # Model artifact
    artifact_path: Mapped[Optional[str]] = mapped_column(String(500))
    
    # Status
    status: Mapped[ModelStatus] = mapped_column(
        Enum(ModelStatus), 
        nullable=False, 
        default=ModelStatus.TRAINING
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    deployed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Error info (if failed)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    
    __table_args__ = (
        UniqueConstraint("model_name", "model_version", name="uq_model_name_version"),
        Index("ix_model_versions_name", "model_name"),
        Index("ix_model_versions_status", "status"),
        Index("ix_model_versions_horizon", "horizon_days"),
        Index("ix_model_versions_created_at", "created_at"),
    )


# =============================================================================
# FEATURE TABLE (for caching built features)
# =============================================================================

class FeatureSnapshot(Base):
    """
    Cached feature vectors for (player, candidate_club) pairs.
    
    Built by features:build job, consumed by predict:run.
    Allows for point-in-time feature reconstruction.
    """
    __tablename__ = "feature_snapshots"
    
    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Identifiers
    player_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    candidate_club_id: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True))
    
    # Time context
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
    # Feature vector
    features: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # Example: {"contract_months_remaining": 18, "market_value": 100000000, ...}
    
    # Metadata
    feature_version: Mapped[str] = mapped_column(String(50), default="v1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        nullable=False
    )
    
    __table_args__ = (
        Index("ix_feature_snapshots_player_as_of", "player_id", "as_of"),
        Index("ix_feature_snapshots_as_of", "as_of"),
        UniqueConstraint(
            "player_id", "candidate_club_id", "as_of", 
            name="uq_feature_snapshot_player_club_asof"
        ),
    )
