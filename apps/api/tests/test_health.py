"""
Tests for Health Endpoints
==========================

Tests for:
- GET /health
- GET /ready
- GET /live
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """Test health check endpoint."""
    response = await client.get("/health")
    assert response.status_code == 200
    
    data = response.json()
    assert "status" in data
    assert "version" in data
    assert "timestamp" in data
    assert "database" in data
    assert "redis" in data
    assert "environment" in data


@pytest.mark.asyncio
async def test_health_status_values(client: AsyncClient):
    """Test health check returns valid status values."""
    response = await client.get("/health")
    assert response.status_code == 200
    
    data = response.json()
    
    # Status should be healthy or degraded
    assert data["status"] in ["healthy", "degraded", "unhealthy"]
    
    # Database status
    assert data["database"] in ["healthy", "unhealthy"]
    
    # Redis status
    assert data["redis"] in ["healthy", "unavailable", "unhealthy"]


@pytest.mark.asyncio
async def test_ready_check(client: AsyncClient):
    """Test readiness probe endpoint."""
    response = await client.get("/ready")
    assert response.status_code == 200
    
    data = response.json()
    assert "ready" in data
    assert "checks" in data
    assert isinstance(data["ready"], bool)
    assert isinstance(data["checks"], dict)


@pytest.mark.asyncio
async def test_live_check(client: AsyncClient):
    """Test liveness probe endpoint."""
    response = await client.get("/live")
    assert response.status_code == 200
    
    data = response.json()
    assert data["alive"] is True


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient):
    """Test root endpoint returns API info."""
    response = await client.get("/")
    assert response.status_code == 200
    
    data = response.json()
    assert data["name"] == "TransferLens API"
    assert "version" in data
    assert "docs" in data
    assert "api" in data
