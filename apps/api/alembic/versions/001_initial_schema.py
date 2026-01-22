"""Initial schema with all four layers

Revision ID: 001_initial_schema
Revises: 
Create Date: 2025-01-21

TransferLens Database Schema
============================

Core entities: competitions, seasons, clubs, players
Ledger layer: transfer_events (immutable)
Signals layer: signal_events (append-only)
Market layer: prediction_snapshots (append-only)
UX layer: user_events, watchlists, watchlist_items
Audit: data_corrections

Plus: player_market_view materialized view for fast reads
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enums first
    entity_type_enum = postgresql.ENUM('player', 'club', 'club_player_pair', name='entitytype', create_type=False)
    entity_type_enum.create(op.get_bind(), checkfirst=True)
    
    signal_type_enum = postgresql.ENUM(
        'minutes_last_5', 'injuries_status', 'goals_last_10', 'assists_last_10',
        'club_league_position', 'club_points_per_game', 'club_net_spend_12m',
        'contract_months_remaining', 'wage_estimate', 'market_value', 'release_clause',
        'social_mention_velocity', 'social_sentiment',
        'user_attention_velocity', 'user_destination_cooccurrence', 'user_watchlist_adds',
        name='signaltypeenum', create_type=False
    )
    signal_type_enum.create(op.get_bind(), checkfirst=True)
    
    transfer_type_enum = postgresql.ENUM(
        'permanent', 'loan', 'loan_with_option', 'loan_with_obligation',
        'free_transfer', 'contract_expiry', 'youth_promotion', 'retirement',
        name='transfertype', create_type=False
    )
    transfer_type_enum.create(op.get_bind(), checkfirst=True)
    
    fee_type_enum = postgresql.ENUM(
        'confirmed', 'reported', 'estimated', 'undisclosed', 'free',
        name='feetype', create_type=False
    )
    fee_type_enum.create(op.get_bind(), checkfirst=True)
    
    user_event_type_enum = postgresql.ENUM(
        'page_view', 'player_view', 'club_view', 'transfer_view', 'prediction_view',
        'watchlist_add', 'watchlist_remove', 'search', 'share', 'filter_apply', 'comparison_view',
        name='usereventtype', create_type=False
    )
    user_event_type_enum.create(op.get_bind(), checkfirst=True)
    
    correction_type_enum = postgresql.ENUM(
        'insert', 'update', 'delete', 'merge',
        name='correctiontype', create_type=False
    )
    correction_type_enum.create(op.get_bind(), checkfirst=True)

    # =========================================================================
    # CORE ENTITIES
    # =========================================================================
    
    # Competitions table
    op.create_table(
        'competitions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('short_name', sa.String(50), nullable=True),
        sa.Column('country', sa.String(100), nullable=False),
        sa.Column('competition_type', sa.String(50), nullable=False, server_default='league'),
        sa.Column('tier', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('transfermarkt_id', sa.String(50), nullable=True),
        sa.Column('sofascore_id', sa.String(50), nullable=True),
        sa.Column('logo_url', sa.String(500), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', 'country', name='uq_competition_name_country')
    )
    op.create_index('ix_competitions_country', 'competitions', ['country'])
    
    # Seasons table
    op.create_table(
        'seasons',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('competition_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(20), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('is_current', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['competition_id'], ['competitions.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('competition_id', 'name', name='uq_season_competition_name')
    )
    op.create_index('ix_seasons_competition', 'seasons', ['competition_id'])
    op.create_index('ix_seasons_current', 'seasons', ['is_current'])
    
    # Clubs table
    op.create_table(
        'clubs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('short_name', sa.String(50), nullable=True),
        sa.Column('country', sa.String(100), nullable=False),
        sa.Column('city', sa.String(100), nullable=True),
        sa.Column('competition_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('founded_year', sa.Integer(), nullable=True),
        sa.Column('stadium', sa.String(255), nullable=True),
        sa.Column('stadium_capacity', sa.Integer(), nullable=True),
        sa.Column('transfermarkt_id', sa.String(50), nullable=True),
        sa.Column('sofascore_id', sa.String(50), nullable=True),
        sa.Column('logo_url', sa.String(500), nullable=True),
        sa.Column('primary_color', sa.String(7), nullable=True),
        sa.Column('secondary_color', sa.String(7), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['competition_id'], ['competitions.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_clubs_name', 'clubs', ['name'])
    op.create_index('ix_clubs_country', 'clubs', ['country'])
    op.create_index('ix_clubs_competition', 'clubs', ['competition_id'])
    
    # Players table
    op.create_table(
        'players',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(500), nullable=True),
        sa.Column('date_of_birth', sa.Date(), nullable=True),
        sa.Column('nationality', sa.String(100), nullable=True),
        sa.Column('secondary_nationality', sa.String(100), nullable=True),
        sa.Column('position', sa.String(50), nullable=True),
        sa.Column('secondary_position', sa.String(50), nullable=True),
        sa.Column('foot', sa.String(10), nullable=True),
        sa.Column('height_cm', sa.Integer(), nullable=True),
        sa.Column('weight_kg', sa.Integer(), nullable=True),
        sa.Column('current_club_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('shirt_number', sa.Integer(), nullable=True),
        sa.Column('joined_club_date', sa.Date(), nullable=True),
        sa.Column('contract_until', sa.Date(), nullable=True),
        sa.Column('transfermarkt_id', sa.String(50), nullable=True),
        sa.Column('sofascore_id', sa.String(50), nullable=True),
        sa.Column('fbref_id', sa.String(50), nullable=True),
        sa.Column('photo_url', sa.String(500), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['current_club_id'], ['clubs.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_players_name', 'players', ['name'])
    op.create_index('ix_players_current_club', 'players', ['current_club_id'])
    op.create_index('ix_players_nationality', 'players', ['nationality'])
    op.create_index('ix_players_position', 'players', ['position'])
    op.create_index('ix_players_contract_until', 'players', ['contract_until'])
    
    # =========================================================================
    # LEDGER LAYER - Transfer Events
    # =========================================================================
    
    op.create_table(
        'transfer_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('event_id', sa.String(100), nullable=False),
        sa.Column('player_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('from_club_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('to_club_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('transfer_type', sa.Enum('permanent', 'loan', 'loan_with_option', 'loan_with_obligation',
                                          'free_transfer', 'contract_expiry', 'youth_promotion', 'retirement',
                                          name='transfertype'), nullable=False),
        sa.Column('transfer_date', sa.Date(), nullable=False),
        sa.Column('announced_date', sa.Date(), nullable=True),
        sa.Column('fee_amount', sa.Numeric(15, 2), nullable=True),
        sa.Column('fee_currency', sa.String(3), nullable=True, server_default='EUR'),
        sa.Column('fee_amount_eur', sa.Numeric(15, 2), nullable=True),
        sa.Column('fee_type', sa.Enum('confirmed', 'reported', 'estimated', 'undisclosed', 'free',
                                      name='feetype'), nullable=False, server_default='reported'),
        sa.Column('add_ons_amount', sa.Numeric(15, 2), nullable=True),
        sa.Column('add_ons_details', sa.Text(), nullable=True),
        sa.Column('contract_start', sa.Date(), nullable=True),
        sa.Column('contract_end', sa.Date(), nullable=True),
        sa.Column('contract_years', sa.Numeric(3, 1), nullable=True),
        sa.Column('loan_end_date', sa.Date(), nullable=True),
        sa.Column('option_to_buy', sa.Boolean(), nullable=True),
        sa.Column('option_to_buy_amount', sa.Numeric(15, 2), nullable=True),
        sa.Column('obligation_to_buy', sa.Boolean(), nullable=True),
        sa.Column('obligation_conditions', sa.Text(), nullable=True),
        sa.Column('loan_fee', sa.Numeric(15, 2), nullable=True),
        sa.Column('sell_on_percent', sa.Numeric(5, 2), nullable=True),
        sa.Column('sell_on_details', sa.Text(), nullable=True),
        sa.Column('buy_back_clause', sa.Boolean(), nullable=True),
        sa.Column('buy_back_amount', sa.Numeric(15, 2), nullable=True),
        sa.Column('buy_back_expiry', sa.Date(), nullable=True),
        sa.Column('source', sa.String(255), nullable=False),
        sa.Column('source_url', sa.String(1000), nullable=True),
        sa.Column('source_confidence', sa.Numeric(3, 2), nullable=False, server_default='1.00'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.String(100), nullable=True),
        sa.Column('is_superseded', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('superseded_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('superseded_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['player_id'], ['players.id']),
        sa.ForeignKeyConstraint(['from_club_id'], ['clubs.id']),
        sa.ForeignKeyConstraint(['to_club_id'], ['clubs.id']),
        sa.ForeignKeyConstraint(['superseded_by'], ['transfer_events.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('event_id'),
        sa.CheckConstraint('source_confidence >= 0 AND source_confidence <= 1', name='ck_transfer_source_confidence_range'),
        sa.CheckConstraint('sell_on_percent IS NULL OR (sell_on_percent >= 0 AND sell_on_percent <= 100)', name='ck_transfer_sell_on_percent_range')
    )
    op.create_index('ix_transfer_events_player', 'transfer_events', ['player_id'])
    op.create_index('ix_transfer_events_from_club', 'transfer_events', ['from_club_id'])
    op.create_index('ix_transfer_events_to_club', 'transfer_events', ['to_club_id'])
    op.create_index('ix_transfer_events_date', 'transfer_events', ['transfer_date'])
    op.create_index('ix_transfer_events_type', 'transfer_events', ['transfer_type'])
    op.create_index('ix_transfer_events_created_at', 'transfer_events', ['created_at'])
    op.create_index('ix_transfer_events_active', 'transfer_events', ['is_superseded'])
    
    # =========================================================================
    # SIGNALS LAYER - Signal Events
    # =========================================================================
    
    op.create_table(
        'signal_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('entity_type', sa.Enum('player', 'club', 'club_player_pair', name='entitytype'), nullable=False),
        sa.Column('player_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('club_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('signal_type', sa.Enum(
            'minutes_last_5', 'injuries_status', 'goals_last_10', 'assists_last_10',
            'club_league_position', 'club_points_per_game', 'club_net_spend_12m',
            'contract_months_remaining', 'wage_estimate', 'market_value', 'release_clause',
            'social_mention_velocity', 'social_sentiment',
            'user_attention_velocity', 'user_destination_cooccurrence', 'user_watchlist_adds',
            name='signaltypeenum'
        ), nullable=False),
        sa.Column('value_json', postgresql.JSONB(), nullable=True),
        sa.Column('value_num', sa.Numeric(20, 6), nullable=True),
        sa.Column('value_text', sa.Text(), nullable=True),
        sa.Column('source', sa.String(255), nullable=False),
        sa.Column('source_id', sa.String(255), nullable=True),
        sa.Column('confidence', sa.Numeric(3, 2), nullable=False, server_default='1.00'),
        sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('effective_from', sa.DateTime(timezone=True), nullable=False),
        sa.Column('effective_to', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('metadata', postgresql.JSONB(), nullable=True),
        sa.ForeignKeyConstraint(['player_id'], ['players.id']),
        sa.ForeignKeyConstraint(['club_id'], ['clubs.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            """
            (entity_type = 'player' AND player_id IS NOT NULL AND club_id IS NULL) OR
            (entity_type = 'club' AND club_id IS NOT NULL AND player_id IS NULL) OR
            (entity_type = 'club_player_pair' AND player_id IS NOT NULL AND club_id IS NOT NULL)
            """,
            name='ck_signal_entity_consistency'
        ),
        sa.CheckConstraint('confidence >= 0 AND confidence <= 1', name='ck_signal_confidence_range'),
        sa.CheckConstraint('effective_to IS NULL OR effective_to > effective_from', name='ck_signal_effective_range')
    )
    op.create_index('ix_signal_events_player_type_effective', 'signal_events', ['player_id', 'signal_type', 'effective_from'])
    op.create_index('ix_signal_events_club_type_effective', 'signal_events', ['club_id', 'signal_type', 'effective_from'])
    op.create_index('ix_signal_events_effective_from', 'signal_events', ['effective_from'])
    op.create_index('ix_signal_events_observed_at', 'signal_events', ['observed_at'])
    op.create_index('ix_signal_events_created_at', 'signal_events', ['created_at'])
    op.create_index('ix_signal_events_entity_type', 'signal_events', ['entity_type'])
    op.create_index('ix_signal_events_signal_type', 'signal_events', ['signal_type'])
    op.create_index('ix_signal_events_player_asof', 'signal_events', ['player_id', 'signal_type', 'effective_from', 'effective_to'])
    op.create_index('ix_signal_events_club_asof', 'signal_events', ['club_id', 'signal_type', 'effective_from', 'effective_to'])
    
    # =========================================================================
    # MARKET LAYER - Prediction Snapshots
    # =========================================================================
    
    op.create_table(
        'prediction_snapshots',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('snapshot_id', sa.String(100), nullable=False),
        sa.Column('model_version', sa.String(50), nullable=False),
        sa.Column('model_name', sa.String(100), nullable=False),
        sa.Column('player_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('from_club_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('to_club_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('horizon_days', sa.Integer(), nullable=False),
        sa.Column('probability', sa.Numeric(5, 4), nullable=False),
        sa.Column('drivers_json', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('features_json', postgresql.JSONB(), nullable=True),
        sa.Column('as_of', sa.DateTime(timezone=True), nullable=False),
        sa.Column('window_start', sa.Date(), nullable=False),
        sa.Column('window_end', sa.Date(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['player_id'], ['players.id']),
        sa.ForeignKeyConstraint(['from_club_id'], ['clubs.id']),
        sa.ForeignKeyConstraint(['to_club_id'], ['clubs.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('snapshot_id'),
        sa.CheckConstraint('probability >= 0 AND probability <= 1', name='ck_prediction_probability_range'),
        sa.CheckConstraint('horizon_days > 0', name='ck_prediction_horizon_positive'),
        sa.CheckConstraint('window_end > window_start', name='ck_prediction_window_valid')
    )
    op.create_index('ix_prediction_snapshots_player', 'prediction_snapshots', ['player_id'])
    op.create_index('ix_prediction_snapshots_player_as_of', 'prediction_snapshots', ['player_id', 'as_of'])
    op.create_index('ix_prediction_snapshots_player_horizon', 'prediction_snapshots', ['player_id', 'horizon_days'])
    op.create_index('ix_prediction_snapshots_to_club', 'prediction_snapshots', ['to_club_id'])
    op.create_index('ix_prediction_snapshots_probability', 'prediction_snapshots', ['probability'])
    op.create_index('ix_prediction_snapshots_as_of', 'prediction_snapshots', ['as_of'])
    op.create_index('ix_prediction_snapshots_horizon', 'prediction_snapshots', ['horizon_days'])
    op.create_index('ix_prediction_snapshots_created_at', 'prediction_snapshots', ['created_at'])
    op.create_index('ix_prediction_snapshots_latest', 'prediction_snapshots', ['player_id', 'to_club_id', 'horizon_days', 'as_of'])
    
    # =========================================================================
    # UX LAYER - User Events
    # =========================================================================
    
    op.create_table(
        'user_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_anon_id', sa.String(100), nullable=False),
        sa.Column('session_id', sa.String(100), nullable=False),
        sa.Column('event_type', sa.Enum(
            'page_view', 'player_view', 'club_view', 'transfer_view', 'prediction_view',
            'watchlist_add', 'watchlist_remove', 'search', 'share', 'filter_apply', 'comparison_view',
            name='usereventtype'
        ), nullable=False),
        sa.Column('event_props_json', postgresql.JSONB(), nullable=True),
        sa.Column('player_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('club_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('device_type', sa.String(20), nullable=True),
        sa.Column('country_code', sa.String(2), nullable=True),
        sa.ForeignKeyConstraint(['player_id'], ['players.id']),
        sa.ForeignKeyConstraint(['club_id'], ['clubs.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_user_events_type', 'user_events', ['event_type'])
    op.create_index('ix_user_events_player', 'user_events', ['player_id'])
    op.create_index('ix_user_events_club', 'user_events', ['club_id'])
    op.create_index('ix_user_events_occurred_at', 'user_events', ['occurred_at'])
    op.create_index('ix_user_events_session', 'user_events', ['session_id'])
    op.create_index('ix_user_events_user_anon', 'user_events', ['user_anon_id'])
    op.create_index('ix_user_events_player_time', 'user_events', ['player_id', 'event_type', 'occurred_at'])
    op.create_index('ix_user_events_club_time', 'user_events', ['club_id', 'event_type', 'occurred_at'])
    
    # =========================================================================
    # USER FEATURES - Watchlists
    # =========================================================================
    
    op.create_table(
        'watchlists',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', sa.String(100), nullable=False),
        sa.Column('name', sa.String(255), nullable=False, server_default='My Watchlist'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_public', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('share_token', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('share_token')
    )
    op.create_index('ix_watchlists_user', 'watchlists', ['user_id'])
    op.create_index('ix_watchlists_share_token', 'watchlists', ['share_token'])
    
    op.create_table(
        'watchlist_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('watchlist_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('player_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('alert_on_transfer', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('alert_on_probability_change', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('probability_threshold', sa.Numeric(3, 2), nullable=True),
        sa.Column('added_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['watchlist_id'], ['watchlists.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['player_id'], ['players.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('watchlist_id', 'player_id', name='uq_watchlist_item_player')
    )
    op.create_index('ix_watchlist_items_watchlist', 'watchlist_items', ['watchlist_id'])
    op.create_index('ix_watchlist_items_player', 'watchlist_items', ['player_id'])
    
    # =========================================================================
    # AUDIT - Data Corrections
    # =========================================================================
    
    op.create_table(
        'data_corrections',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('table_name', sa.String(100), nullable=False),
        sa.Column('record_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('correction_type', sa.Enum('insert', 'update', 'delete', 'merge', name='correctiontype'), nullable=False),
        sa.Column('field_name', sa.String(100), nullable=True),
        sa.Column('old_value', postgresql.JSONB(), nullable=True),
        sa.Column('new_value', postgresql.JSONB(), nullable=True),
        sa.Column('new_record_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('source', sa.String(255), nullable=True),
        sa.Column('source_url', sa.String(1000), nullable=True),
        sa.Column('corrected_by', sa.String(100), nullable=False),
        sa.Column('corrected_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('reviewed_by', sa.String(100), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_data_corrections_table_record', 'data_corrections', ['table_name', 'record_id'])
    op.create_index('ix_data_corrections_corrected_at', 'data_corrections', ['corrected_at'])
    
    # =========================================================================
    # MATERIALIZED VIEW - Player Market View
    # =========================================================================
    
    # Create materialized view for fast reads of latest predictions per player + destination
    op.execute("""
        CREATE MATERIALIZED VIEW player_market_view AS
        WITH latest_predictions AS (
            SELECT DISTINCT ON (player_id, to_club_id, horizon_days)
                ps.id,
                ps.snapshot_id,
                ps.player_id,
                ps.from_club_id,
                ps.to_club_id,
                ps.horizon_days,
                ps.probability,
                ps.drivers_json,
                ps.model_version,
                ps.model_name,
                ps.as_of,
                ps.window_start,
                ps.window_end,
                ps.created_at
            FROM prediction_snapshots ps
            ORDER BY player_id, to_club_id, horizon_days, as_of DESC
        ),
        latest_market_value AS (
            SELECT DISTINCT ON (player_id)
                player_id,
                value_num as market_value,
                observed_at as market_value_observed_at
            FROM signal_events
            WHERE signal_type = 'market_value' AND entity_type = 'player'
            ORDER BY player_id, effective_from DESC
        ),
        latest_contract AS (
            SELECT DISTINCT ON (player_id)
                player_id,
                value_num as contract_months_remaining,
                observed_at as contract_observed_at
            FROM signal_events
            WHERE signal_type = 'contract_months_remaining' AND entity_type = 'player'
            ORDER BY player_id, effective_from DESC
        )
        SELECT 
            lp.id,
            lp.snapshot_id,
            lp.player_id,
            p.name as player_name,
            p.position as player_position,
            p.nationality as player_nationality,
            p.date_of_birth as player_dob,
            p.photo_url as player_photo_url,
            lp.from_club_id,
            fc.name as from_club_name,
            fc.logo_url as from_club_logo_url,
            lp.to_club_id,
            tc.name as to_club_name,
            tc.logo_url as to_club_logo_url,
            lp.horizon_days,
            lp.probability,
            lp.drivers_json,
            lp.model_version,
            lp.model_name,
            lp.as_of,
            lp.window_start,
            lp.window_end,
            lmv.market_value,
            lmv.market_value_observed_at,
            lc.contract_months_remaining,
            lc.contract_observed_at,
            lp.created_at
        FROM latest_predictions lp
        JOIN players p ON p.id = lp.player_id
        LEFT JOIN clubs fc ON fc.id = lp.from_club_id
        LEFT JOIN clubs tc ON tc.id = lp.to_club_id
        LEFT JOIN latest_market_value lmv ON lmv.player_id = lp.player_id
        LEFT JOIN latest_contract lc ON lc.player_id = lp.player_id
    """)
    
    # Create indexes on materialized view
    op.execute("CREATE INDEX ix_player_market_view_player ON player_market_view (player_id)")
    op.execute("CREATE INDEX ix_player_market_view_to_club ON player_market_view (to_club_id)")
    op.execute("CREATE INDEX ix_player_market_view_probability ON player_market_view (probability DESC)")
    op.execute("CREATE INDEX ix_player_market_view_horizon ON player_market_view (horizon_days)")
    op.execute("CREATE UNIQUE INDEX ix_player_market_view_unique ON player_market_view (player_id, to_club_id, horizon_days)")
    
    # Create function and trigger for refreshing materialized view
    op.execute("""
        CREATE OR REPLACE FUNCTION refresh_player_market_view()
        RETURNS TRIGGER AS $$
        BEGIN
            REFRESH MATERIALIZED VIEW CONCURRENTLY player_market_view;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # Note: In production, you'd typically refresh via a scheduled job rather than triggers
    # for performance reasons. This is here for completeness.


def downgrade() -> None:
    # Drop materialized view and function
    op.execute("DROP FUNCTION IF EXISTS refresh_player_market_view() CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS player_market_view")
    
    # Drop tables in reverse order (respecting foreign keys)
    op.drop_table('data_corrections')
    op.drop_table('watchlist_items')
    op.drop_table('watchlists')
    op.drop_table('user_events')
    op.drop_table('prediction_snapshots')
    op.drop_table('signal_events')
    op.drop_table('transfer_events')
    op.drop_table('players')
    op.drop_table('clubs')
    op.drop_table('seasons')
    op.drop_table('competitions')
    
    # Drop enums
    op.execute("DROP TYPE IF EXISTS correctiontype")
    op.execute("DROP TYPE IF EXISTS usereventtype")
    op.execute("DROP TYPE IF EXISTS feetype")
    op.execute("DROP TYPE IF EXISTS transfertype")
    op.execute("DROP TYPE IF EXISTS signaltypeenum")
    op.execute("DROP TYPE IF EXISTS entitytype")
