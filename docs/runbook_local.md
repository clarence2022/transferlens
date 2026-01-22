# Local Development Runbook

This guide explains how to run the complete TransferLens stack locally using Docker.

---

## Prerequisites

- Docker Desktop (or Docker + Docker Compose)
- Git
- 4GB+ RAM available for containers
- Ports 3000, 8000, 5432, 6379 available

---

## Quick Start

```bash
# Clone and enter directory
git clone https://github.com/transferlens/transferlens.git
cd transferlens

# Start everything
make up

# Seed demo data
make seed

# Generate predictions
make predict

# Open in browser
open http://localhost:3000
```

---

## Step-by-Step Setup

### 1. Start Infrastructure

```bash
# Start all services
docker compose up -d

# Check status
docker compose ps

# Expected output:
# NAME           STATUS                   PORTS
# tl-api         running                  0.0.0.0:8000->8000/tcp
# tl-web         running                  0.0.0.0:3000->3000/tcp
# tl-postgres    running (healthy)        0.0.0.0:5432->5432/tcp
# tl-redis       running (healthy)        0.0.0.0:6379->6379/tcp
```

### 2. Run Database Migrations

```bash
# Apply all migrations
docker compose exec api alembic upgrade head

# Verify tables exist
docker compose exec postgres psql -U transferlens -d transferlens -c "\dt"
```

### 3. Seed Demo Data

```bash
# Load demo players, clubs, signals, predictions
docker compose exec api python scripts/seed.py

# Or use worker CLI
docker compose --profile worker up -d worker
docker compose exec worker python -m worker.cli ingest:demo --force
```

### 4. Generate Predictions

```bash
# Start worker container
docker compose --profile worker up -d worker

# Option A: Run daily pipeline
docker compose exec worker python -m worker.cli daily:run

# Option B: Run individual steps
docker compose exec worker python -m worker.cli signals:derive --window 24h
docker compose exec worker python -m worker.cli features:build
docker compose exec worker python -m worker.cli predict:run --horizon 90
```

### 5. Verify Everything Works

```bash
# Check API health
curl http://localhost:8000/health

# Search for a player
curl "http://localhost:8000/api/v1/search?q=Haaland"

# Get market data
curl "http://localhost:8000/api/v1/market/latest?limit=5"

# Open web UI
open http://localhost:3000
```

---

## Service URLs

| Service | URL | Description |
|---------|-----|-------------|
| Web UI | http://localhost:3000 | Next.js frontend |
| API | http://localhost:8000 | FastAPI backend |
| API Docs | http://localhost:8000/docs | Swagger UI |
| PostgreSQL | localhost:5432 | Database (user: transferlens) |
| Redis | localhost:6379 | Cache/queue |

---

## Common Commands

### Docker Compose

```bash
# Start all services
docker compose up -d

# Start with worker
docker compose --profile worker up -d

# View logs
docker compose logs -f api
docker compose logs -f web
docker compose logs -f worker

# Stop all services
docker compose down

# Stop and remove volumes (reset database)
docker compose down -v

# Rebuild images
docker compose build --no-cache
docker compose up -d
```

### Database

```bash
# Connect to PostgreSQL
docker compose exec postgres psql -U transferlens -d transferlens

# Run a query
docker compose exec postgres psql -U transferlens -d transferlens -c "SELECT COUNT(*) FROM players"

# Run migrations
docker compose exec api alembic upgrade head

# Create new migration
docker compose exec api alembic revision -m "description"

# Rollback migration
docker compose exec api alembic downgrade -1

# Refresh materialized view
docker compose exec postgres psql -U transferlens -d transferlens -c "REFRESH MATERIALIZED VIEW player_market_view"
```

### Worker Jobs

```bash
# Seed demo data
docker compose exec worker python -m worker.cli ingest:demo --force

# Build features
docker compose exec worker python -m worker.cli features:build --as-of 2025-01-15T00:00:00

# Train model
docker compose exec worker python -m worker.cli model:train --horizon 90

# Generate predictions
docker compose exec worker python -m worker.cli predict:run --horizon 90

# Derive user signals
docker compose exec worker python -m worker.cli signals:derive --window 24h

# Run full daily pipeline
docker compose exec worker python -m worker.cli daily:run

# List trained models
docker compose exec worker python -m worker.cli model:list
```

### API

```bash
# Run tests
docker compose exec api pytest -v

# Check health
curl http://localhost:8000/health
curl http://localhost:8000/ready

# Search
curl "http://localhost:8000/api/v1/search?q=Salah"

# Get player
curl "http://localhost:8000/api/v1/players/{player_id}"

# Get club
curl "http://localhost:8000/api/v1/clubs/{club_id}"

# Get market
curl "http://localhost:8000/api/v1/market/latest?horizon_days=90&limit=10"

# Admin: refresh view (requires API key)
curl -X POST "http://localhost:8000/api/v1/admin/rebuild/materialized" \
  -H "X-API-Key: tl-admin-dev-key-change-in-production"
```

