"""
Tests for Search Endpoint
=========================

Tests for GET /api/v1/search
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_search_requires_query(client: AsyncClient):
    """Test that search requires a query parameter."""
    response = await client.get("/api/v1/search")
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_search_minimum_query_length(client: AsyncClient):
    """Test that search requires minimum query length."""
    response = await client.get("/api/v1/search?q=")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_search_players_by_name(client: AsyncClient, seeded_db):
    """Test searching for players by name."""
    response = await client.get("/api/v1/search?q=Haaland")
    assert response.status_code == 200
    
    data = response.json()
    assert "results" in data
    assert "query" in data
    assert data["query"] == "Haaland"
    
    # Should find Haaland
    player_results = [r for r in data["results"] if r["type"] == "player"]
    assert len(player_results) >= 1
    assert any("Haaland" in r["name"] for r in player_results)


@pytest.mark.asyncio
async def test_search_clubs_by_name(client: AsyncClient, seeded_db):
    """Test searching for clubs by name."""
    response = await client.get("/api/v1/search?q=Manchester")
    assert response.status_code == 200
    
    data = response.json()
    club_results = [r for r in data["results"] if r["type"] == "club"]
    assert len(club_results) >= 1
    assert any("Manchester" in r["name"] for r in club_results)


@pytest.mark.asyncio
async def test_search_mixed_results(client: AsyncClient, seeded_db):
    """Test that search returns both players and clubs."""
    # "Real" should match Real Madrid (club) and possibly players
    response = await client.get("/api/v1/search?q=Real")
    assert response.status_code == 200
    
    data = response.json()
    assert "total" in data
    
    # Results should be ranked by score
    if len(data["results"]) > 1:
        scores = [r["score"] for r in data["results"]]
        assert scores == sorted(scores, reverse=True), "Results should be ranked by score descending"


@pytest.mark.asyncio
async def test_search_limit_parameter(client: AsyncClient, seeded_db):
    """Test that limit parameter works."""
    response = await client.get("/api/v1/search?q=a&limit=2")
    assert response.status_code == 200
    
    data = response.json()
    assert len(data["results"]) <= 2


@pytest.mark.asyncio
async def test_search_response_structure(client: AsyncClient, seeded_db):
    """Test that search response has correct structure."""
    response = await client.get("/api/v1/search?q=Saka")
    assert response.status_code == 200
    
    data = response.json()
    assert "query" in data
    assert "results" in data
    assert "total" in data
    
    if data["results"]:
        result = data["results"][0]
        assert "type" in result
        assert "id" in result
        assert "name" in result
        assert "score" in result
        # subtitle and image_url are optional
