# Fly.io Deployment

Deploy TransferLens to Fly.io's global edge network.

## Prerequisites

```bash
# Install Fly CLI
curl -L https://fly.io/install.sh | sh

# Login
fly auth login

# Create organization (if needed)
fly orgs create transferlens
```

## Quick Deploy

```bash
# From project root
cd transferlens

# Deploy all services
fly deploy -c infra/fly/api.toml
fly deploy -c infra/fly/web.toml
fly deploy -c infra/fly/worker.toml
```

## Step-by-Step Setup

### 1. Create Postgres Database

```bash
# Create Fly Postgres cluster
fly postgres create \
  --name transferlens-db \
  --region lhr \
  --vm-size shared-cpu-1x \
  --initial-cluster-size 1 \
  --volume-size 10

# Get connection string
fly postgres connect -a transferlens-db

# Or use external (Neon, Supabase)
# Just set DATABASE_URL in secrets
```

### 2. Create Apps

```bash
# Create API app
fly apps create transferlens-api

# Create Web app  
fly apps create transferlens-web

# Create Worker app
fly apps create transferlens-worker
```

### 3. Set Secrets

```bash
# API secrets
fly secrets set -a transferlens-api \
  DATABASE_URL="postgres://..." \
  ADMIN_API_KEY="$(openssl rand -base64 32)" \
  CORS_ORIGINS="https://transferlens.io,https://www.transferlens.io"

# Web secrets
fly secrets set -a transferlens-web \
  NEXT_PUBLIC_API_URL="https://transferlens-api.fly.dev"

# Worker secrets
fly secrets set -a transferlens-worker \
  DATABASE_URL="postgres://..."
```

### 4. Deploy Services

```bash
# Deploy API
fly deploy -a transferlens-api -c infra/fly/api.toml

# Deploy Web
fly deploy -a transferlens-web -c infra/fly/web.toml

# Deploy Worker
fly deploy -a transferlens-worker -c infra/fly/worker.toml
```

### 5. Run Migrations

```bash
# SSH into API and run migrations
fly ssh console -a transferlens-api
> alembic upgrade head
> exit
```

### 6. Seed Data

```bash
# SSH into worker
fly ssh console -a transferlens-worker
> python -m worker.cli ingest:demo --force
> python -m worker.cli daily:run
> exit
```

### 7. Custom Domain

```bash
# Add custom domain
fly certs create transferlens.io -a transferlens-web
fly certs create api.transferlens.io -a transferlens-api

# Update DNS (add CNAME records)
# transferlens.io -> transferlens-web.fly.dev
# api.transferlens.io -> transferlens-api.fly.dev
```

## Configuration Files

### API (`infra/fly/api.toml`)

```toml
app = "transferlens-api"
primary_region = "lhr"

[build]
  dockerfile = "apps/api/Dockerfile"

[env]
  API_LOG_LEVEL = "INFO"
  API_RATE_LIMIT = "60"
  API_RATE_LIMIT_BURST = "100"

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

[[http_service.checks]]
  grace_period = "10s"
  interval = "30s"
  method = "GET"
  path = "/health"
  timeout = "5s"

[[vm]]
  cpu_kind = "shared"
  cpus = 1
  memory_mb = 512
```

### Web (`infra/fly/web.toml`)

```toml
app = "transferlens-web"
primary_region = "lhr"

[build]
  dockerfile = "apps/web/Dockerfile"

[http_service]
  internal_port = 3000
  force_https = true
  auto_stop_machines = true
  auto_start_machines = true
  min_machines_running = 1

  [http_service.concurrency]
    type = "requests"
    hard_limit = 250
    soft_limit = 200

[[vm]]
  cpu_kind = "shared"
  cpus = 1
  memory_mb = 512
```

### Worker (`infra/fly/worker.toml`)

```toml
app = "transferlens-worker"
primary_region = "lhr"

[build]
  dockerfile = "apps/worker/Dockerfile"

[env]
  WORKER_LOG_LEVEL = "INFO"

# No HTTP service - worker only
[processes]
  worker = "python -m worker.cli daily:run"

[[vm]]
  cpu_kind = "shared"
  cpus = 1
  memory_mb = 1024
```

## Scheduled Jobs

Fly.io doesn't have built-in cron, so use one of:

### Option A: fly-cron (External Service)

```bash
# Use GitHub Actions or external cron
# See .github/workflows/daily-pipeline.yml
```

### Option B: Fly Machine API

```bash
# Schedule machine to run daily
fly machine run transferlens-worker \
  --schedule "0 6 * * *" \
  --command "python -m worker.cli daily:run"
```

### Option C: Always-on Worker with Sleep

```python
# In worker entrypoint
import schedule
import time

schedule.every().day.at("06:00").do(run_daily_pipeline)

while True:
    schedule.run_pending()
    time.sleep(60)
```

## Scaling

```bash
# Scale API horizontally
fly scale count 2 -a transferlens-api

# Scale memory
fly scale memory 1024 -a transferlens-api

# Scale to different regions
fly regions add iad -a transferlens-api
```

## Monitoring

```bash
# View logs
fly logs -a transferlens-api

# Check status
fly status -a transferlens-api

# Dashboard
fly dashboard -a transferlens-api
```

## Costs (Estimated)

| Service | Config | Monthly |
|---------|--------|---------|
| API | shared-cpu-1x, 512MB | ~$3 |
| Web | shared-cpu-1x, 512MB | ~$3 |
| Worker | shared-cpu-1x, 1GB | ~$5 |
| Postgres | 10GB | ~$0 (free tier) |
| **Total** | | **~$11/mo** |

## Troubleshooting

### App won't start

```bash
# Check logs
fly logs -a transferlens-api

# SSH in and debug
fly ssh console -a transferlens-api
```

### Database connection issues

```bash
# Verify connection string
fly secrets list -a transferlens-api

# Test connection
fly ssh console -a transferlens-api
> python -c "from app.database import engine; print(engine.url)"
```

### Out of memory

```bash
# Increase memory
fly scale memory 1024 -a transferlens-api
```