### Web

```bash
# Install dependencies (if running outside Docker)
cd apps/web
pnpm install

# Run dev server
pnpm dev

# Build
pnpm build
```

---

## Demo Data Walkthrough

After running `make seed`, you'll have:

### Players (15)
- Erling Haaland (Man City, ST)
- Bukayo Saka (Arsenal, RW)
- Jude Bellingham (Real Madrid, CAM)
- Lamine Yamal (Barcelona, RW)
- ... and 11 more

### Clubs (12)
- English: Man City, Arsenal, Liverpool, Chelsea
- Spanish: Real Madrid, Barcelona, Atletico
- German: Bayern, Dortmund
- Italian: Juventus, AC Milan, Inter

### Signals
- Market values
- Contract months remaining
- Goals and assists
- Social mention velocity
- User attention signals

### Predictions
- Transfer probabilities for each player
- Multiple destination clubs
- 30/90/180 day horizons

---

## Generating Fresh Predictions

To generate new predictions from scratch:

```bash
# 1. Clear existing predictions
docker compose exec postgres psql -U transferlens -d transferlens \
  -c "TRUNCATE prediction_snapshots CASCADE"

# 2. Build features
docker compose exec worker python -m worker.cli features:build

# 3. Train a model (optional - uses demo model if none exists)
docker compose exec worker python -m worker.cli model:train --horizon 90

# 4. Generate predictions
docker compose exec worker python -m worker.cli predict:run --horizon 90

# 5. Refresh the materialized view
docker compose exec worker python -m worker.cli refresh:views

# 6. Verify
curl "http://localhost:8000/api/v1/market/latest?limit=5" | jq
```

---

## Troubleshooting

### Services Won't Start

```bash
# Check what's using the ports
lsof -i :3000
lsof -i :8000
lsof -i :5432

# Kill conflicting processes
kill -9 <PID>

# Or use different ports
# Edit docker-compose.yml to change port mappings
```

### Database Connection Failed

```bash
# Check if postgres is healthy
docker compose ps

# View postgres logs
docker compose logs postgres

# Try restarting
docker compose restart postgres
```

### API Returns 500

```bash
# Check API logs
docker compose logs api

# Verify database connection
docker compose exec api python -c "from app.database import engine; print(engine.url)"

# Run migrations
docker compose exec api alembic upgrade head
```

### Worker Jobs Fail

```bash
# Check worker logs
docker compose logs worker

# Verify database connection
docker compose exec worker python -m worker.cli db:check

# Try running with debug output
docker compose exec worker python -m worker.cli daily:run 2>&1 | tee worker.log
```

### Predictions Not Showing

```bash
# Check if predictions exist
docker compose exec postgres psql -U transferlens -d transferlens \
  -c "SELECT COUNT(*) FROM prediction_snapshots"

# Check if materialized view is populated
docker compose exec postgres psql -U transferlens -d transferlens \
  -c "SELECT COUNT(*) FROM player_market_view"

# Refresh the view
docker compose exec worker python -m worker.cli refresh:views
```

---

## Environment Variables

### API (apps/api)

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | postgresql://... | Database connection |
| `REDIS_URL` | redis://... | Redis connection |
| `ADMIN_API_KEY` | tl-admin-dev-key... | Admin endpoint auth |
| `API_VERSION` | v1 | API version prefix |

### Worker (apps/worker)

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | postgresql://... | Database connection |
| `REDIS_URL` | redis://... | Redis connection |
| `MODEL_STORAGE_PATH` | /app/models | Model artifact storage |

### Web (apps/web)

| Variable | Default | Description |
|----------|---------|-------------|
| `NEXT_PUBLIC_API_URL` | http://localhost:8000 | API base URL |

---

## Development Workflow

### Making API Changes

1. Edit files in `apps/api/`
2. API hot-reloads automatically (volume mounted)
3. Test: `curl http://localhost:8000/...`

### Making Worker Changes

1. Edit files in `apps/worker/`
2. Run command: `docker compose exec worker python -m worker.cli <command>`

### Making Web Changes

1. Edit files in `apps/web/`
2. Web hot-reloads automatically
3. View at http://localhost:3000

### Making Database Changes

1. Create migration: `docker compose exec api alembic revision -m "add_column"`
2. Edit migration file
3. Apply: `docker compose exec api alembic upgrade head`

---

## See Also

- [Architecture](./architecture.md) — System design
- [Data Contracts](./data_contracts.md) — Table definitions
- [Ontology Rules](./ontology_rules.md) — Data classification rules
