"""
Time Travel Correctness Tests
==============================

These tests verify that the ML pipeline correctly excludes future signals
and respects time-travel constraints.

CRITICAL: These tests ensure we don't accidentally "cheat" by using
data that wouldn't have been available at prediction time.
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4

# Test the time_guards module
from worker.time_guards import (
    validate_signal_time_travel,
    validate_user_event_time_travel,
    validate_training_label_time_travel,
    TimeTravelViolationError,
    DataLeakageError,
)


class TestSignalTimeTravel:
    """Tests for signal time-travel validation."""
    
    def test_valid_signal_both_timestamps_before_as_of(self):
        """Signal with observed_at and effective_from before as_of should be valid."""
        as_of = datetime(2025, 1, 15, 12, 0, 0)
        observed_at = datetime(2025, 1, 10, 12, 0, 0)  # 5 days before
        effective_from = datetime(2025, 1, 10, 12, 0, 0)  # 5 days before
        
        # Should not raise
        validate_signal_time_travel(
            observed_at=observed_at,
            effective_from=effective_from,
            as_of=as_of,
            signal_type="market_value",
            entity_id="test-player-1",
        )
    
    def test_signal_observed_after_as_of_raises_error(self):
        """Signal observed AFTER as_of should raise TimeTravelViolationError."""
        as_of = datetime(2025, 1, 15, 12, 0, 0)
        observed_at = datetime(2025, 1, 20, 12, 0, 0)  # 5 days AFTER as_of
        effective_from = datetime(2025, 1, 10, 12, 0, 0)  # But effective before
        
        with pytest.raises(TimeTravelViolationError) as exc_info:
            validate_signal_time_travel(
                observed_at=observed_at,
                effective_from=effective_from,
                as_of=as_of,
                signal_type="market_value",
                entity_id="test-player-1",
            )
        
        assert "observed_at" in str(exc_info.value)
        assert "future knowledge" in str(exc_info.value).lower()
    
    def test_signal_effective_after_as_of_raises_error(self):
        """Signal effective AFTER as_of should raise TimeTravelViolationError."""
        as_of = datetime(2025, 1, 15, 12, 0, 0)
        observed_at = datetime(2025, 1, 10, 12, 0, 0)  # Observed before
        effective_from = datetime(2025, 1, 20, 12, 0, 0)  # But effective AFTER as_of
        
        with pytest.raises(TimeTravelViolationError) as exc_info:
            validate_signal_time_travel(
                observed_at=observed_at,
                effective_from=effective_from,
                as_of=as_of,
                signal_type="contract_months_remaining",
                entity_id="test-player-1",
            )
        
        assert "effective_from" in str(exc_info.value)
    
    def test_signal_exactly_at_as_of_is_valid(self):
        """Signal with timestamps exactly at as_of should be valid (<=)."""
        as_of = datetime(2025, 1, 15, 12, 0, 0)
        observed_at = as_of  # Exactly at as_of
        effective_from = as_of  # Exactly at as_of
        
        # Should not raise
        validate_signal_time_travel(
            observed_at=observed_at,
            effective_from=effective_from,
            as_of=as_of,
            signal_type="market_value",
            entity_id="test-player-1",
        )
    
    def test_future_signal_by_one_second_raises_error(self):
        """Even 1 second in the future should be rejected."""
        as_of = datetime(2025, 1, 15, 12, 0, 0)
        observed_at = datetime(2025, 1, 15, 12, 0, 1)  # 1 second after
        effective_from = datetime(2025, 1, 10, 12, 0, 0)
        
        with pytest.raises(TimeTravelViolationError):
            validate_signal_time_travel(
                observed_at=observed_at,
                effective_from=effective_from,
                as_of=as_of,
                signal_type="market_value",
                entity_id="test-player-1",
            )


class TestUserEventTimeTravel:
    """Tests for user event time-travel validation."""
    
    def test_valid_user_event_before_as_of(self):
        """User event occurred before as_of should be valid."""
        as_of = datetime(2025, 1, 15, 12, 0, 0)
        occurred_at = datetime(2025, 1, 10, 12, 0, 0)
        
        # Should not raise
        validate_user_event_time_travel(
            occurred_at=occurred_at,
            as_of=as_of,
            event_type="player_view",
            entity_id="test-player-1",
        )
    
    def test_user_event_after_as_of_raises_error(self):
        """User event occurred AFTER as_of should raise error."""
        as_of = datetime(2025, 1, 15, 12, 0, 0)
        occurred_at = datetime(2025, 1, 20, 12, 0, 0)  # AFTER as_of
        
        with pytest.raises(TimeTravelViolationError) as exc_info:
            validate_user_event_time_travel(
                occurred_at=occurred_at,
                as_of=as_of,
                event_type="player_view",
                entity_id="test-player-1",
            )
        
        assert "future user behavior" in str(exc_info.value).lower()
    
    def test_user_event_exactly_at_as_of_is_valid(self):
        """User event at exactly as_of should be valid."""
        as_of = datetime(2025, 1, 15, 12, 0, 0)
        occurred_at = as_of
        
        # Should not raise
        validate_user_event_time_travel(
            occurred_at=occurred_at,
            as_of=as_of,
            event_type="watchlist_add",
            entity_id="test-player-1",
        )


class TestTrainingLabelTimeTravel:
    """Tests for training data leakage detection."""
    
    def test_valid_feature_date_before_transfer(self):
        """Feature date well before transfer should be valid."""
        transfer_date = datetime(2025, 3, 15)
        feature_date = datetime(2024, 12, 15)  # 90 days before
        
        # Should not raise
        validate_training_label_time_travel(
            transfer_date=transfer_date,
            feature_date=feature_date,
            horizon_days=90,
            player_id="test-player-1",
        )
    
    def test_feature_date_at_transfer_raises_error(self):
        """Feature date at transfer time should raise DataLeakageError."""
        transfer_date = datetime(2025, 3, 15)
        feature_date = datetime(2025, 3, 15)  # Same as transfer
        
        with pytest.raises(DataLeakageError) as exc_info:
            validate_training_label_time_travel(
                transfer_date=transfer_date,
                feature_date=feature_date,
                horizon_days=90,
                player_id="test-player-1",
            )
        
        assert "BEFORE the transfer" in str(exc_info.value)
    
    def test_feature_date_after_transfer_raises_error(self):
        """Feature date AFTER transfer should definitely raise error."""
        transfer_date = datetime(2025, 3, 15)
        feature_date = datetime(2025, 4, 1)  # AFTER transfer
        
        with pytest.raises(DataLeakageError):
            validate_training_label_time_travel(
                transfer_date=transfer_date,
                feature_date=feature_date,
                horizon_days=90,
                player_id="test-player-1",
            )


class TestFutureSignalExclusion:
    """
    Integration-style tests that verify future signals are excluded.
    
    These tests require a database connection and create test data.
    They should be run with pytest-postgresql or similar fixture.
    """
    
    @pytest.mark.integration
    def test_future_signal_excluded_from_feature_build(self, db_session):
        """
        Insert a signal with observed_at in the future, verify it's excluded.
        
        This is the CRITICAL test - if this fails, we're cheating.
        """
        from worker.jobs.features import get_latest_signal_value
        
        player_id = uuid4()
        as_of = datetime(2025, 1, 15, 12, 0, 0)
        
        # Insert a signal OBSERVED in the future
        future_signal_id = uuid4()
        db_session.execute(
            """
            INSERT INTO signal_events (
                id, entity_type, player_id, signal_type, value_num,
                source, confidence, observed_at, effective_from
            ) VALUES (
                :id, 'player', :player_id, 'market_value', 100000000,
                'test', 0.9, :observed_at, :effective_from
            )
            """,
            {
                "id": future_signal_id,
                "player_id": player_id,
                "observed_at": datetime(2025, 1, 20, 12, 0, 0),  # FUTURE
                "effective_from": datetime(2025, 1, 10, 12, 0, 0),  # But effective in past
            }
        )
        
        # Insert a valid signal
        valid_signal_id = uuid4()
        db_session.execute(
            """
            INSERT INTO signal_events (
                id, entity_type, player_id, signal_type, value_num,
                source, confidence, observed_at, effective_from
            ) VALUES (
                :id, 'player', :player_id, 'market_value', 50000000,
                'test', 0.9, :observed_at, :effective_from
            )
            """,
            {
                "id": valid_signal_id,
                "player_id": player_id,
                "observed_at": datetime(2025, 1, 10, 12, 0, 0),  # Valid
                "effective_from": datetime(2025, 1, 10, 12, 0, 0),
            }
        )
        db_session.commit()
        
        # Get signal value - should return the valid one (50M), not future one (100M)
        value = get_latest_signal_value(
            db_session, "player", player_id, "market_value", as_of
        )
        
        # CRITICAL ASSERTION: Should get 50M, not 100M
        assert value == 50000000, (
            f"Expected 50M (valid signal), got {value}. "
            f"This means future signals are leaking into features!"
        )
    
    @pytest.mark.integration
    def test_no_valid_signal_returns_none(self, db_session):
        """If only future signals exist, should return None."""
        from worker.jobs.features import get_latest_signal_value
        
        player_id = uuid4()
        as_of = datetime(2025, 1, 15, 12, 0, 0)
        
        # Insert ONLY a future signal
        db_session.execute(
            """
            INSERT INTO signal_events (
                id, entity_type, player_id, signal_type, value_num,
                source, confidence, observed_at, effective_from
            ) VALUES (
                :id, 'player', :player_id, 'market_value', 100000000,
                'test', 0.9, :observed_at, :effective_from
            )
            """,
            {
                "id": uuid4(),
                "player_id": player_id,
                "observed_at": datetime(2025, 1, 20, 12, 0, 0),  # FUTURE
                "effective_from": datetime(2025, 1, 20, 12, 0, 0),  # FUTURE
            }
        )
        db_session.commit()
        
        value = get_latest_signal_value(
            db_session, "player", player_id, "market_value", as_of
        )
        
        assert value is None, (
            f"Expected None (no valid signal), got {value}. "
            f"Future signals are being incorrectly used!"
        )


class TestCalibrationMetrics:
    """Tests for calibration computation."""
    
    def test_perfect_calibration(self):
        """Perfect calibration should have slope=1, intercept=0."""
        from worker.jobs.evaluate import compute_calibration_metrics
        import numpy as np
        
        # Perfect calibration: predicted = actual
        y_true = np.array([0, 0, 0, 0, 0, 1, 1, 1, 1, 1])
        y_prob = np.array([0.1, 0.1, 0.2, 0.2, 0.3, 0.7, 0.8, 0.8, 0.9, 0.9])
        
        result = compute_calibration_metrics(y_true, y_prob, n_bins=5)
        
        # Slope should be close to 1
        assert 0.7 <= result["slope"] <= 1.3, f"Slope {result['slope']} not close to 1"
    
    def test_calibration_bins_structure(self):
        """Calibration bins should have correct structure."""
        from worker.jobs.evaluate import compute_calibration_metrics
        import numpy as np
        
        y_true = np.random.randint(0, 2, size=100)
        y_prob = np.random.random(size=100)
        
        result = compute_calibration_metrics(y_true, y_prob, n_bins=10)
        
        assert "slope" in result
        assert "intercept" in result
        assert "bins" in result
        
        for bin_key, bin_data in result["bins"].items():
            assert "range" in bin_data
            assert "predicted_mean" in bin_data
            assert "actual_mean" in bin_data
            assert "count" in bin_data


class TestThresholdMetrics:
    """Tests for threshold-based metrics."""
    
    def test_threshold_metrics_structure(self):
        """Threshold metrics should have correct structure."""
        from worker.jobs.evaluate import compute_threshold_metrics
        import numpy as np
        
        y_true = np.random.randint(0, 2, size=100)
        y_prob = np.random.random(size=100)
        
        result = compute_threshold_metrics(y_true, y_prob)
        
        assert "threshold_0.5" in result
        
        t05 = result["threshold_0.5"]
        assert "precision" in t05
        assert "recall" in t05
        assert "f1" in t05
    
    def test_high_threshold_reduces_predicted_positives(self):
        """Higher thresholds should reduce predicted positives."""
        from worker.jobs.evaluate import compute_threshold_metrics
        import numpy as np
        
        y_true = np.array([0, 0, 1, 1])
        y_prob = np.array([0.3, 0.4, 0.6, 0.7])
        
        result = compute_threshold_metrics(y_true, y_prob, thresholds=[0.3, 0.5, 0.7])
        
        # At threshold 0.3, should predict more positives
        assert result["threshold_0.3"]["predicted_positive"] >= result["threshold_0.7"]["predicted_positive"]


# Fixture for database session (to be used with pytest-postgresql or similar)
@pytest.fixture
def db_session():
    """
    Database session fixture.
    
    This is a placeholder - actual implementation depends on test infrastructure.
    Options:
    - pytest-postgresql
    - testcontainers
    - SQLite in-memory with schema
    """
    pytest.skip("Database tests require test infrastructure setup")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
