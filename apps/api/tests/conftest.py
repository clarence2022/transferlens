"""
Pytest Configuration and Fixtures
=================================

Shared fixtures for API tests.
"""

import asyncio
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import AsyncGenerator
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.config import settings
from app.database import Base, async_session_factory
from app.models import (
    Competition, Club, Player, TransferEvent, SignalEvent, PredictionSnapshot,
    EntityType, SignalTypeEnum, TransferType, FeeType
)
from main import app


# Use a test database URL
TEST_DATABASE_URL = settings.async_database_url


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for each test."""
    async with async_session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Create an async HTTP client for testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture(scope="function")
async def seeded_db(db_session: AsyncSession) -> AsyncSession:
    """
    Seed the database with test data.
    
    Creates:
    - 2 competitions
    - 4 clubs
    - 5 players
    - 3 transfers
    - 20 signals
    - 10 predictions
    """
    # Create competitions
    pl = Competition(
        id=uuid4(),
        name="Premier League",
        short_name="PL",
        country="England",
        tier=1
    )
    la_liga = Competition(
        id=uuid4(),
        name="La Liga",
        short_name="LL",
        country="Spain",
        tier=1
    )
    db_session.add_all([pl, la_liga])
    await db_session.flush()
    
    # Create clubs
    man_city = Club(
        id=uuid4(),
        name="Manchester City",
        short_name="MCI",
        country="England",
        city="Manchester",
        competition_id=pl.id
    )
    arsenal = Club(
        id=uuid4(),
        name="Arsenal",
        short_name="ARS",
        country="England",
        city="London",
        competition_id=pl.id
    )
    real_madrid = Club(
        id=uuid4(),
        name="Real Madrid",
        short_name="RMA",
        country="Spain",
        city="Madrid",
        competition_id=la_liga.id
    )
    barcelona = Club(
        id=uuid4(),
        name="FC Barcelona",
        short_name="BAR",
        country="Spain",
        city="Barcelona",
        competition_id=la_liga.id
    )
    db_session.add_all([man_city, arsenal, real_madrid, barcelona])
    await db_session.flush()
    
    # Create players
    haaland = Player(
        id=uuid4(),
        name="Erling Haaland",
        full_name="Erling Braut Haaland",
        date_of_birth=date(2000, 7, 21),
        nationality="Norway",
        position="ST",
        current_club_id=man_city.id,
        contract_until=date(2027, 6, 30)
    )
    saka = Player(
        id=uuid4(),
        name="Bukayo Saka",
        date_of_birth=date(2001, 9, 5),
        nationality="England",
        position="RW",
        current_club_id=arsenal.id,
        contract_until=date(2027, 6, 30)
    )
    bellingham = Player(
        id=uuid4(),
        name="Jude Bellingham",
        date_of_birth=date(2003, 6, 29),
        nationality="England",
        position="CAM",
        current_club_id=real_madrid.id,
        contract_until=date(2029, 6, 30)
    )
    vinicius = Player(
        id=uuid4(),
        name="Vinicius Junior",
        date_of_birth=date(2000, 7, 12),
        nationality="Brazil",
        position="LW",
        current_club_id=real_madrid.id,
        contract_until=date(2027, 6, 30)
    )
    pedri = Player(
        id=uuid4(),
        name="Pedri",
        full_name="Pedro González López",
        date_of_birth=date(2002, 11, 25),
        nationality="Spain",
        position="CM",
        current_club_id=barcelona.id,
        contract_until=date(2026, 6, 30)
    )
    db_session.add_all([haaland, saka, bellingham, vinicius, pedri])
    await db_session.flush()
    
    # Create transfer events
    now = datetime.utcnow()
    transfers = [
        TransferEvent(
            id=uuid4(),
            event_id=f"TL-20220701-{str(haaland.id)[:8]}-EXTERNAL",
            player_id=haaland.id,
            from_club_id=None,
            to_club_id=man_city.id,
            transfer_type=TransferType.PERMANENT,
            transfer_date=date(2022, 7, 1),
            fee_amount=Decimal("60000000"),
            fee_currency="EUR",
            fee_amount_eur=Decimal("60000000"),
            fee_type=FeeType.CONFIRMED,
            source="official",
            source_confidence=Decimal("1.00")
        ),
        TransferEvent(
            id=uuid4(),
            event_id=f"TL-20230701-{str(bellingham.id)[:8]}-EXTERNAL",
            player_id=bellingham.id,
            from_club_id=None,
            to_club_id=real_madrid.id,
            transfer_type=TransferType.PERMANENT,
            transfer_date=date(2023, 7, 1),
            fee_amount=Decimal("103000000"),
            fee_currency="EUR",
            fee_amount_eur=Decimal("103000000"),
            fee_type=FeeType.CONFIRMED,
            source="official",
            source_confidence=Decimal("1.00")
        ),
    ]
    db_session.add_all(transfers)
    await db_session.flush()
    
    # Create signals
    signals = []
    for player in [haaland, saka, bellingham, vinicius, pedri]:
        # Market value signals
        for days_ago in [0, 7, 14, 30]:
            signals.append(SignalEvent(
                id=uuid4(),
                entity_type=EntityType.PLAYER,
                player_id=player.id,
                signal_type=SignalTypeEnum.MARKET_VALUE,
                value_num=Decimal("100000000") + Decimal(str(days_ago * 1000000)),
                source="transfermarkt",
                confidence=Decimal("0.95"),
                observed_at=now - timedelta(days=days_ago),
                effective_from=now - timedelta(days=days_ago)
            ))
        
        # Contract months remaining
        signals.append(SignalEvent(
            id=uuid4(),
            entity_type=EntityType.PLAYER,
            player_id=player.id,
            signal_type=SignalTypeEnum.CONTRACT_MONTHS_REMAINING,
            value_num=Decimal("24"),
            source="transfermarkt",
            confidence=Decimal("1.00"),
            observed_at=now - timedelta(days=7),
            effective_from=now - timedelta(days=7)
        ))
        signals.append(SignalEvent(
            id=uuid4(),
            entity_type=EntityType.PLAYER,
            player_id=player.id,
            signal_type=SignalTypeEnum.CONTRACT_MONTHS_REMAINING,
            value_num=Decimal("23"),
            source="transfermarkt",
            confidence=Decimal("1.00"),
            observed_at=now,
            effective_from=now
        ))
    
    db_session.add_all(signals)
    await db_session.flush()
    
    # Create predictions
    predictions = []
    for player in [haaland, saka, bellingham]:
        for horizon in [30, 90, 180]:
            predictions.append(PredictionSnapshot(
                id=uuid4(),
                snapshot_id=f"SNAP-{str(player.id)[:8]}-ANY-H{horizon}-{now.strftime('%Y%m%d%H%M%S')}",
                model_version="v1.0.0",
                model_name="transfer_xgb",
                player_id=player.id,
                from_club_id=player.current_club_id,
                to_club_id=None,
                horizon_days=horizon,
                probability=Decimal("0.35") + Decimal(str(horizon / 1000)),
                drivers_json={"contract": 0.3, "form": 0.2},
                as_of=now,
                window_start=now.date(),
                window_end=now.date() + timedelta(days=horizon)
            ))
    
    db_session.add_all(predictions)
    await db_session.commit()
    
    # Store IDs for tests
    db_session.test_data = {
        "competitions": {"pl": pl.id, "la_liga": la_liga.id},
        "clubs": {
            "man_city": man_city.id,
            "arsenal": arsenal.id,
            "real_madrid": real_madrid.id,
            "barcelona": barcelona.id
        },
        "players": {
            "haaland": haaland.id,
            "saka": saka.id,
            "bellingham": bellingham.id,
            "vinicius": vinicius.id,
            "pedri": pedri.id
        }
    }
    
    return db_session
