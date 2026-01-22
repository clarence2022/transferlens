# Render Deployment

Deploy TransferLens to Render with automatic GitHub integration.

## Prerequisites

1. GitHub account with repo access
2. Render account (free tier available)

## Quick Deploy

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

Or use the Blueprint below.

## Blueprint Deployment

### 1. Create `render.yaml`

Already provided at `infra/render/render.yaml`

### 2. Connect GitHub

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click "New" → "Blueprint"
3. Connect your GitHub repository
4. Select the repo and branch
5. Review services and click "Apply"

### 3. Configure Secrets

After deployment, set secrets in Render dashboard:

**API Service:**
- `ADMIN_API_KEY`: Generate with `openssl rand -base64 32`

**Web Service:**
- `NEXT_PUBLIC_API_URL`: Your API URL (e.g., `https://transferlens-api.onrender.com`)

## Manual Setup

### 1. Create Database

1. Dashboard → New → PostgreSQL
2. Name: `transferlens-db`
3. Region: Oregon (or closest)
4. Plan: Free (or Starter for production)
5. Create Database

Copy the **Internal Database URL** for services.

### 2. Create API Service

1. Dashboard → New → Web Service
2. Connect repository
3. Configure:
   - Name: `transferlens-api`
   - Root Directory: `apps/api`
   - Runtime: Docker
   - Region: Same as database
   - Plan: Free (or Starter)

4. Environment Variables:
   ```
   DATABASE_URL=<internal-db-url>
   ADMIN_API_KEY=<your-secret-key>
   CORS_ORIGINS=https://transferlens-web.onrender.com
   API_LOG_LEVEL=INFO
   API_RATE_LIMIT=60
   ```

5. Health Check Path: `/health`

### 3. Create Web Service

1. Dashboard → New → Web Service
2. Connect repository
3. Configure:
   - Name: `transferlens-web`
   - Root Directory: `apps/web`
   - Runtime: Docker
   - Plan: Free (or Starter)

4. Environment Variables:
   ```
   NEXT_PUBLIC_API_URL=https://transferlens-api.onrender.com
   ```

### 4. Create Worker Service

1. Dashboard → New → Background Worker
2. Connect repository
3. Configure:
   - Name: `transferlens-worker`
   - Root Directory: `apps/worker`
   - Runtime: Docker
   - Plan: Starter (Background Workers need paid plan)

4. Environment Variables:
   ```
   DATABASE_URL=<internal-db-url>
   ```

### 5. Create Cron Job

1. Dashboard → New → Cron Job
2. Connect repository
3. Configure:
   - Name: `transferlens-daily`
   - Root Directory: `apps/worker`
   - Runtime: Docker
   - Schedule: `0 6 * * *` (daily at 6am UTC)
   - Command: `python -m worker.cli daily:run`

## Configuration Files

### `render.yaml` Blueprint

```yaml
# See infra/render/render.yaml
databases:
  - name: transferlens-db
    plan: free
    region: oregon

services:
  - type: web
    name: transferlens-api
    runtime: docker
    dockerfilePath: ./apps/api/Dockerfile
    dockerContext: .
    region: oregon
    plan: free
    healthCheckPath: /health
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: transferlens-db
          property: connectionString
      - key: ADMIN_API_KEY
        generateValue: true
      - key: CORS_ORIGINS
        value: https://transferlens-web.onrender.com
      - key: API_LOG_LEVEL
        value: INFO
      - key: API_RATE_LIMIT
        value: "60"

  - type: web
    name: transferlens-web
    runtime: docker
    dockerfilePath: ./apps/web/Dockerfile
    dockerContext: .
    region: oregon
    plan: free
    envVars:
      - key: NEXT_PUBLIC_API_URL
        value: https://transferlens-api.onrender.com

  - type: worker
    name: transferlens-worker
    runtime: docker
    dockerfilePath: ./apps/worker/Dockerfile
    dockerContext: .
    region: oregon
    plan: starter
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: transferlens-db
          property: connectionString

  - type: cron
    name: transferlens-daily
    runtime: docker
    dockerfilePath: ./apps/worker/Dockerfile
    dockerContext: .
    region: oregon
    schedule: "0 6 * * *"
    dockerCommand: python -m worker.cli daily:run
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: transferlens-db
          property: connectionString
```

## Post-Deployment

### Run Migrations

```bash
# Via Render Shell (Dashboard → Service → Shell)
alembic upgrade head
```

### Seed Data

```bash
# Via Render Shell on worker
python -m worker.cli ingest:demo --force
python -m worker.cli daily:run
```

### Custom Domain

1. Dashboard → Service → Settings → Custom Domains
2. Add domain (e.g., `transferlens.io`)
3. Configure DNS:
   - Add CNAME record pointing to `*.onrender.com`
4. Wait for SSL certificate (automatic)

## Scaling

### Vertical Scaling

Upgrade service plan:
- Free → Starter → Standard → Pro

### Horizontal Scaling

1. Dashboard → Service → Settings
2. Increase instance count
3. Note: Only available on paid plans

## Monitoring

### Built-in Features

- Logs: Dashboard → Service → Logs
- Metrics: Dashboard → Service → Metrics
- Alerts: Dashboard → Service → Settings → Notifications

### External Monitoring

Add to environment:
```
SENTRY_DSN=https://xxx@sentry.io/xxx
```

## Costs (Estimated)

| Service | Plan | Monthly |
|---------|------|---------|
| API | Free | $0 |
| Web | Free | $0 |
| Worker | Starter | $7 |
| Cron | Starter | $7 |
| Database | Free | $0 |
| **Total** | | **$14/mo** |

**Production (Starter plans):**

| Service | Plan | Monthly |
|---------|------|---------|
| API | Starter | $7 |
| Web | Starter | $7 |
| Worker | Starter | $7 |
| Cron | Starter | $7 |
| Database | Starter | $7 |
| **Total** | | **$35/mo** |

## Troubleshooting

### Service won't start

1. Check build logs: Dashboard → Service → Events
2. Check runtime logs: Dashboard → Service → Logs
3. Verify environment variables

### Database connection issues

1. Ensure using **Internal** Database URL
2. Check database is in same region
3. Verify DATABASE_URL format

### Slow cold starts

Free tier services spin down after 15 minutes of inactivity.
- Upgrade to Starter plan for always-on
- Or use uptime monitoring to keep warm

### Build failures

1. Check Dockerfile path is correct
2. Ensure Docker context includes all needed files
3. Check build logs for specific errors
