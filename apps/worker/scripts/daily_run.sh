#!/bin/bash
# =============================================================================
# TransferLens Daily Run Script
# =============================================================================
#
# Executes the daily pipeline:
# 1. Derive signals from user events (24h window)
# 2. Build feature tables
# 3. Generate prediction snapshots for multiple horizons
#
# Usage:
#   ./scripts/daily_run.sh [--horizon 90]
#
# Environment:
#   DATABASE_URL - PostgreSQL connection string
#   LOG_LEVEL - Logging level (default: INFO)
#
# =============================================================================

set -e

# Configuration
HORIZON=${1:-90}
LOG_FILE="/var/log/transferlens/daily_$(date +%Y%m%d_%H%M%S).log"

echo "=============================================="
echo "TransferLens Daily Run"
echo "=============================================="
echo "Start time: $(date -Iseconds)"
echo "Horizon: $HORIZON days"
echo "Log file: $LOG_FILE"
echo "=============================================="

# Create log directory if it doesn't exist
mkdir -p /var/log/transferlens

# Run the daily pipeline
python -m worker.cli daily:run --horizon $HORIZON 2>&1 | tee "$LOG_FILE"

EXIT_CODE=${PIPESTATUS[0]}

echo ""
echo "=============================================="
echo "End time: $(date -Iseconds)"
echo "Exit code: $EXIT_CODE"
echo "=============================================="

exit $EXIT_CODE
