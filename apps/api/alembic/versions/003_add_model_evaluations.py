"""Add model_evaluations table

Revision ID: 003_add_model_evaluations
Revises: 002_add_ml_tables
Create Date: 2025-01-21
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers
revision = '003_add_model_evaluations'
down_revision = '002_add_ml_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create model_evaluations table
    op.create_table(
        'model_evaluations',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('model_version_id', UUID(as_uuid=True), sa.ForeignKey('model_versions.id'), nullable=False),
        sa.Column('evaluation_type', sa.String(50), nullable=False),  # 'holdout', 'backtest', 'live'
        sa.Column('evaluation_name', sa.String(200), nullable=False),  # e.g., 'season_2023-24'
        
        # Time bounds for evaluation
        sa.Column('evaluation_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('evaluation_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('horizon_days', sa.Integer, nullable=False),
        
        # Sample counts
        sa.Column('total_predictions', sa.Integer, nullable=False),
        sa.Column('total_positives', sa.Integer, nullable=False),
        sa.Column('total_negatives', sa.Integer, nullable=False),
        
        # Core metrics
        sa.Column('auc_roc', sa.Numeric(6, 4)),
        sa.Column('auc_pr', sa.Numeric(6, 4)),  # Precision-Recall AUC
        sa.Column('accuracy', sa.Numeric(6, 4)),
        sa.Column('precision_score', sa.Numeric(6, 4)),
        sa.Column('recall_score', sa.Numeric(6, 4)),
        sa.Column('f1_score', sa.Numeric(6, 4)),
        sa.Column('log_loss', sa.Numeric(10, 6)),
        sa.Column('brier_score', sa.Numeric(10, 6)),  # Calibration metric
        
        # Calibration metrics
        sa.Column('calibration_slope', sa.Numeric(8, 4)),  # Should be close to 1.0
        sa.Column('calibration_intercept', sa.Numeric(8, 4)),  # Should be close to 0.0
        sa.Column('calibration_bins', JSONB),  # {bin: {predicted: x, actual: y, count: n}}
        
        # Detailed metrics
        sa.Column('confusion_matrix', JSONB),  # {tp: x, fp: y, tn: z, fn: w}
        sa.Column('threshold_metrics', JSONB),  # Metrics at different thresholds
        sa.Column('feature_drift', JSONB),  # Feature distribution changes
        
        # Backtest specific
        sa.Column('backtest_windows', JSONB),  # [{start, end, auc, n_samples}, ...]
        
        # Metadata
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('evaluation_duration_seconds', sa.Numeric(10, 2)),
        sa.Column('notes', sa.Text),
    )
    
    # Create indexes
    op.create_index(
        'ix_model_evaluations_model_version',
        'model_evaluations',
        ['model_version_id']
    )
    op.create_index(
        'ix_model_evaluations_type_name',
        'model_evaluations',
        ['evaluation_type', 'evaluation_name']
    )
    op.create_index(
        'ix_model_evaluations_created_at',
        'model_evaluations',
        ['created_at']
    )


def downgrade() -> None:
    op.drop_table('model_evaluations')
