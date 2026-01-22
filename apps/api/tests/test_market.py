"""
Tests for Market Endpoints
==========================

Tests for GET /api/v1/market/latest
"""

import pytest
from httpx import AsyncClient
from uuid import uuid4


@pytest.mark.asyncio
async def test_get_market_latest(client: AsyncClient, seeded_db):
    """Test getting latest market probabilities."""
    response = await client.get("/api/v1/market/latest")
    assert response.status_code == 200
    
    data = response.json()
    assert "predictions" in data
    assert "total" in data
    assert "as_of" in data
    assert "filters_applied" in data
    
    # Should have predictions from seeded data
    assert isinstance(data["predictions"], list)


@pytest.mark.asyncio
async def test_market_latest_with_limit(client: AsyncClient, seeded_db):
    """Test market latest with limit parameter."""
    response = await client.get("/api/v1/market/latest?limit=5")
    assert response.status_code == 200
    
    data = response.json()
    assert len(data["predictions"]) <= 5


@pytest.mark.asyncio
async def test_market_latest_with_horizon_filter(client: AsyncClient, seeded_db):
    """Test filtering by horizon_days."""
    response = await client.get("/api/v1/market/latest?horizon_days=90")
    assert response.status_code == 200
    
    data = response.json()
    for pred in data["predictions"]:
        assert pred["horizon_days"] == 90


@pytest.mark.asyncio
async def test_market_latest_with_min_probability(client: AsyncClient, seeded_db):
    """Test filtering by minimum probability."""
    response = await client.get("/api/v1/market/latest?min_probability=0.3")
    assert response.status_code == 200
    
    data = response.json()
    for pred in data["predictions"]:
        assert pred["probability"] >= 0.3


@pytest.mark.asyncio
async def test_market_latest_with_club_filter(client: AsyncClient, seeded_db):
    """Test filtering by club."""
    club_id = seeded_db.test_data["clubs"]["man_city"]
    response = await client.get(f"/api/v1/market/latest?club_id={club_id}")
    assert response.status_code == 200
    
    data = response.json()
    # All predictions should involve the club
    for pred in data["predictions"]:
        assert pred["from_club_id"] == str(club_id) or pred["to_club_id"] == str(club_id)


@pytest.mark.asyncio
async def test_market_latest_response_structure(client: AsyncClient, seeded_db):
    """Test that response has correct structure."""
    response = await client.get("/api/v1/market/latest?limit=1")
    assert response.status_code == 200
    
    data = response.json()
    
    if data["predictions"]:
        pred = data["predictions"][0]
        
        # Player info
        assert "player_id" in pred
        assert "player_name" in pred
        assert "player_position" in pred
        
        # Club info
        assert "from_club_id" in pred
        assert "from_club_name" in pred
        assert "to_club_id" in pred
        assert "to_club_name" in pred
        
        # Prediction info
        assert "horizon_days" in pred
        assert "probability" in pred
        assert "drivers_json" in pred
        assert "as_of" in pred
        assert "window_end" in pred


@pytest.mark.asyncio
async def test_market_latest_filters_applied(client: AsyncClient, seeded_db):
    """Test that filters_applied reflects query parameters."""
    response = await client.get("/api/v1/market/latest?horizon_days=30&min_probability=0.5")
    assert response.status_code == 200
    
    data = response.json()
    filters = data["filters_applied"]
    
    assert filters["horizon_days"] == 30
    assert filters["min_probability"] == 0.5


@pytest.mark.asyncio
async def test_market_latest_sorted_by_probability(client: AsyncClient, seeded_db):
    """Test that results are sorted by probability descending."""
    response = await client.get("/api/v1/market/latest")
    assert response.status_code == 200
    
    data = response.json()
    predictions = data["predictions"]
    
    if len(predictions) > 1:
        probabilities = [p["probability"] for p in predictions]
        assert probabilities == sorted(probabilities, reverse=True)
