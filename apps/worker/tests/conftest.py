"""
Pytest Configuration for Worker Tests
======================================

Fixtures and configuration for testing the worker module.
"""

import pytest
import sys
from pathlib import Path

# Add worker module to path
worker_path = Path(__file__).parent.parent
sys.path.insert(0, str(worker_path))


def pytest_configure(config):
    """Configure custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (requires database)"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )


@pytest.fixture
def sample_player_id():
    """Sample player UUID for testing."""
    from uuid import uuid4
    return uuid4()


@pytest.fixture
def sample_club_id():
    """Sample club UUID for testing."""
    from uuid import uuid4
    return uuid4()


@pytest.fixture
def sample_datetime():
    """Sample datetime for testing."""
    from datetime import datetime
    return datetime(2025, 1, 15, 12, 0, 0)
