# TransferLens Deployment Guide

This guide covers deploying TransferLens to production using containerized services.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              INTERNET                                    │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
                    ▼               ▼               ▼
            ┌───────────┐   ┌───────────┐   ┌───────────┐
            │    Web    │   │    API    │   │   API     │
            │  (Next.js)│   │ (FastAPI) │   │  (replica)│
            │   :3000   │   │   :8000   │   │   :8000   │
            └───────────┘   └───────────┘   └───────────┘
                    │               │               │
                    │               └───────┬───────┘
                    │                       │
                    ▼                       ▼
            ┌───────────────────────────────────────────┐
            │              Managed Postgres              │
            │           (Neon / Supabase / RDS)          │
            └───────────────────────────────────────────┘
                                    ▲
                                    │
                            ┌───────────┐
                            │   Worker  │
                            │  (cron)   │
                            └───────────┘
```

## Container Services

| Service | Purpose | Scaling |
|---------|---------|---------|
| **API** | REST API, handles all reads/writes | Horizontal (2-4 instances) |
| **Web** | Next.js frontend | Horizontal (1-2 instances) |
| **Worker** | Background jobs, ML pipeline | Single instance (scheduled) |

## Deployment Options

### Recommended: Fly.io

See [fly.io deployment guide](./fly.md)

**Pros:**
- Simple CLI deployment
- Global edge network
- Built-in Postgres (or use external)
- Generous free tier

### Alternative: Render

See [render.com deployment guide](./render.md)

**Pros:**
- Easy GitHub integration
- Managed Postgres included
- Auto-scaling
- Good free tier

### Alternative: Railway

Similar to Render, supports monorepos well.

### Enterprise: AWS/GCP/Azure

For larger deployments, use:
- ECS/Cloud Run/AKS for containers
- RDS/Cloud SQL/Azure Database for Postgres
- ElastiCache/Memorystore for Redis (optional)

---

## Environment Variables

### Required for All Services

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | Postgres connection string | `postgresql://user:pass@host:5432/db?sslmode=require` |

### API Service

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | Postgres connection | Required |
| `REDIS_URL` | Redis connection (optional) | `redis://localhost:6379` |
| `ADMIN_API_KEY` | Admin endpoint authentication | Required in production |
| `CORS_ORIGINS` | Allowed CORS origins | `https://transferlens.io` |
| `API_LOG_LEVEL` | Logging level | `INFO` |
| `API_RATE_LIMIT` | Requests per minute | `60` |
| `API_RATE_LIMIT_BURST` | Burst limit | `100` |

### Web Service

| Variable | Description | Example |
|----------|-------------|---------|
| `NEXT_PUBLIC_API_URL` | API base URL | `https://api.transferlens.io` |
| `NEXT_PUBLIC_SITE_URL` | Site URL for OG images | `https://transferlens.io` |

### Worker Service

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | Postgres connection | Required |
| `REDIS_URL` | Redis connection | Optional |
| `MODEL_STORAGE_PATH` | Model artifact path | `/app/models` |
| `WORKER_LOG_LEVEL` | Logging level | `INFO` |

---

## Database

### Managed Postgres Recommendations

| Provider | Plan | Cost | Notes |
|----------|------|------|-------|
| **Neon** | Free tier | $0 | Serverless, auto-suspend |
| **Supabase** | Free tier | $0 | 500MB, good dashboard |
| **Render** | Starter | $7/mo | Simple, integrated |
| **Fly.io** | Postgres | $0+ | Collocated, fast |
| **AWS RDS** | db.t3.micro | ~$15/mo | Production-grade |

### Required Extensions

```sql
-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable pg_trgm for fuzzy search
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

### Connection Pooling

For serverless/scaled deployments, use connection pooling:

- **PgBouncer** (self-hosted)
- **Neon** (built-in)
- **Supabase** (built-in pooler)

---

## Security Checklist

### Before Launch

- [ ] `ADMIN_API_KEY` is a strong random string (32+ chars)
- [ ] `DATABASE_URL` uses SSL (`?sslmode=require`)
- [ ] `CORS_ORIGINS` is set to production domain only
- [ ] Rate limiting is enabled
- [ ] Request logging excludes sensitive data
- [ ] Secrets are in environment variables, not code

### API Security

```python
# Example: Generate secure admin key
import secrets
print(secrets.token_urlsafe(32))
# Output: xK9mN2pQ3rS4tU5vW6xY7zA8bC9dE0fG
```

---

## Monitoring

### Health Checks

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Basic liveness check |
| `GET /ready` | Readiness (DB connected) |

### Recommended Monitoring

- **Uptime**: Fly.io built-in, UptimeRobot, Pingdom
- **Errors**: Sentry (free tier available)
- **Metrics**: Prometheus + Grafana, or Fly.io metrics

---

## Scaling Guidelines

### API

| Traffic | Instances | Memory |
|---------|-----------|--------|
| Low (<100 req/min) | 1 | 256MB |
| Medium (<1K req/min) | 2 | 512MB |
| High (<10K req/min) | 4 | 1GB |

### Web

| Traffic | Instances | Memory |
|---------|-----------|--------|
| Low | 1 | 256MB |
| Medium | 2 | 512MB |
| High | 2-4 | 512MB |

### Worker

Single instance, scheduled execution:
- `signals:derive` - Every hour
- `candidates:generate` - Daily
- `predict:run` - Daily
- `model:train` - Weekly

---

## Quick Deploy Checklist

1. **Create Managed Postgres**
   - Get `DATABASE_URL` with SSL
   - Run migrations

2. **Deploy API**
   - Set environment variables
   - Verify `/health` endpoint

3. **Deploy Web**
   - Set `NEXT_PUBLIC_API_URL`
   - Verify pages load

4. **Deploy Worker**
   - Set `DATABASE_URL`
   - Run initial data load
   - Set up scheduled jobs

5. **DNS & SSL**
   - Point domain to services
   - Verify HTTPS works

6. **Monitoring**
   - Set up health check alerts
   - Configure error tracking

---

## See Also

- [Fly.io Deployment](./fly.md)
- [Render Deployment](./render.md)
- [Environment Variables Reference](./env-vars.md)
