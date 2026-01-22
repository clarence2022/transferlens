"""
Tests for Admin and Events Endpoints
====================================

Tests for:
- POST /api/v1/events/user
- POST /api/v1/admin/transfer_events
- POST /api/v1/admin/signal_events
- POST /api/v1/admin/rebuild/materialized
"""

import pytest
from httpx import AsyncClient
from datetime import datetime
from uuid import uuid4


# =============================================================================
# EVENTS TESTS
# =============================================================================

@pytest.mark.asyncio
async def test_create_user_event(client: AsyncClient, seeded_db):
    """Test creating a user event."""
    player_id = seeded_db.test_data["players"]["haaland"]
    
    event_data = {
        "user_anon_id": "anon_test123",
        "session_id": "sess_test456",
        "event_type": "player_view",
        "player_id": str(player_id),
        "event_props_json": {
            "page_url": f"/players/{player_id}",
            "referrer": "search"
        }
    }
    
    response = await client.post("/api/v1/events/user", json=event_data)
    assert response.status_code == 201
    
    data = response.json()
    assert data["success"] is True
    assert "event_id" in data


@pytest.mark.asyncio
async def test_create_user_event_minimal(client: AsyncClient):
    """Test creating a user event with minimal data."""
    event_data = {
        "user_anon_id": "anon_test123",
        "session_id": "sess_test456",
        "event_type": "page_view",
    }
    
    response = await client.post("/api/v1/events/user", json=event_data)
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_create_user_event_invalid_type(client: AsyncClient):
    """Test that invalid event type is rejected."""
    event_data = {
        "user_anon_id": "anon_test123",
        "session_id": "sess_test456",
        "event_type": "invalid_type",
    }
    
    response = await client.post("/api/v1/events/user", json=event_data)
    assert response.status_code == 422


# =============================================================================
# ADMIN TESTS - No Auth
# =============================================================================

@pytest.mark.asyncio
async def test_admin_transfer_no_auth(client: AsyncClient, seeded_db):
    """Test that admin endpoints require API key."""
    player_id = seeded_db.test_data["players"]["haaland"]
    club_id = seeded_db.test_data["clubs"]["man_city"]
    
    transfer_data = {
        "player_id": str(player_id),
        "to_club_id": str(club_id),
        "transfer_type": "permanent",
        "transfer_date": "2025-01-15",
        "fee_currency": "EUR",
        "fee_type": "confirmed",
        "source": "test",
        "source_confidence": 1.0
    }
    
    response = await client.post("/api/v1/admin/transfer_events", json=transfer_data)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_signal_no_auth(client: AsyncClient, seeded_db):
    """Test that admin signal endpoint requires API key."""
    player_id = seeded_db.test_data["players"]["haaland"]
    
    signal_data = {
        "entity_type": "player",
        "player_id": str(player_id),
        "signal_type": "market_value",
        "value_num": 150000000,
        "source": "test",
        "confidence": 0.9,
        "observed_at": datetime.utcnow().isoformat(),
        "effective_from": datetime.utcnow().isoformat()
    }
    
    response = await client.post("/api/v1/admin/signal_events", json=signal_data)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_rebuild_no_auth(client: AsyncClient):
    """Test that materialized view refresh requires API key."""
    response = await client.post("/api/v1/admin/rebuild/materialized")
    assert response.status_code == 401


# =============================================================================
# ADMIN TESTS - With Auth
# =============================================================================

ADMIN_HEADERS = {"X-API-Key": "tl-admin-dev-key-change-in-production"}


@pytest.mark.asyncio
async def test_admin_transfer_with_auth(client: AsyncClient, seeded_db):
    """Test creating transfer event with valid API key."""
    player_id = seeded_db.test_data["players"]["saka"]
    from_club_id = seeded_db.test_data["clubs"]["arsenal"]
    to_club_id = seeded_db.test_data["clubs"]["real_madrid"]
    
    transfer_data = {
        "player_id": str(player_id),
        "from_club_id": str(from_club_id),
        "to_club_id": str(to_club_id),
        "transfer_type": "permanent",
        "transfer_date": "2025-07-01",
        "announced_date": "2025-06-15",
        "fee_amount": 80000000,
        "fee_currency": "EUR",
        "fee_type": "confirmed",
        "contract_start": "2025-07-01",
        "contract_end": "2030-06-30",
        "source": "test",
        "source_confidence": 1.0
    }
    
    response = await client.post(
        "/api/v1/admin/transfer_events",
        json=transfer_data,
        headers=ADMIN_HEADERS
    )
    assert response.status_code == 201
    
    data = response.json()
    assert "event_id" in data
    assert data["player_id"] == str(player_id)
    assert data["is_superseded"] is False


@pytest.mark.asyncio
async def test_admin_signal_with_auth(client: AsyncClient, seeded_db):
    """Test creating signal event with valid API key."""
    player_id = seeded_db.test_data["players"]["bellingham"]
    
    signal_data = {
        "entity_type": "player",
        "player_id": str(player_id),
        "signal_type": "market_value",
        "value_num": 200000000,
        "source": "test",
        "confidence": 0.95,
        "observed_at": datetime.utcnow().isoformat(),
        "effective_from": datetime.utcnow().isoformat()
    }
    
    response = await client.post(
        "/api/v1/admin/signal_events",
        json=signal_data,
        headers=ADMIN_HEADERS
    )
    assert response.status_code == 201
    
    data = response.json()
    assert data["player_id"] == str(player_id)
    assert data["signal_type"] == "market_value"


@pytest.mark.asyncio
async def test_admin_signal_entity_validation(client: AsyncClient, seeded_db):
    """Test that signal entity type validation works."""
    player_id = seeded_db.test_data["players"]["bellingham"]
    club_id = seeded_db.test_data["clubs"]["real_madrid"]
    
    # Player signal with club_id should fail
    signal_data = {
        "entity_type": "player",
        "player_id": str(player_id),
        "club_id": str(club_id),  # Should not be present for player signal
        "signal_type": "market_value",
        "value_num": 200000000,
        "source": "test",
        "confidence": 0.95,
        "observed_at": datetime.utcnow().isoformat(),
        "effective_from": datetime.utcnow().isoformat()
    }
    
    response = await client.post(
        "/api/v1/admin/signal_events",
        json=signal_data,
        headers=ADMIN_HEADERS
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_admin_invalid_api_key(client: AsyncClient, seeded_db):
    """Test that invalid API key is rejected."""
    player_id = seeded_db.test_data["players"]["haaland"]
    
    signal_data = {
        "entity_type": "player",
        "player_id": str(player_id),
        "signal_type": "market_value",
        "value_num": 150000000,
        "source": "test",
        "confidence": 0.9,
        "observed_at": datetime.utcnow().isoformat(),
        "effective_from": datetime.utcnow().isoformat()
    }
    
    response = await client.post(
        "/api/v1/admin/signal_events",
        json=signal_data,
        headers={"X-API-Key": "invalid-key"}
    )
    assert response.status_code == 403
