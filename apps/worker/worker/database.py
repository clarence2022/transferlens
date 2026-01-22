"""
Database Connection
===================

Provides both sync and async database connections for the worker.
Sync is used for pandas operations, async for efficient bulk operations.
"""

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from worker.config import settings


# =============================================================================
# SYNC ENGINE (for pandas, sklearn)
# =============================================================================

sync_engine = create_engine(
    settings.sync_database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    echo=False,
)

SyncSessionLocal = sessionmaker(
    bind=sync_engine,
    autocommit=False,
    autoflush=False,
)


@contextmanager
def get_sync_session() -> Generator[Session, None, None]:
    """Get a synchronous database session."""
    session = SyncSessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_sync_connection():
    """Get a raw database connection for pandas."""
    return sync_engine.connect()


# =============================================================================
# ASYNC ENGINE (optional, for bulk operations)
# =============================================================================

async_database_url = settings.database_url.replace(
    "postgresql://", "postgresql+asyncpg://"
)

async_engine = create_async_engine(
    async_database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_async_session() -> AsyncSession:
    """Get an async database session."""
    async with AsyncSessionLocal() as session:
        yield session


# =============================================================================
# HEALTH CHECK
# =============================================================================

def check_database_connection() -> bool:
    """Check if database is accessible."""
    try:
        with get_sync_session() as session:
            session.execute(text("SELECT 1"))
        return True
    except Exception as e:
        print(f"Database connection failed: {e}")
        return False
