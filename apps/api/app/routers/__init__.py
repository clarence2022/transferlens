"""
TransferLens API Routers
========================

All API routers for the TransferLens API.
"""

from app.routers.health import router as health_router
from app.routers.search import router as search_router
from app.routers.players import router as players_router
from app.routers.clubs import router as clubs_router
from app.routers.market import router as market_router
from app.routers.events import router as events_router
from app.routers.admin import router as admin_router

__all__ = [
    "health_router",
    "search_router",
    "players_router",
    "clubs_router",
    "market_router",
    "events_router",
    "admin_router",
]
