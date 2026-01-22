"""
Health Check Router
===================

Provides health, readiness, and liveness endpoints.
"""

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.config import settings
from app.schemas import HealthResponse, ReadyResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    """
    Health check endpoint.
    
    Returns status of all dependencies including database and redis.
    """
    db_status = "healthy"
    redis_status = "healthy"
    
    # Check database
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "unhealthy"
    
    # Check Redis (optional - might not be configured)
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.redis_url)
        await r.ping()
        await r.close()
    except Exception:
        redis_status = "unavailable"
    
    overall_status = "healthy" if db_status == "healthy" else "degraded"
    
    return HealthResponse(
        status=overall_status,
        version=settings.api_version,
        timestamp=datetime.utcnow(),
        database=db_status,
        redis=redis_status,
        environment=settings.environment
    )


@router.get("/ready", response_model=ReadyResponse)
async def readiness_check(db: AsyncSession = Depends(get_db)) -> ReadyResponse:
    """
    Kubernetes readiness probe.
    
    Returns true only if all critical dependencies are available.
    """
    checks = {}
    
    # Check database
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        checks["database"] = False
    
    ready = all(checks.values())
    
    return ReadyResponse(ready=ready, checks=checks)


@router.get("/live")
async def liveness_check() -> dict:
    """
    Kubernetes liveness probe.
    
    Simple check that the service is responding.
    """
    return {"alive": True}
