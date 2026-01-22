"""Add candidate_sets table for auditable destination candidates

Revision ID: 004_add_candidate_sets
Revises: 003_add_model_evaluations
Create Date: 2025-01-21
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers
revision = '004_add_candidate_sets'
down_revision = '003_add_model_evaluations'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create candidate_sets table
    op.create_table(
        'candidate_sets',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('player_id', UUID(as_uuid=True), sa.ForeignKey('players.id'), nullable=False),
        sa.Column('as_of', sa.DateTime(timezone=True), nullable=False),
        sa.Column('horizon_days', sa.Integer, nullable=False),
        
        # Current club at time of candidate generation
        sa.Column('from_club_id', UUID(as_uuid=True), sa.ForeignKey('clubs.id')),
        
        # Candidate counts by source
        sa.Column('total_candidates', sa.Integer, nullable=False),
        sa.Column('league_candidates', sa.Integer, default=0),
        sa.Column('social_candidates', sa.Integer, default=0),
        sa.Column('user_attention_candidates', sa.Integer, default=0),
        sa.Column('constraint_fit_candidates', sa.Integer, default=0),
        sa.Column('random_candidates', sa.Integer, default=0),
        
        # The actual candidates with metadata
        # Format: [{club_id, source, score, reason}, ...]
        sa.Column('candidates_json', JSONB, nullable=False),
        
        # Player context at generation time
        sa.Column('player_context_json', JSONB),  # market_value, position, contract_months, etc.
        
        # Generation metadata
        sa.Column('generation_version', sa.String(50), default='v1'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    
    # Create indexes
    op.create_index(
        'ix_candidate_sets_player_as_of',
        'candidate_sets',
        ['player_id', 'as_of']
    )
    op.create_index(
        'ix_candidate_sets_as_of',
        'candidate_sets',
        ['as_of']
    )
    
    # Create unique constraint to prevent duplicate generation
    op.create_unique_constraint(
        'uq_candidate_sets_player_as_of_horizon',
        'candidate_sets',
        ['player_id', 'as_of', 'horizon_days']
    )


def downgrade() -> None:
    op.drop_table('candidate_sets')
