"""
TransferLens API
================
The Bloomberg Terminal for Football Transfers

Main FastAPI application entry point.
"""

from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from app.config import settings
from app.database import engine, check_database_connection
from app.routers import (
    health_router,
    search_router,
    players_router,
    clubs_router,
    market_router,
    events_router,
    admin_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    print("🚀 TransferLens API starting up...")
    await check_database_connection()
    print("✅ Database connection verified")
    yield
    # Shutdown
    print("👋 TransferLens API shutting down...")
    await engine.dispose()


# OpenAPI tags metadata for better documentation
tags_metadata = [
    {
        "name": "Health",
        "description": "Health check and status endpoints",
    },
    {
        "name": "Search",
        "description": "Unified search across players and clubs",
    },
    {
        "name": "Players",
        "description": "Player profiles, signals, and predictions",
    },
    {
        "name": "Clubs",
        "description": "Club profiles, squads, and transfer activity",
    },
    {
        "name": "Market",
        "description": "Transfer probability table and market data",
    },
    {
        "name": "Events",
        "description": "User event ingestion for analytics and weak signals",
    },
    {
        "name": "Admin",
        "description": "Admin-only endpoints (requires API key)",
    },
]


app = FastAPI(
    title="TransferLens API",
    description="""
## The Bloomberg Terminal for Football Transfers

Real-time transfer intelligence platform built on four data layers:

- **Ledger Layer**: Immutable completed transfers
- **Signals Layer**: Time-stamped signals with provenance
- **Market Layer**: Probability snapshots and model outputs  
- **UX Layer**: User events for weak signal derivation

### Features

- Time-travel queries via `as_of` parameter
- "What Changed" detection for signal deltas
- Ranked search across players and clubs
- Transfer probability table with drivers

### Authentication

Public endpoints require no authentication.
Admin endpoints require `X-API-Key` header.
""",
    version=settings.api_version,
    lifespan=lifespan,
    default_response_class=ORJSONResponse,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    openapi_tags=tags_metadata,
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request timing middleware
@app.middleware("http")
async def add_timing_header(request: Request, call_next):
    """Add X-Response-Time header to all responses."""
    start_time = datetime.utcnow()
    response = await call_next(request)
    process_time = (datetime.utcnow() - start_time).total_seconds() * 1000
    response.headers["X-Response-Time"] = f"{process_time:.2f}ms"
    return response


# Include routers
# Health endpoints at root level
app.include_router(health_router)

# API v1 endpoints
app.include_router(search_router, prefix="/api/v1")
app.include_router(players_router, prefix="/api/v1")
app.include_router(clubs_router, prefix="/api/v1")
app.include_router(market_router, prefix="/api/v1")
app.include_router(events_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")


@app.get("/", response_class=ORJSONResponse)
async def root() -> dict[str, Any]:
    """Root endpoint with API information."""
    return {
        "name": "TransferLens API",
        "version": settings.api_version,
        "description": "The Bloomberg Terminal for Football Transfers",
        "docs": "/docs",
        "health": "/health",
        "api": {
            "search": "/api/v1/search?q=",
            "players": "/api/v1/players/{player_id}",
            "clubs": "/api/v1/clubs/{club_id}",
            "market": "/api/v1/market/latest",
        },
        "timestamp": datetime.utcnow().isoformat(),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
