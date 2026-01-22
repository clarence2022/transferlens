# Production Deployment Guide

This guide covers deploying TransferLens to production using Fly.io or Render.

---

## Architecture Overview

```
                                    ┌─────────────────┐
                                    │   CloudFlare    │
                                    │   (DNS + CDN)   │
                                    └────────┬────────┘
                                             │
                    ┌────────────────────────┼────────────────────────┐
                    │                        │                        │
                    ▼                        ▼                        ▼
           ┌───────────────┐       ┌───────────────┐       ┌───────────────┐
           │     Web       │       │      API      │       │    Worker     │
           │   (Next.js)   │       │   (FastAPI)   │       │   (Python)    │
           │   Port 3000   │       │   Port 8000   │       │   (cron)      │
           └───────┬───────┘       └───────┬───────┘       └───────┬───────┘
                   │                       │                       │
                   │                       │                       │
                   │            ┌──────────┴──────────┐            │
                   │            │                     │            │
                   │            ▼                     ▼            │
                   │    ┌───────────────┐     ┌───────────────┐    │
                   │    │   Postgres    │     │    Redis      │    │
                   │    │   (Managed)   │     │   (Optional)  │    │
                   │    └───────────────┘     └───────────────┘    │
                   │            ▲                     ▲            │
                   └────────────┴─────────────────────┴────────────┘
```

---

## Environment Variables

### Required for All Services

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@host:5432/db` |

### API Service

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection | `postgresql://...` |
| `REDIS_URL` | Redis connection (optional) | `redis://host:6379` |
| `ADMIN_API_KEY` | Admin endpoint authentication | `tl-admin-prod-xxxxx` |
| `CORS_ORIGINS` | Allowed CORS origins | `https://transferlens.io,https://www.transferlens.io` |
| `API_VERSION` | API version prefix | `v1` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `RATE_LIMIT_REQUESTS` | Requests per window | `100` |
| `RATE_LIMIT_WINDOW` | Rate limit window (seconds) | `60` |
| `ENVIRONMENT` | Deployment environment | `production` |

### Web Service

| Variable | Description | Example |
|----------|-------------|---------|
| `NEXT_PUBLIC_API_URL` | API base URL | `https://api.transferlens.io` |
| `NEXT_PUBLIC_SITE_URL` | Site URL for OG images | `https://transferlens.io` |

### Worker Service

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection | `postgresql://...` |
| `REDIS_URL` | Redis connection (optional) | `redis://host:6379` |
| `MODEL_STORAGE_PATH` | Model artifact storage | `/app/models` |
| `LOG_LEVEL` | Logging level | `INFO` |

---

## Option 1: Fly.io Deployment

### Prerequisites

```bash
# Install Fly CLI
curl -L https://fly.io/install.sh | sh

# Login
fly auth login
```

### 1. Create Fly Apps

```bash
cd transferlens

# Create apps
fly apps create transferlens-api
fly apps create transferlens-web
fly apps create transferlens-worker
```

### 2. Create Postgres Database

```bash
# Create managed Postgres (recommended)
fly postgres create --name transferlens-db --region lhr

# Attach to API app
fly postgres attach transferlens-db --app transferlens-api

# Get connection string
fly postgres connect -a transferlens-db
```

### 3. Set Secrets

```bash
# API secrets
fly secrets set -a transferlens-api \
  ADMIN_API_KEY="tl-admin-$(openssl rand -hex 16)" \
  CORS_ORIGINS="https://transferlens.io,https://www.transferlens.io" \
  LOG_LEVEL="INFO" \
  ENVIRONMENT="production"

# Web secrets
fly secrets set -a transferlens-web \
  NEXT_PUBLIC_API_URL="https://transferlens-api.fly.dev"

# Worker secrets (attach same DB)
fly postgres attach transferlens-db --app transferlens-worker
```

### 4. Deploy Services

**API (`fly.toml` in apps/api/):**

