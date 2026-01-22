"""
Tests for Club Endpoints
========================

Tests for GET /api/v1/clubs/{club_id}
"""

import pytest
from httpx import AsyncClient
from uuid import uuid4


@pytest.mark.asyncio
async def test_get_club_not_found(client: AsyncClient):
    """Test that non-existent club returns 404."""
    fake_id = uuid4()
    response = await client.get(f"/api/v1/clubs/{fake_id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_club_detail(client: AsyncClient, seeded_db):
    """Test getting club detail page."""
    club_id = seeded_db.test_data["clubs"]["man_city"]
    response = await client.get(f"/api/v1/clubs/{club_id}")
    assert response.status_code == 200
    
    data = response.json()
    
    # Basic fields
    assert data["id"] == str(club_id)
    assert data["name"] == "Manchester City"
    assert data["country"] == "England"


@pytest.mark.asyncio
async def test_get_club_competition(client: AsyncClient, seeded_db):
    """Test that club detail includes competition."""
    club_id = seeded_db.test_data["clubs"]["man_city"]
    response = await client.get(f"/api/v1/clubs/{club_id}")
    assert response.status_code == 200
    
    data = response.json()
    
    # Competition should be included
    assert data["competition"] is not None
    assert data["competition"]["name"] == "Premier League"


@pytest.mark.asyncio
async def test_get_club_squad(client: AsyncClient, seeded_db):
    """Test that club detail includes squad."""
    club_id = seeded_db.test_data["clubs"]["man_city"]
    response = await client.get(f"/api/v1/clubs/{club_id}")
    assert response.status_code == 200
    
    data = response.json()
    
    assert "squad" in data
    assert isinstance(data["squad"], list)
    assert "squad_count" in data
    
    # Squad should contain Haaland
    player_names = [p["name"] for p in data["squad"]]
    assert "Erling Haaland" in player_names


@pytest.mark.asyncio
async def test_get_club_probabilities(client: AsyncClient, seeded_db):
    """Test that club detail includes probabilities."""
    club_id = seeded_db.test_data["clubs"]["man_city"]
    response = await client.get(f"/api/v1/clubs/{club_id}")
    assert response.status_code == 200
    
    data = response.json()
    
    # Outgoing and incoming probabilities should be lists
    assert "outgoing_probabilities" in data
    assert "incoming_probabilities" in data
    assert isinstance(data["outgoing_probabilities"], list)
    assert isinstance(data["incoming_probabilities"], list)


@pytest.mark.asyncio
async def test_get_club_recent_transfers(client: AsyncClient, seeded_db):
    """Test that club detail includes recent transfers."""
    club_id = seeded_db.test_data["clubs"]["man_city"]
    response = await client.get(f"/api/v1/clubs/{club_id}")
    assert response.status_code == 200
    
    data = response.json()
    
    # Transfer lists should be present
    assert "recent_transfers_in" in data
    assert "recent_transfers_out" in data
    assert isinstance(data["recent_transfers_in"], list)
    assert isinstance(data["recent_transfers_out"], list)


@pytest.mark.asyncio
async def test_get_club_response_structure(client: AsyncClient, seeded_db):
    """Test that club response has correct structure."""
    club_id = seeded_db.test_data["clubs"]["real_madrid"]
    response = await client.get(f"/api/v1/clubs/{club_id}")
    assert response.status_code == 200
    
    data = response.json()
    
    # Required fields
    assert "id" in data
    assert "name" in data
    assert "country" in data
    assert "is_active" in data
    assert "created_at" in data
    
    # Optional fields should be present (may be null)
    assert "short_name" in data
    assert "city" in data
    assert "stadium" in data
    assert "logo_url" in data


@pytest.mark.asyncio
async def test_get_club_squad_players_have_correct_club(client: AsyncClient, seeded_db):
    """Test that squad players belong to this club."""
    club_id = seeded_db.test_data["clubs"]["real_madrid"]
    response = await client.get(f"/api/v1/clubs/{club_id}")
    assert response.status_code == 200
    
    data = response.json()
    
    # All squad players should have this club as current_club_id
    for player in data["squad"]:
        assert player["current_club_id"] == str(club_id)
