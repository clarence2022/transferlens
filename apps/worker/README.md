# TransferLens Worker

Background job runner for the TransferLens platform.

## Overview

The worker service handles:
- **Data Ingestion**: Loading demo/seed data
- **Feature Building**: Building feature vectors for (player, club) pairs
- **Model Training**: Training transfer prediction models
- **Prediction Generation**: Generating probability snapshots
- **Signal Derivation**: Deriving weak signals from user events

## Commands

### Data Ingestion

```bash
# Load demo seed data (idempotent)
python -m worker.cli ingest:demo --force
```

### Feature Building

```bash
# Build features as of now
python -m worker.cli features:build

# Build features as of specific timestamp (time-travel)
python -m worker.cli features:build --as-of 2025-01-15T00:00:00
```

### Model Training

```bash
# Train model with 90-day horizon
python -m worker.cli model:train --horizon 90

# Train with specific parameters
python -m worker.cli model:train \
    --as-of 2025-01-15T00:00:00 \
    --horizon 90 \
    --model-type logistic \
    --lookback 730

# List trained models
python -m worker.cli model:list
```

### Prediction Generation

```bash
# Generate predictions with 90-day horizon
python -m worker.cli predict:run --horizon 90

# Generate predictions as of specific timestamp
python -m worker.cli predict:run --as-of 2025-01-15T00:00:00 --horizon 90

# Test predictions for a single player
python -m worker.cli predict:player <player-uuid> --horizon 90
```

### Signal Derivation

```bash
# Derive signals from last 24 hours of user events
python -m worker.cli signals:derive --window 24h

# Derive signals from last 7 days
python -m worker.cli signals:derive --window 7d
```

### Daily Run

```bash
# Run the complete daily pipeline
python -m worker.cli daily:run --horizon 90

# Skip specific steps
python -m worker.cli daily:run --skip-signals
python -m worker.cli daily:run --skip-features
python -m worker.cli daily:run --skip-predictions
```

### Utility Commands

```bash
# Check database connection
python -m worker.cli db:check

# Refresh materialized views
python -m worker.cli refresh:views
```

## Docker Compose Usage

```bash
# Run ingest:demo
docker compose exec worker python -m worker.cli ingest:demo --force

# Run daily pipeline
docker compose exec worker python -m worker.cli daily:run

# Run model training
docker compose exec worker python -m worker.cli model:train --horizon 90

# Run predictions
docker compose exec worker python -m worker.cli predict:run --horizon 90
```

## Daily Pipeline

The daily pipeline (`daily:run`) executes:

1. **Signal Derivation** (signals:derive)
   - Computes `user_attention_velocity` per player
   - Computes `user_destination_cooccurrence` for (player, club) pairs
   - Sources: 24h window of user events
   - Confidence: 0.6 (weak signals)

2. **Feature Building** (features:build)
   - Builds feature vectors for all active players
   - For each player, generates candidates from:
     - Same league clubs
     - Top clubs from other leagues
     - Clubs with user attention signals
     - Random negative samples

3. **Prediction Generation** (predict:run)
   - Loads latest trained model
   - Generates predictions for each (player, club) candidate
   - Stores probability + driver explanations
   - Refreshes materialized view

## Model Training

The training job:
- Uses historical transfers as positive labels
- Samples non-transfers as negative labels
- **No data leakage**: Only uses signals observed before transfer_date
- Saves model artifacts to `/app/models/`
- Registers in `model_versions` table

### Features Used

| Category | Features |
|----------|----------|
| Player | market_value, contract_months_remaining, goals_last_10, assists_last_10, age |
| From Club | club_tier, league_position, points_per_game, net_spend_12m |
| To Club | club_tier, league_position, points_per_game, net_spend_12m |
| Pair | same_country, same_league, tier_difference, user_destination_cooccurrence |

### Driver Explanations

For each prediction, the top contributing features are computed using a simplified approach:
- For logistic regression: Uses absolute coefficient values
- Normalized and displayed as top-N drivers

Example drivers output:
```json
{
  "contract_months_remaining": 0.35,
  "market_value": 0.20,
  "user_destination_cooccurrence": 0.15,
  "same_league": 0.10,
  "tier_difference": 0.10
}
```

## Configuration

Environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://transferlens:...` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `MODEL_STORAGE_PATH` | Path to store model artifacts | `/app/models` |
| `DEFAULT_HORIZON_DAYS` | Default prediction horizon | `90` |
| `CANDIDATE_CLUBS_PER_PLAYER` | Max candidate clubs | `20` |
| `MIN_TRAINING_SAMPLES` | Min samples for training | `50` |
| `DERIVED_SIGNAL_CONFIDENCE` | Confidence for derived signals | `0.6` |

## Database Tables

### model_versions

Tracks trained model versions:
- Model identification (name, version)
- Training parameters (horizon, as_of)
- Training data stats (samples, features)
- Performance metrics (accuracy, precision, recall, AUC)
- Feature importances
- Artifact path
- Status (training, completed, deployed, failed, archived)

### feature_snapshots

Caches built features:
- Player ID
- Candidate club ID
- As-of timestamp
- Feature vector (JSONB)
- Feature version

## Scheduled Runs

For production, schedule the daily run via cron or external scheduler:

```bash
# Cron example (run at 4 AM UTC daily)
0 4 * * * docker compose exec -T worker python -m worker.cli daily:run >> /var/log/transferlens/daily.log 2>&1
```

Or use the included script:
```bash
# In Docker Compose
docker compose exec worker ./scripts/daily_run.sh
```

## Development

```bash
# Install dependencies
cd apps/worker
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run locally (requires DATABASE_URL)
export DATABASE_URL="postgresql://transferlens:transferlens_dev@localhost:5432/transferlens"
python -m worker.cli db:check
python -m worker.cli ingest:demo --force
```

## Testing

```bash
pytest tests/
```

## License

MIT © TransferLens Team
