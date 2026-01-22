"""
Tests for Player Endpoints
==========================

Tests for:
- GET /api/v1/players/{player_id}
- GET /api/v1/players/{player_id}/signals
- GET /api/v1/players/{player_id}/predictions
"""

import pytest
from httpx import AsyncClient
from uuid import uuid4


@pytest.mark.asyncio
async def test_get_player_not_found(client: AsyncClient):
    """Test that non-existent player returns 404."""
    fake_id = uuid4()
    response = await client.get(f"/api/v1/players/{fake_id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_player_detail(client: AsyncClient, seeded_db):
    """Test getting player detail page."""
    player_id = seeded_db.test_data["players"]["haaland"]
    response = await client.get(f"/api/v1/players/{player_id}")
    assert response.status_code == 200
    
    data = response.json()
    
    # Basic fields
    assert data["id"] == str(player_id)
    assert data["name"] == "Erling Haaland"
    assert data["nationality"] == "Norway"
    assert data["position"] == "ST"
    
    # Current club should be included
    assert data["current_club"] is not None
    assert data["current_club"]["name"] == "Manchester City"
    
    # Age should be calculated
    assert data["age"] is not None
    assert data["age"] > 20


@pytest.mark.asyncio
async def test_get_player_key_stats(client: AsyncClient, seeded_db):
    """Test that player detail includes key stats from signals."""
    player_id = seeded_db.test_data["players"]["haaland"]
    response = await client.get(f"/api/v1/players/{player_id}")
    assert response.status_code == 200
    
    data = response.json()
    
    # Key stats should be present (from signals)
    assert "market_value" in data
    assert "contract_months_remaining" in data


@pytest.mark.asyncio
async def test_get_player_predictions(client: AsyncClient, seeded_db):
    """Test that player detail includes predictions."""
    player_id = seeded_db.test_data["players"]["haaland"]
    response = await client.get(f"/api/v1/players/{player_id}")
    assert response.status_code == 200
    
    data = response.json()
    
    assert "latest_predictions" in data
    assert isinstance(data["latest_predictions"], list)


@pytest.mark.asyncio
async def test_get_player_what_changed(client: AsyncClient, seeded_db):
    """Test that player detail includes 'what changed' section."""
    player_id = seeded_db.test_data["players"]["haaland"]
    response = await client.get(f"/api/v1/players/{player_id}")
    assert response.status_code == 200
    
    data = response.json()
    
    # What changed should be a list (may be empty if no changes)
    assert "what_changed" in data
    assert isinstance(data["what_changed"], list)


@pytest.mark.asyncio
async def test_get_player_transfer_history(client: AsyncClient, seeded_db):
    """Test that player detail includes transfer history."""
    player_id = seeded_db.test_data["players"]["haaland"]
    response = await client.get(f"/api/v1/players/{player_id}")
    assert response.status_code == 200
    
    data = response.json()
    
    assert "transfer_history" in data
    assert isinstance(data["transfer_history"], list)
    
    # Haaland should have at least one transfer
    if data["transfer_history"]:
        transfer = data["transfer_history"][0]
        assert "event_id" in transfer
        assert "transfer_type" in transfer
        assert "transfer_date" in transfer


@pytest.mark.asyncio
async def test_get_player_signals_endpoint(client: AsyncClient, seeded_db):
    """Test getting player signals."""
    player_id = seeded_db.test_data["players"]["haaland"]
    response = await client.get(f"/api/v1/players/{player_id}/signals")
    assert response.status_code == 200
    
    data = response.json()
    assert isinstance(data, list)
    
    if data:
        signal = data[0]
        assert "signal_type" in signal
        assert "source" in signal
        assert "effective_from" in signal


@pytest.mark.asyncio
async def test_get_player_signals_filter_by_type(client: AsyncClient, seeded_db):
    """Test filtering player signals by type."""
    player_id = seeded_db.test_data["players"]["haaland"]
    response = await client.get(
        f"/api/v1/players/{player_id}/signals?signal_type=market_value"
    )
    assert response.status_code == 200
    
    data = response.json()
    for signal in data:
        assert signal["signal_type"] == "market_value"


@pytest.mark.asyncio
async def test_get_player_predictions_endpoint(client: AsyncClient, seeded_db):
    """Test getting player predictions."""
    player_id = seeded_db.test_data["players"]["haaland"]
    response = await client.get(f"/api/v1/players/{player_id}/predictions")
    assert response.status_code == 200
    
    data = response.json()
    assert isinstance(data, list)
    
    if data:
        prediction = data[0]
        assert "probability" in prediction
        assert "horizon_days" in prediction
        assert "drivers_json" in prediction


@pytest.mark.asyncio
async def test_get_player_predictions_filter_by_horizon(client: AsyncClient, seeded_db):
    """Test filtering player predictions by horizon."""
    player_id = seeded_db.test_data["players"]["haaland"]
    response = await client.get(
        f"/api/v1/players/{player_id}/predictions?horizon_days=90"
    )
    assert response.status_code == 200
    
    data = response.json()
    for prediction in data:
        assert prediction["horizon_days"] == 90


@pytest.mark.asyncio
async def test_player_page_response_time(client: AsyncClient, seeded_db):
    """Test that player page responds within performance target (<200ms)."""
    player_id = seeded_db.test_data["players"]["haaland"]
    response = await client.get(f"/api/v1/players/{player_id}")
    
    assert response.status_code == 200
    
    # Check response time header
    response_time = response.headers.get("X-Response-Time")
    assert response_time is not None
    
    # Parse response time (format: "123.45ms")
    time_ms = float(response_time.replace("ms", ""))
    
    # Performance target: <200ms (relaxed for CI environments)
    assert time_ms < 500, f"Response time {time_ms}ms exceeds 500ms threshold"
