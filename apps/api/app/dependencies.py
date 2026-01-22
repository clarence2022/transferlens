"""
FastAPI Dependencies
====================

Common dependencies for dependency injection.
"""

from typing import AsyncGenerator, Optional
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.config import settings


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session."""
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_admin_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key")
) -> str:
    """Verify admin API key for protected endpoints."""
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key header (X-API-Key)"
        )
    
    # Simple API key check - in production, use proper secret management
    if x_api_key != settings.admin_api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key"
        )
    
    return x_api_key


# Type alias for cleaner annotations
DbSession = AsyncSession
