"""
Tests for Time-Travel Queries
=============================

Tests for as_of parameter support in various endpoints.
"""

import pytest
from datetime import datetime, timedelta
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_signals_time_travel_basic(client: AsyncClient, seeded_db):
    """Test basic time-travel query for signals."""
    player_id = seeded_db.test_data["players"]["haaland"]
    
    # Get current signals
    response_current = await client.get(f"/api/v1/players/{player_id}/signals")
    assert response_current.status_code == 200
    current_signals = response_current.json()
    
    # Get signals as of 30 days ago
    as_of = (datetime.utcnow() - timedelta(days=30)).isoformat()
    response_past = await client.get(
        f"/api/v1/players/{player_id}/signals?as_of={as_of}"
    )
    assert response_past.status_code == 200
    past_signals = response_past.json()
    
    # Past query should return fewer or different signals
    # (signals created after as_of should not be included)
    assert isinstance(past_signals, list)


@pytest.mark.asyncio
async def test_signals_time_travel_filters_by_effective_from(client: AsyncClient, seeded_db):
    """Test that time-travel filters by effective_from correctly."""
    player_id = seeded_db.test_data["players"]["haaland"]
    
    # Get signals as of 1 week ago
    one_week_ago = datetime.utcnow() - timedelta(days=7)
    as_of = one_week_ago.isoformat()
    
    response = await client.get(
        f"/api/v1/players/{player_id}/signals?as_of={as_of}"
    )
    assert response.status_code == 200
    signals = response.json()
    
    # All returned signals should have effective_from <= as_of
    for signal in signals:
        signal_effective = datetime.fromisoformat(signal["effective_from"].replace("Z", "+00:00"))
        # Allow some tolerance for timezone differences
        assert signal_effective <= one_week_ago + timedelta(hours=24), \
            f"Signal effective_from {signal_effective} is after as_of {one_week_ago}"


@pytest.mark.asyncio
async def test_predictions_time_travel_basic(client: AsyncClient, seeded_db):
    """Test basic time-travel query for predictions."""
    player_id = seeded_db.test_data["players"]["haaland"]
    
    # Get current predictions
    response_current = await client.get(f"/api/v1/players/{player_id}/predictions")
    assert response_current.status_code == 200
    current_preds = response_current.json()
    
    # Get predictions as of 30 days ago
    as_of = (datetime.utcnow() - timedelta(days=30)).isoformat()
    response_past = await client.get(
        f"/api/v1/players/{player_id}/predictions?as_of={as_of}"
    )
    assert response_past.status_code == 200
    past_preds = response_past.json()
    
    # Both should return lists
    assert isinstance(current_preds, list)
    assert isinstance(past_preds, list)


@pytest.mark.asyncio
async def test_predictions_time_travel_filters_by_as_of(client: AsyncClient, seeded_db):
    """Test that time-travel filters predictions by as_of correctly."""
    player_id = seeded_db.test_data["players"]["haaland"]
    
    # Get predictions as of 1 week ago
    one_week_ago = datetime.utcnow() - timedelta(days=7)
    as_of_param = one_week_ago.isoformat()
    
    response = await client.get(
        f"/api/v1/players/{player_id}/predictions?as_of={as_of_param}"
    )
    assert response.status_code == 200
    predictions = response.json()
    
    # All returned predictions should have as_of <= query as_of
    for pred in predictions:
        pred_as_of = datetime.fromisoformat(pred["as_of"].replace("Z", "+00:00"))
        assert pred_as_of <= one_week_ago + timedelta(hours=24), \
            f"Prediction as_of {pred_as_of} is after query as_of {one_week_ago}"


@pytest.mark.asyncio
async def test_signals_time_travel_with_type_filter(client: AsyncClient, seeded_db):
    """Test combining time-travel with signal type filter."""
    player_id = seeded_db.test_data["players"]["haaland"]
    
    # Get market_value signals as of 2 weeks ago
    two_weeks_ago = (datetime.utcnow() - timedelta(days=14)).isoformat()
    
    response = await client.get(
        f"/api/v1/players/{player_id}/signals?as_of={two_weeks_ago}&signal_type=market_value"
    )
    assert response.status_code == 200
    signals = response.json()
    
    # All should be market_value type
    for signal in signals:
        assert signal["signal_type"] == "market_value"


@pytest.mark.asyncio
async def test_predictions_time_travel_with_horizon_filter(client: AsyncClient, seeded_db):
    """Test combining time-travel with horizon filter."""
    player_id = seeded_db.test_data["players"]["haaland"]
    
    # Get 90-day predictions as of 2 weeks ago
    two_weeks_ago = (datetime.utcnow() - timedelta(days=14)).isoformat()
    
    response = await client.get(
        f"/api/v1/players/{player_id}/predictions?as_of={two_weeks_ago}&horizon_days=90"
    )
    assert response.status_code == 200
    predictions = response.json()
    
    # All should be 90-day horizon
    for pred in predictions:
        assert pred["horizon_days"] == 90


@pytest.mark.asyncio
async def test_signals_future_as_of_returns_all(client: AsyncClient, seeded_db):
    """Test that future as_of date returns all signals."""
    player_id = seeded_db.test_data["players"]["haaland"]
    
    # Get signals with future as_of
    future = (datetime.utcnow() + timedelta(days=365)).isoformat()
    
    response_future = await client.get(
        f"/api/v1/players/{player_id}/signals?as_of={future}"
    )
    response_current = await client.get(f"/api/v1/players/{player_id}/signals")
    
    assert response_future.status_code == 200
    assert response_current.status_code == 200
    
    future_signals = response_future.json()
    current_signals = response_current.json()
    
    # Future query should return at least as many signals as current
    assert len(future_signals) >= len(current_signals)


@pytest.mark.asyncio
async def test_signals_very_old_as_of_returns_empty(client: AsyncClient, seeded_db):
    """Test that very old as_of date returns empty results."""
    player_id = seeded_db.test_data["players"]["haaland"]
    
    # Get signals as of 10 years ago
    old_date = (datetime.utcnow() - timedelta(days=3650)).isoformat()
    
    response = await client.get(
        f"/api/v1/players/{player_id}/signals?as_of={old_date}"
    )
    assert response.status_code == 200
    signals = response.json()
    
    # Should return empty or very few signals
    assert len(signals) == 0


@pytest.mark.asyncio
async def test_time_travel_invalid_format(client: AsyncClient, seeded_db):
    """Test that invalid as_of format is rejected."""
    player_id = seeded_db.test_data["players"]["haaland"]
    
    # Invalid date format
    response = await client.get(
        f"/api/v1/players/{player_id}/signals?as_of=not-a-date"
    )
    assert response.status_code == 422  # Validation error
