# TransferLens 🔭

**The Bloomberg Terminal for Football Transfers**

Real-time transfer intelligence. Track probabilities, signals, and market movements before they happen.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Next.js 14](https://img.shields.io/badge/Next.js-14-black.svg)](https://nextjs.org/)

---

## Quick Start

```bash
# Clone the repository
git clone https://github.com/transferlens/transferlens.git
cd transferlens

# Start everything
make up
make seed
make predict

# Open http://localhost:3000
```

---

## Demo Walkthrough

A 2-minute tour of TransferLens in action.

### 1. Seed Data & Generate Predictions

```bash
make up          # Start services
make seed        # Load demo data (15 players, 12 clubs, 450+ signals)
make predict     # Generate transfer probabilities
```

### 2. Open a Player Page

Navigate to **http://localhost:3000/players/[id]** (e.g., Erling Haaland).

You'll see:
- **Transfer Probabilities**: Top destinations with 30/90/180 day horizons
- **Probability Drivers**: Why each prediction was made (contract months, market value, etc.)
- **Signal History**: Time-series of market value, performance, social mentions

### 3. View "What Changed"

The player page shows a **"What Changed"** section:

```
📈 What Changed (Last 7 Days)
─────────────────────────────
• Market value: €180M → €185M (+2.8%)
• Contract months remaining: 36 → 35
• Social mention velocity: 1.2x → 2.4x ⚡
• Real Madrid probability: 12% → 18% (+6%)
```

This shows signal deltas that explain why probabilities shifted.

### 4. Share a Link

Click **Share** on any player or prediction. This copies a deep link:

```
https://localhost:3000/players/abc123?as_of=2025-01-21
```

The `as_of` parameter preserves the exact snapshot, so shared links always show what you saw.

### 5. Event is Logged

Every interaction is tracked as a user event:

```bash
# Check the event was logged
curl http://localhost:8000/api/v1/admin/events/recent \
  -H "X-API-Key: tl-admin-dev-key-change-in-production"
```

```json
{
  "events": [
    {
      "event_type": "share",
      "player_id": "abc123",
      "occurred_at": "2025-01-21T12:34:56Z",
      "session_id": "sess_xyz"
    }
  ]
}
```

User events flow through the pipeline:
1. **Logged** → `user_events` table
2. **Aggregated** → `signals:derive` job (hourly)
3. **Converted** → Weak signals (`user_attention_velocity`, `user_destination_cooccurrence`)
4. **Fed back** → Next prediction batch (with `confidence ≤ 0.6`)

---

## What is TransferLens?

TransferLens aggregates signals from multiple sources to predict football transfer probabilities. Unlike rumour aggregators, we maintain strict data discipline:

- **Ledger**: Only confirmed, completed transfers (immutable)
- **Signals**: Time-stamped observations with source and confidence
- **Predictions**: Probability snapshots that are never overwritten
- **User Behavior**: Weak signals only, never ground truth

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         UX LAYER                                     │
│   Next.js Terminal UI • Watchlists • User Event Tracking             │
│   (ephemeral, never ground truth)                                    │
├─────────────────────────────────────────────────────────────────────┤
│                       MARKET LAYER                                   │
│   Probability Snapshots • Model Outputs • Explanation Drivers        │
│   (derived, versioned, never overwritten)                            │
├─────────────────────────────────────────────────────────────────────┤
│                      SIGNALS LAYER                                   │
│   Performance • Contract • Finance • Social • User-Derived           │
│   (bi-temporal, auditable, source + confidence)                      │
├─────────────────────────────────────────────────────────────────────┤
│                       LEDGER LAYER                                   │
│   Confirmed Transfers Only • Immutable • Append-Only                 │
│   (single source of truth)                                           │
└─────────────────────────────────────────────────────────────────────┘
```

See [docs/architecture.md](docs/architecture.md) for details.

---

## Key Features

### 🎯 Transfer Probability Engine
- Machine learning predictions for 30/90/180 day windows
- Feature importance ("drivers") explaining each prediction
- Historical probability tracking for backtesting

### 📊 Signal Aggregation
- Official data: Market values, contract dates, performance stats
- Social signals: Mention velocity, sentiment analysis
- User-derived: Attention patterns, destination co-occurrence

### 🔒 Data Integrity
- Strict separation of fact vs. prediction vs. speculation
- Bi-temporal queries ("what did we know on date X?")
- Full audit trail with source attribution

### ⚡ Real-Time UI
- Bloomberg Terminal-inspired dark theme
- Sub-100ms search with fuzzy matching
- ISR caching for instant page loads

---

## Project Structure

```
transferlens/
├── apps/
│   ├── api/              # FastAPI backend
│   │   ├── app/          # Application code
│   │   │   ├── routers/  # API endpoints
│   │   │   ├── schemas.py
│   │   │   └── services.py
│   │   ├── alembic/      # Database migrations
│   │   └── tests/        # API tests
│   │
│   ├── web/              # Next.js frontend
│   │   ├── src/app/      # App router pages
│   │   ├── src/components/
│   │   └── src/lib/      # API client, tracking
│   │
│   └── worker/           # Background jobs
│       └── worker/
│           ├── jobs/     # CLI commands
│           └── ml/       # ML utilities
│
├── packages/
│   └── shared/           # TypeScript client & types
│
├── docs/
│   ├── architecture.md   # Layer design & anti-leakage rules
│   ├── data_contracts.md # Table definitions & invariants
│   ├── ontology_rules.md # What goes where
│   └── runbook_local.md  # Local development guide
│
├── docker-compose.yml
├── Makefile              # Common commands
└── README.md
```

---

## Technology Stack

| Component | Technology |
|-----------|------------|
| Database | PostgreSQL 15 |
| API | FastAPI (Python 3.11) |
| Frontend | Next.js 14 (React 18) |
| Styling | Tailwind CSS |
| Charts | Recharts |
| ML | scikit-learn |
| Cache | Redis |
| Container | Docker Compose |

---

## Development

### Prerequisites

- Docker & Docker Compose
- 4GB+ RAM available
- Ports 3000, 8000, 5432, 6379 available

### Make Commands

```bash
make up          # Start all services
make down        # Stop all services
make seed        # Load demo data
make predict     # Generate predictions
make test        # Run all tests

make train       # Train a new model
make features    # Build feature tables
make signals     # Derive user signals
make daily       # Run daily pipeline

make shell-api   # Open API shell
make shell-db    # Open PostgreSQL shell
make logs        # View all logs
make status      # Check service health
```

### Manual Setup

```bash
# Start infrastructure
docker compose up -d

# Run migrations
docker compose exec api alembic upgrade head

# Seed demo data
docker compose exec api python scripts/seed.py

# Start worker and generate predictions
docker compose --profile worker up -d worker
docker compose exec worker python -m worker.cli daily:run
```

---

## API Endpoints

### Public

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health check |
| `GET /api/v1/search?q=` | Search players & clubs |
| `GET /api/v1/players/{id}` | Player detail + predictions + what changed |
| `GET /api/v1/players/{id}/signals` | Signal history (time-travel supported) |
| `GET /api/v1/players/{id}/predictions` | Prediction history |
| `GET /api/v1/clubs/{id}` | Club detail + squad + probabilities |
| `GET /api/v1/market/latest` | Probability table with filters |
| `POST /api/v1/events/user` | Track user events |

### Admin (requires `X-API-Key` header)

| Endpoint | Description |
|----------|-------------|
| `POST /api/v1/admin/transfer_events` | Create transfer event |
| `POST /api/v1/admin/signal_events` | Create signal event |
| `POST /api/v1/admin/rebuild/materialized` | Refresh views |

---

## Worker Commands

```bash
# Demo data
python -m worker.cli ingest:demo --force

# Feature building
python -m worker.cli features:build --as-of 2025-01-15T00:00:00

# Model training
python -m worker.cli model:train --horizon 90 --model-type logistic

# Prediction generation
python -m worker.cli predict:run --horizon 90

# Signal derivation
python -m worker.cli signals:derive --window 24h

# Daily pipeline (signals → features → predict)
python -m worker.cli daily:run
```

---

## Data Principles

These rules prevent ontology pollution. Violating them corrupts the system.

### 1. Ledger is Sacred
Only confirmed, completed transfers. Never rumours or "done deals" until official.

### 2. Signals Must Be Sourced
Every signal has: `observed_at`, `effective_from`, `source`, `confidence`.

### 3. User Behavior is Weak
User-derived signals have `confidence ≤ 0.6` and `source = 'tl_user_derived'`.

### 4. Predictions are Snapshots
Never update. Always insert new snapshots. `snapshot_id` is deterministic.

### 5. No Time-Travel Violations
Features only use data with `effective_from ≤ as_of`.

See [docs/ontology_rules.md](docs/ontology_rules.md) for complete rules.

---

## Demo Data

After running `make seed`, you'll have:

| Entity | Count | Examples |
|--------|-------|----------|
| Competitions | 4 | Premier League, La Liga, Bundesliga, Serie A |
| Clubs | 12 | Man City, Arsenal, Real Madrid, Bayern... |
| Players | 15 | Haaland, Saka, Bellingham, Yamal... |
| Signals | 450+ | Market values, contract months, goals... |
| Predictions | 100+ | 30/90/180 day transfer probabilities |

---

## Service URLs

| Service | URL |
|---------|-----|
| Web UI | http://localhost:3000 |
| API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |

---

## Documentation

| Document | Description |
|----------|-------------|
| [architecture.md](docs/architecture.md) | Four-layer design, anti-leakage rules |
| [data_contracts.md](docs/data_contracts.md) | Table definitions, constraints, invariants |
| [ontology_rules.md](docs/ontology_rules.md) | What data goes where |
| [runbook_local.md](docs/runbook_local.md) | Local development guide |
| [deployment.md](docs/deployment.md) | Production deployment guide |
| [deploy/env-vars.md](docs/deploy/env-vars.md) | Environment variable reference |

---

## Deployment

Deploy to **Fly.io** or **Render** with managed Postgres.

```bash
# Fly.io (recommended)
fly apps create transferlens-api
fly secrets set DATABASE_URL="postgres://..." ADMIN_API_KEY="..."
fly deploy -c apps/api/fly.toml

# Or use Render Blueprint
# Connect GitHub repo → Deploy with render.yaml
```

See [deployment.md](docs/deployment.md) for detailed instructions.

---

## Roadmap

- [ ] Email alerts for watchlist changes
- [ ] Historical accuracy dashboard
- [ ] Additional data sources (social, news)
- [ ] Multi-model ensemble predictions
- [ ] Public API tier

---

## Contributing

1. Read [docs/ontology_rules.md](docs/ontology_rules.md) first
2. Fork the repository
3. Create a feature branch
4. Run tests: `make test`
5. Submit a pull request

---

## License

MIT © TransferLens Team

---

<p align="center">
  <strong>TRANSFER</strong><span style="color: #ff6b00">LENS</span>
  <br>
  <em>Real-time transfer intelligence</em>
</p>
