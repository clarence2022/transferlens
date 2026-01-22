# Environment Variables Reference

Complete reference for all environment variables used by TransferLens services.

---

## Quick Start

Create a `.env` file in each service directory with the required variables.

### Minimal Production Setup

```bash
# API (.env)
DATABASE_URL=postgresql://user:pass@host:5432/transferlens?sslmode=require
ADMIN_API_KEY=tl-admin-prod-$(openssl rand -hex 16)
CORS_ORIGINS=https://transferlens.io,https://www.transferlens.io
ENVIRONMENT=production

# Web (.env)
NEXT_PUBLIC_API_URL=https://api.transferlens.io

# Worker (.env)
DATABASE_URL=postgresql://user:pass@host:5432/transferlens?sslmode=require
```

---

## API Service

### Required

| Variable | Type | Description |
|----------|------|-------------|
| `DATABASE_URL` | string | PostgreSQL connection string |
| `ADMIN_API_KEY` | string | Authentication key for admin endpoints |

### Optional

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `ENVIRONMENT` | string | `development` | Environment name (`development`, `production`) |
| `LOG_LEVEL` | string | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `CORS_ORIGINS` | string | `http://localhost:3000` | Comma-separated allowed CORS origins |
| `REDIS_URL` | string | - | Redis connection for caching/rate limiting |
| `RATE_LIMIT_ENABLED` | bool | `true` | Enable/disable rate limiting |
| `RATE_LIMIT_REQUESTS` | int | `100` | Requests allowed per window |
| `RATE_LIMIT_WINDOW` | int | `60` | Rate limit window in seconds |
| `RATE_LIMIT_BURST` | int | `150` | Maximum burst requests |
| `DB_POOL_SIZE` | int | `5` | Database connection pool size |
| `DB_MAX_OVERFLOW` | int | `10` | Max overflow connections |
| `DEFAULT_PAGE_SIZE` | int | `20` | Default pagination size |
| `MAX_PAGE_SIZE` | int | `100` | Maximum pagination size |

### Examples

```bash
# Development
DATABASE_URL=postgresql://transferlens:dev@localhost:5432/transferlens
ADMIN_API_KEY=tl-admin-dev-key
CORS_ORIGINS=http://localhost:3000,http://localhost:8000
ENVIRONMENT=development
LOG_LEVEL=DEBUG

# Production
DATABASE_URL=postgresql://user:pass@db.example.com:5432/transferlens?sslmode=require
ADMIN_API_KEY=tl-admin-prod-a1b2c3d4e5f6g7h8i9j0
CORS_ORIGINS=https://transferlens.io,https://www.transferlens.io
ENVIRONMENT=production
LOG_LEVEL=INFO
RATE_LIMIT_REQUESTS=60
RATE_LIMIT_WINDOW=60
```

---

## Web Service

### Required

| Variable | Type | Description |
|----------|------|-------------|
| `NEXT_PUBLIC_API_URL` | string | API base URL (used by client) |

### Optional

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `NEXT_PUBLIC_SITE_URL` | string | - | Site URL for OG images |
| `NODE_ENV` | string | `development` | Node environment |

### Notes

- Variables prefixed with `NEXT_PUBLIC_` are exposed to the browser
- Set these at **build time** for static generation
- The API URL must be accessible from user browsers (not internal URLs)

### Examples

```bash
# Development
NEXT_PUBLIC_API_URL=http://localhost:8000

# Production
NEXT_PUBLIC_API_URL=https://api.transferlens.io
NEXT_PUBLIC_SITE_URL=https://transferlens.io
```

---

## Worker Service

### Required

| Variable | Type | Description |
|----------|------|-------------|
| `DATABASE_URL` | string | PostgreSQL connection string |

### Optional

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `REDIS_URL` | string | - | Redis connection for job queue |
| `MODEL_STORAGE_PATH` | string | `/app/models` | Path for model artifacts |
| `LOG_LEVEL` | string | `INFO` | Logging level |
| `CANDIDATE_CLUBS_PER_PLAYER` | int | `20` | Max candidate destinations |
| `MIN_TRAINING_SAMPLES` | int | `50` | Minimum samples for training |
| `TEST_SIZE` | float | `0.2` | Train/test split ratio |
| `RANDOM_STATE` | int | `42` | Random seed for reproducibility |

### Examples

```bash
# Development
DATABASE_URL=postgresql://transferlens:dev@localhost:5432/transferlens
MODEL_STORAGE_PATH=./models
LOG_LEVEL=DEBUG

# Production
DATABASE_URL=postgresql://user:pass@db.example.com:5432/transferlens?sslmode=require
MODEL_STORAGE_PATH=/app/models
LOG_LEVEL=INFO
```

---

## Database Configuration

### Connection String Format

```
postgresql://[user]:[password]@[host]:[port]/[database]?[options]
```

### Options

| Option | Description |
|--------|-------------|
| `sslmode=require` | Require SSL (recommended for production) |
| `sslmode=verify-full` | Verify SSL certificate |
| `connect_timeout=10` | Connection timeout in seconds |
| `application_name=transferlens` | Application identifier |

### Examples by Provider

```bash
# Local development
DATABASE_URL=postgresql://transferlens:dev@localhost:5432/transferlens

# Fly.io Postgres
DATABASE_URL=postgres://postgres:password@transferlens-db.internal:5432/postgres?sslmode=disable

# Neon
DATABASE_URL=postgresql://user:pass@ep-xxx.us-east-2.aws.neon.tech/neondb?sslmode=require

# Supabase
DATABASE_URL=postgresql://postgres:pass@db.xxx.supabase.co:5432/postgres?sslmode=require

# Render
DATABASE_URL=postgresql://user:pass@dpg-xxx.oregon-postgres.render.com/transferlens

# AWS RDS
DATABASE_URL=postgresql://user:pass@xxx.us-east-1.rds.amazonaws.com:5432/transferlens?sslmode=require
```

---

## Security Best Practices

### Generating Secrets

```bash
# Generate ADMIN_API_KEY
openssl rand -hex 32
# or
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Generate SECRET_KEY
openssl rand -base64 32
```

### Secret Management

**Development:**
- Use `.env` files (add to `.gitignore`)
- Never commit secrets to git

**Production:**
- Use platform secret management:
  - Fly.io: `fly secrets set VAR=value`
  - Render: Dashboard → Environment
  - AWS: Secrets Manager or Parameter Store
  - Kubernetes: Secrets or external-secrets

### CORS Configuration

```bash
# Bad - allows all origins
CORS_ORIGINS=*

# Good - specific origins only
CORS_ORIGINS=https://transferlens.io,https://www.transferlens.io

# Development - localhost only
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

---

## Validation

### Check Required Variables

```python
# Python script to validate environment
import os
import sys

required_vars = {
    'api': ['DATABASE_URL', 'ADMIN_API_KEY'],
    'web': ['NEXT_PUBLIC_API_URL'],
    'worker': ['DATABASE_URL'],
}

service = sys.argv[1] if len(sys.argv) > 1 else 'api'

missing = [v for v in required_vars.get(service, []) if not os.getenv(v)]

if missing:
    print(f"Missing required variables: {missing}")
    sys.exit(1)
else:
    print("All required variables set ✓")
```

### Test Database Connection

```bash
# Using psql
psql "$DATABASE_URL" -c "SELECT 1"

# Using Python
python -c "
from sqlalchemy import create_engine
import os
engine = create_engine(os.environ['DATABASE_URL'])
with engine.connect() as conn:
    print('Connected successfully')
"
```