```toml
# apps/api/fly.toml
app = "transferlens-api"
primary_region = "lhr"

[build]
  dockerfile = "Dockerfile"

[env]
  API_VERSION = "v1"
  LOG_LEVEL = "INFO"

[http_service]
  internal_port = 8000
  force_https = true
  auto_stop_machines = true
  auto_start_machines = true
  min_machines_running = 1

  [http_service.concurrency]
    type = "requests"
    hard_limit = 250
    soft_limit = 200

[[services]]
  protocol = "tcp"
  internal_port = 8000

  [[services.ports]]
    port = 80
    handlers = ["http"]

  [[services.ports]]
    port = 443
    handlers = ["tls", "http"]

  [services.concurrency]
    type = "requests"
    hard_limit = 250
    soft_limit = 200

  [[services.http_checks]]
    interval = "15s"
    timeout = "2s"
    path = "/health"

[checks]
  [checks.health]
    port = 8000
    type = "http"
    interval = "15s"
    timeout = "2s"
    path = "/health"
```

**Web (`fly.toml` in apps/web/):**

```toml
# apps/web/fly.toml
app = "transferlens-web"
primary_region = "lhr"

[build]
  dockerfile = "Dockerfile"

[env]
  NODE_ENV = "production"

[http_service]
  internal_port = 3000
  force_https = true
  auto_stop_machines = true
  auto_start_machines = true
  min_machines_running = 1

[[services]]
  protocol = "tcp"
  internal_port = 3000

  [[services.ports]]
    port = 80
    handlers = ["http"]

  [[services.ports]]
    port = 443
    handlers = ["tls", "http"]

  [[services.http_checks]]
    interval = "15s"
    timeout = "2s"
    path = "/"
```

**Worker (`fly.toml` in apps/worker/):**

```toml
# apps/worker/fly.toml
app = "transferlens-worker"
primary_region = "lhr"

[build]
  dockerfile = "Dockerfile"

[env]
  LOG_LEVEL = "INFO"

# No HTTP service - runs as scheduled task
[processes]
  worker = "python -m worker.cli daily:run --horizon 90"
```

**Deploy:**

```bash
# Deploy API
cd apps/api && fly deploy

# Deploy Web
cd apps/web && fly deploy

# Deploy Worker (run migrations first)
cd apps/worker
fly ssh console -a transferlens-api -C "alembic upgrade head"
fly deploy
```

### 5. Set Up Scheduled Jobs

```bash
# Schedule daily worker run
fly machines run transferlens-worker \
  --schedule "0 6 * * *" \
  --command "python -m worker.cli daily:run --horizon 90"
```

---

## Option 2: Render Deployment

### 1. Create render.yaml

```yaml
# render.yaml
services:
  # API Service
  - type: web
    name: transferlens-api
    env: docker
    dockerfilePath: ./apps/api/Dockerfile
    dockerContext: ./apps/api
    region: frankfurt
    plan: starter
    healthCheckPath: /health
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: transferlens-db
          property: connectionString
      - key: ADMIN_API_KEY
        generateValue: true
      - key: CORS_ORIGINS
        value: https://transferlens.onrender.com
      - key: LOG_LEVEL
        value: INFO
      - key: ENVIRONMENT
        value: production
    autoDeploy: true

  # Web Service
  - type: web
    name: transferlens-web
    env: docker
    dockerfilePath: ./apps/web/Dockerfile
    dockerContext: ./apps/web
    region: frankfurt
    plan: starter
    envVars:
      - key: NEXT_PUBLIC_API_URL
        value: https://transferlens-api.onrender.com
    autoDeploy: true

  # Worker Service (Background)
  - type: worker
    name: transferlens-worker
    env: docker
    dockerfilePath: ./apps/worker/Dockerfile
    dockerContext: ./apps/worker
    region: frankfurt
    plan: starter
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: transferlens-db
          property: connectionString
      - key: LOG_LEVEL
        value: INFO
    autoDeploy: true

  # Cron Job for Daily Pipeline
  - type: cron
    name: transferlens-daily
    env: docker
    dockerfilePath: ./apps/worker/Dockerfile
    dockerContext: ./apps/worker
    schedule: "0 6 * * *"
    region: frankfurt
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: transferlens-db
          property: connectionString
    buildCommand: ""
    startCommand: python -m worker.cli daily:run --horizon 90

databases:
  - name: transferlens-db
    plan: starter
    region: frankfurt
    postgresMajorVersion: 15
```

