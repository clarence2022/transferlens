# TransferLens API

FastAPI service implementing the four-layer architecture for football transfer intelligence.

## Architecture Layers

| Layer | Description | Tables |
|-------|-------------|--------|
| **Core Entities** | Reference data | `competitions`, `seasons`, `clubs`, `players` |
| **Ledger** | Immutable completed transfers | `transfer_events` |
| **Signals** | Time-stamped signals with provenance | `signal_events` |
| **Market** | Model outputs & predictions | `prediction_snapshots` |
| **UX** | User events & watchlists | `user_events`, `watchlists`, `watchlist_items` |
| **Audit** | Data correction tracking | `data_corrections` |

## Database Schema

### Core Entities

```sql
-- competitions: Football leagues/cups
-- seasons: Season periods per competition
-- clubs: Football clubs with current competition
-- players: Player profiles with current club
```

### Ledger Layer: `transfer_events`

Immutable append-only ledger for completed transfers:

| Column | Type | Description |
|--------|------|-------------|
| `event_id` | VARCHAR(100) | Unique ID: `TL-YYYYMMDD-PLAYERID-FROMCLUBID` |
| `player_id` | UUID | Player being transferred |
| `from_club_id` | UUID (nullable) | Origin club (null for youth) |
| `to_club_id` | UUID | Destination club |
| `transfer_type` | ENUM | permanent, loan, loan_with_option, etc. |
| `fee_amount` | NUMERIC | Transfer fee |
| `fee_currency` | VARCHAR(3) | Currency code |
| `fee_type` | ENUM | confirmed, reported, estimated, undisclosed |
| `contract_start` | DATE | Contract start date |
| `contract_end` | DATE | Contract end date |
| `option_to_buy` | BOOLEAN | Has purchase option |
| `sell_on_percent` | NUMERIC | Sell-on clause percentage |
| `source` | VARCHAR | Data source |
| `source_confidence` | NUMERIC(3,2) | 0.00-1.00 confidence |
| `is_superseded` | BOOLEAN | Soft-delete for corrections |

### Signals Layer: `signal_events`

Append-only signal storage with time-travel support:

| Column | Type | Description |
|--------|------|-------------|
| `entity_type` | ENUM | player, club, club_player_pair |
| `player_id` | UUID | Player reference |
| `club_id` | UUID | Club reference |
| `signal_type` | ENUM | See signal types below |
| `value_json` | JSONB | Complex values |
| `value_num` | NUMERIC | Numeric values |
| `value_text` | TEXT | Text values |
| `source` | VARCHAR | Data source |
| `confidence` | NUMERIC(3,2) | 0.00-1.00 confidence |
| `observed_at` | TIMESTAMPTZ | When signal was observed |
| `effective_from` | TIMESTAMPTZ | When it became true |
| `effective_to` | TIMESTAMPTZ | When it stopped being true |

**Signal Types:**
- Performance: `minutes_last_5`, `injuries_status`, `goals_last_10`, `assists_last_10`
- Club: `club_league_position`, `club_points_per_game`, `club_net_spend_12m`
- Contract: `contract_months_remaining`, `wage_estimate`, `market_value`, `release_clause`
- Social: `social_mention_velocity`, `social_sentiment`
- User-derived: `user_attention_velocity`, `user_destination_cooccurrence`, `user_watchlist_adds`

### Market Layer: `prediction_snapshots`

Point-in-time probability estimates:

| Column | Type | Description |
|--------|------|-------------|
| `snapshot_id` | VARCHAR(100) | Unique snapshot ID |
| `model_version` | VARCHAR(50) | Model version string |
| `model_name` | VARCHAR(100) | Model identifier |
| `player_id` | UUID | Player being predicted |
| `from_club_id` | UUID | Current club at prediction |
| `to_club_id` | UUID (nullable) | Target club (null = any move) |
| `horizon_days` | INTEGER | 30, 90, or 180 days |
| `probability` | NUMERIC(5,4) | 0.0000-1.0000 |
| `drivers_json` | JSONB | Feature importance |
| `as_of` | TIMESTAMPTZ | Signals cutoff time |
| `window_start` | DATE | Prediction window start |
| `window_end` | DATE | Prediction window end |

### Materialized View: `player_market_view`

Read-optimized view for latest predictions per player + destination:

```sql
-- Returns latest prediction per (player_id, to_club_id, horizon_days)
-- Includes player info, club info, market value, contract months
```

Refresh with: `REFRESH MATERIALIZED VIEW CONCURRENTLY player_market_view`

## Quick Start

```bash
# Install dependencies
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Set up database
export DATABASE_URL="postgresql://transferlens:transferlens_dev@localhost:5432/transferlens"
alembic upgrade head

# Seed demo data
python scripts/seed.py

# Run server
uvicorn main:app --reload --port 8000
```

## API Endpoints

### Health
- `GET /health` - Health check with dependency status
- `GET /ready` - Kubernetes readiness probe
- `GET /live` - Kubernetes liveness probe

### Players
- `GET /api/v1/players` - List players (paginated, filterable)
- `GET /api/v1/players/{id}` - Player detail with signals & predictions
- `POST /api/v1/players` - Create player
- `GET /api/v1/players/{id}/signals` - Signal history
- `GET /api/v1/players/{id}/predictions` - Prediction history

### Clubs
- `GET /api/v1/clubs` - List clubs (paginated, filterable)
- `GET /api/v1/clubs/{id}` - Club detail with stats
- `POST /api/v1/clubs` - Create club
- `GET /api/v1/clubs/{id}/squad` - Current squad
- `GET /api/v1/clubs/{id}/transfers` - Transfer history

### Transfers (Ledger)
- `GET /api/v1/transfers` - List transfers (paginated, filterable)
- `GET /api/v1/transfers/{id}` - Transfer detail
- `POST /api/v1/transfers` - Record completed transfer
- `GET /api/v1/transfers/stats/summary` - Aggregate statistics

### Signals
- `GET /api/v1/signals/{player_id}` - Player signals
- `GET /api/v1/signals/{player_id}/latest` - Latest signal per type
- `GET /api/v1/signals/{player_id}/timeseries/{signal_name}` - Time series
- `POST /api/v1/signals` - Record signal
- `POST /api/v1/signals/batch` - Bulk record signals

### Market (Predictions)
- `GET /api/v1/market/probabilities` - Transfer probability table
- `GET /api/v1/market/predictions/{player_id}` - Prediction history
- `GET /api/v1/market/predictions/{player_id}/latest` - Latest prediction
- `POST /api/v1/market/predictions` - Record prediction
- `GET /api/v1/market/movers` - Biggest probability changes

### Events & Watchlists
- `POST /api/v1/events` - Record user event
- `GET /api/v1/events/watchlist` - Get user watchlist
- `POST /api/v1/events/watchlist` - Add to watchlist
- `DELETE /api/v1/events/watchlist/{player_id}` - Remove from watchlist
- `GET /api/v1/events/stats/trending` - Trending players

## Time-Travel Queries

All relevant endpoints support an `as_of` query parameter for time-travel queries:

```bash
# Get player state as of 30 days ago
GET /api/v1/players/123?as_of=2025-01-01T00:00:00Z

# Get probability table at a historical point
GET /api/v1/market/probabilities?as_of=2025-01-01T00:00:00Z
```

## Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one version
alembic downgrade -1
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://...` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `ENVIRONMENT` | Environment name | `development` |
| `DEBUG` | Enable debug mode | `false` |
| `SECRET_KEY` | Secret key for sessions | `change-me-in-production` |

## Testing

```bash
pytest -v
pytest --cov=app --cov-report=html
```
