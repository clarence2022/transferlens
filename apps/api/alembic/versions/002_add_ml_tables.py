"""Add model_versions and feature_snapshots tables

Revision ID: 002_add_ml_tables
Revises: 001_initial_schema
Create Date: 2025-01-21

Adds tables for ML model tracking and feature caching:
- model_versions: Track trained model versions and metadata
- feature_snapshots: Cache built features for (player, club) pairs
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002_add_ml_tables'
down_revision = '001_initial_schema'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create model_status enum
    model_status_enum = postgresql.ENUM(
        'training', 'completed', 'failed', 'deployed', 'archived',
        name='modelstatus', create_type=False
    )
    model_status_enum.create(op.get_bind(), checkfirst=True)
    
    # Create model_versions table
    op.create_table(
        'model_versions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('model_name', sa.String(100), nullable=False),
        sa.Column('model_version', sa.String(50), nullable=False),
        sa.Column('horizon_days', sa.Integer(), nullable=False),
        sa.Column('training_as_of', sa.DateTime(timezone=True), nullable=False),
        sa.Column('training_samples', sa.Integer(), nullable=False),
        sa.Column('positive_samples', sa.Integer(), nullable=False),
        sa.Column('negative_samples', sa.Integer(), nullable=False),
        sa.Column('feature_count', sa.Integer(), nullable=False),
        sa.Column('features_used', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('metrics', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('feature_importances', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('artifact_path', sa.String(500), nullable=True),
        sa.Column('status', sa.Enum('training', 'completed', 'failed', 'deployed', 'archived', name='modelstatus'), nullable=False, server_default='training'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deployed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('model_name', 'model_version', name='uq_model_name_version')
    )
    op.create_index('ix_model_versions_name', 'model_versions', ['model_name'])
    op.create_index('ix_model_versions_status', 'model_versions', ['status'])
    op.create_index('ix_model_versions_horizon', 'model_versions', ['horizon_days'])
    op.create_index('ix_model_versions_created_at', 'model_versions', ['created_at'])
    
    # Create feature_snapshots table
    op.create_table(
        'feature_snapshots',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('player_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('candidate_club_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('as_of', sa.DateTime(timezone=True), nullable=False),
        sa.Column('features', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('feature_version', sa.String(50), server_default='v1', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('player_id', 'candidate_club_id', 'as_of', name='uq_feature_snapshot_player_club_asof')
    )
    op.create_index('ix_feature_snapshots_player_as_of', 'feature_snapshots', ['player_id', 'as_of'])
    op.create_index('ix_feature_snapshots_as_of', 'feature_snapshots', ['as_of'])


def downgrade() -> None:
    # Drop feature_snapshots table
    op.drop_index('ix_feature_snapshots_as_of', table_name='feature_snapshots')
    op.drop_index('ix_feature_snapshots_player_as_of', table_name='feature_snapshots')
    op.drop_table('feature_snapshots')
    
    # Drop model_versions table
    op.drop_index('ix_model_versions_created_at', table_name='model_versions')
    op.drop_index('ix_model_versions_horizon', table_name='model_versions')
    op.drop_index('ix_model_versions_status', table_name='model_versions')
    op.drop_index('ix_model_versions_name', table_name='model_versions')
    op.drop_table('model_versions')
    
    # Drop enum
    sa.Enum(name='modelstatus').drop(op.get_bind(), checkfirst=True)