### 2. Deploy to Render

```bash
# Connect repository and deploy
# 1. Go to https://dashboard.render.com
# 2. New > Blueprint
# 3. Connect your repository
# 4. Render will detect render.yaml and deploy all services
```

### 3. Run Migrations

```bash
# Use Render Shell or SSH
# In API service shell:
alembic upgrade head
```

---

## Database Setup

### Managed Postgres (Recommended)

**Fly.io:**
```bash
fly postgres create --name transferlens-db --region lhr --vm-size shared-cpu-1x
```

**Render:**
- Use the database defined in render.yaml
- Or create manually in dashboard

**Supabase:**
```bash
# Create project at supabase.com
# Connection string: postgresql://postgres:[PASSWORD]@db.[PROJECT].supabase.co:5432/postgres
```

**Neon:**
```bash
# Create project at neon.tech
# Connection string: postgresql://[USER]:[PASSWORD]@[HOST]/[DATABASE]?sslmode=require
```

### Connection Pooling

For production, use connection pooling:

```python
# In apps/api/app/database.py
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800,
)
```

---

## Production Checklist

### Before Deploy

- [ ] Generate strong `ADMIN_API_KEY` (32+ chars)
- [ ] Set `CORS_ORIGINS` to actual domains
- [ ] Configure managed Postgres with backups
- [ ] Set up monitoring/alerting
- [ ] Review rate limiting settings

### After Deploy

- [ ] Run database migrations
- [ ] Seed initial data (if needed)
- [ ] Run first prediction batch
- [ ] Verify health endpoints
- [ ] Test API authentication
- [ ] Check CORS headers
- [ ] Verify OG image generation

### Monitoring

```bash
# Fly.io logs
fly logs -a transferlens-api

# Render logs
# View in dashboard under "Logs" tab

# Check health
curl https://api.transferlens.io/health
```

---

## Scaling

### Horizontal Scaling

**Fly.io:**
```bash
# Scale API to 2 instances
fly scale count 2 -a transferlens-api

# Scale by memory
fly scale memory 512 -a transferlens-api
```

**Render:**
- Upgrade plan in dashboard
- Enable auto-scaling in Pro plan

### Database Scaling

- Upgrade Postgres plan for more connections
- Add read replicas for read-heavy workloads
- Use connection pooler (PgBouncer)

---

## Security Considerations

1. **Secrets Management**
   - Never commit secrets to git
   - Use platform secret management
   - Rotate `ADMIN_API_KEY` periodically

2. **Network Security**
   - Force HTTPS everywhere
   - Restrict database access to app IPs
   - Use private networking where possible

3. **Rate Limiting**
   - Configure appropriate limits
   - Monitor for abuse
   - Consider IP-based blocking

4. **CORS**
   - Only allow specific origins
   - Don't use `*` in production

---

## Troubleshooting

### Common Issues

**Database Connection Failed:**
```bash
# Check connection string
fly ssh console -a transferlens-api
python -c "from app.database import engine; print(engine.connect())"
```

**Migrations Failed:**
```bash
# Run manually
fly ssh console -a transferlens-api
alembic upgrade head
```

**Worker Not Running:**
```bash
# Check logs
fly logs -a transferlens-worker

# Manual run
fly ssh console -a transferlens-worker
python -m worker.cli daily:run
```

---

## Cost Estimates

### Fly.io (Monthly)

| Service | Plan | Cost |
|---------|------|------|
| API (2x shared-cpu-1x) | $3.50/mo each | $7 |
| Web (1x shared-cpu-1x) | $3.50/mo | $3.50 |
| Worker (1x shared-cpu-1x) | $3.50/mo | $3.50 |
| Postgres (1GB) | $7/mo | $7 |
| **Total** | | **~$21/mo** |

### Render (Monthly)

| Service | Plan | Cost |
|---------|------|------|
| API | Starter | $7 |
| Web | Starter | $7 |
| Worker | Starter | $7 |
| Postgres | Starter | $7 |
| **Total** | | **~$28/mo** |

---

## See Also

- [Architecture](./architecture.md) — System design
- [Runbook](./runbook_local.md) — Local development
- [Data Contracts](./data_contracts.md) — Database schema
