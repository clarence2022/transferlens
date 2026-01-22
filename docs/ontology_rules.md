# Ontology Rules

This document defines the **strict rules** for what data goes where in TransferLens. These rules prevent ontology pollution — the dangerous mixing of ground truth, signals, predictions, and user behavior.

**Violating these rules corrupts the entire system.** Read carefully.

---

## Rule 1: Ledger is Completed Transfers ONLY

### ✅ What Goes in the Ledger

The `transfer_events` table contains ONLY transfers that meet ALL of these criteria:

1. **Officially confirmed** by at least one of:
   - Club announcement (official website, social media)
   - League registration database
   - Player confirmation with contract evidence
   
2. **Actually completed** — the player has:
   - Signed a contract
   - Been registered with the new club
   - (For loans) arrived at the loan club

3. **Verifiable** — we can point to:
   - A URL or document proving the transfer
   - A timestamp of the announcement

### ❌ What Does NOT Go in the Ledger

| Item | Why Not | Where It Goes |
|------|---------|---------------|
| "Done deal" per journalist | Not official until announced | Signals (social_mention_velocity) |
| Agreement in principle | Not completed | Signals (if reported) |
| Medical scheduled | Not completed | Signals (if reported) |
| Fee agreed | Not completed | Signals (if reported) |
| Player spotted at airport | Rumour | Nowhere (too weak) |
| Transfermarkt "confirmed" | Often premature | Wait for official |

### Example: Valid Ledger Entry

```json
{
  "event_id": "TL-20250115-ab12cd34-ef56gh78",
  "player_id": "ab12cd34-...",
  "from_club_id": "ef56gh78-...",
  "to_club_id": "ij90kl12-...",
  "transfer_type": "permanent",
  "transfer_date": "2025-01-15",
  "source": "official_club_announcement",
  "source_url": "https://mancity.com/news/new-signing",
  "source_confidence": 1.0
}
```

### Example: Invalid Ledger Entry

```json
{
  "event_id": "TL-20250115-ab12cd34-ef56gh78",
  "transfer_date": "2025-01-15",
  "source": "fabrizio_romano_tweet",  // ❌ Not official
  "source_confidence": 0.9  // ❌ Should be 1.0 for ledger
}
```

---

## Rule 2: Signals Must Be Time-Stamped, Sourced, Confidence-Scored

### ✅ Every Signal MUST Have

| Field | Requirement | Example |
|-------|-------------|---------|
| `observed_at` | When we learned this | `2025-01-15T14:30:00Z` |
| `effective_from` | When this became true | `2025-01-15T00:00:00Z` |
| `source` | Where this came from | `transfermarkt`, `opta`, `tl_user_derived` |
| `confidence` | How reliable (0-1) | `0.9` |

### Confidence Guidelines

| Source Type | Typical Confidence | Examples |
|-------------|-------------------|----------|
| Official data provider | 0.9 - 1.0 | Opta stats, Transfermarkt values |
| Reliable aggregator | 0.8 - 0.9 | FBRef, WhoScored |
| Social media metrics | 0.6 - 0.8 | Twitter mention velocity |
| News reports | 0.5 - 0.8 | Depends on source reliability |
| User-derived | 0.5 - 0.6 | ⚠️ MUST NOT exceed 0.6 |

### ❌ Invalid Signals

```python
# Missing timestamp
signal_events.insert({
    "player_id": player_id,
    "signal_type": "market_value",
    "value_num": 100000000,
    # ❌ No observed_at
    # ❌ No effective_from
})

# Missing source
signal_events.insert({
    "player_id": player_id,
    "signal_type": "market_value",
    "value_num": 100000000,
    "observed_at": now,
    "effective_from": now,
    # ❌ No source
})

# User-derived with high confidence
signal_events.insert({
    "player_id": player_id,
    "signal_type": "user_attention_velocity",
    "value_num": 500,
    "source": "tl_user_derived",
    "confidence": 0.9  # ❌ MUST be <= 0.6
})
```

### Time-Travel Correctness

Signals support bi-temporal queries:

```sql
-- "What did we know about this player on Jan 1?"
SELECT * FROM signal_events
WHERE player_id = :player_id
  AND effective_from <= '2025-01-01'
  AND (effective_to IS NULL OR effective_to > '2025-01-01')
ORDER BY effective_from DESC;
```

---

## Rule 3: User Behavior Becomes Weak Signals ONLY

### The Derivation Process

```
┌─────────────────┐
│   user_events   │
│   (raw clicks)  │
└────────┬────────┘
         │
         │ Aggregation (24h window)
         │ Confidence = 0.6
         │ Source = 'tl_user_derived'
         ▼
┌─────────────────┐
│  signal_events  │
│  (weak signal)  │
└─────────────────┘
```

### ✅ Valid User-Derived Signals

| Signal Type | Derivation | Max Confidence |
|-------------|------------|----------------|
| `user_attention_velocity` | Views per hour, recent vs older | 0.6 |
| `user_destination_cooccurrence` | Sessions with both player + club views | 0.6 |
| `user_watchlist_adds` | Watchlist additions in window | 0.6 |

### ❌ User Behavior NEVER Becomes

| Invalid Use | Why |
|-------------|-----|
| Ground truth | Users can be wrong, manipulated |
| High-confidence signal | Too noisy, not causal |
| Direct prediction input | Must go through signal layer |
| Transfer confirmation | Only official sources confirm |

### Code Enforcement

```python
# In signals.py - enforced at derivation time
DERIVED_SIGNAL_CONFIDENCE = 0.6  # NEVER exceed this

def write_user_derived_signal(...):
    assert confidence <= DERIVED_SIGNAL_CONFIDENCE, \
        f"User-derived signals must have confidence <= {DERIVED_SIGNAL_CONFIDENCE}"
    assert source == "tl_user_derived", \
        "User-derived signals must have source='tl_user_derived'"
```

---

## Rule 4: Predictions Are Snapshots, Never Overwritten

### The Snapshot Principle

Every prediction is an **immutable snapshot** that captures:
- What we predicted
- When we predicted it (`as_of`)
- What model we used (`model_version`)
- What features we saw (`features_json`)
- What drove the prediction (`drivers_json`)

### ✅ Correct: Insert New Snapshots

```python
# Day 1: First prediction
INSERT INTO prediction_snapshots (
    snapshot_id = 'SNAP-abc123-def456-H90-20250101120000',
    player_id = 'abc123',
    to_club_id = 'def456',
    probability = 0.35,
    as_of = '2025-01-01T12:00:00Z'
)

# Day 2: New prediction (different snapshot_id)
INSERT INTO prediction_snapshots (
    snapshot_id = 'SNAP-abc123-def456-H90-20250102120000',
    player_id = 'abc123',
    to_club_id = 'def456',
    probability = 0.42,  # Changed!
    as_of = '2025-01-02T12:00:00Z'
)
```

### ❌ FORBIDDEN: Update Existing Predictions

```python
# NEVER DO THIS
UPDATE prediction_snapshots
SET probability = 0.42
WHERE player_id = 'abc123' AND to_club_id = 'def456';
# ❌ This destroys our ability to backtest
# ❌ This hides our mistakes
# ❌ This is ontology pollution
```

### Why Snapshots Matter

1. **Backtesting**: We can measure "how accurate were our 90-day predictions?"
2. **Accountability**: We never "memory hole" bad predictions
3. **Charts**: Users can see probability over time
4. **Debugging**: When something goes wrong, we have a full audit trail

### Querying Current Predictions

To get the "latest" prediction, use `DISTINCT ON`:

```sql
SELECT DISTINCT ON (player_id, to_club_id, horizon_days)
    *
FROM prediction_snapshots
WHERE player_id = :player_id
ORDER BY player_id, to_club_id, horizon_days, as_of DESC;
```

---

## Rule 5: No Time-Travel Violations

### The Iron Law

> When building features or training models, you MUST NOT use data
> that would not have been available at the prediction time.

### ✅ Correct: Strict Time Boundaries

```python
def build_training_features(as_of: datetime, horizon_days: int):
    # Get transfers that happened AFTER the prediction window
    # These are our LABELS (what we're predicting)
    transfers = query("""
        SELECT * FROM transfer_events
        WHERE transfer_date BETWEEN :as_of AND :as_of + :horizon
    """)
    
    # Get signals that were known BEFORE as_of
    # These are our FEATURES (what we use to predict)
    for transfer in transfers:
        feature_date = transfer.transfer_date - timedelta(days=horizon_days)
        signals = query("""
            SELECT * FROM signal_events
            WHERE effective_from <= :feature_date  -- ✅ No future data
        """, feature_date=feature_date)
```

### ❌ Time-Travel Violations

```python
# VIOLATION 1: Using signals from after the transfer
signals = query("""
    SELECT * FROM signal_events
    WHERE player_id = :player_id
    ORDER BY observed_at DESC
    LIMIT 1
""")
# ❌ This might return a signal from after the transfer!

# VIOLATION 2: Using transfer outcome as feature
# "Players who transferred had high attention" - but we only know
# this BECAUSE they transferred, not BEFORE.

# VIOLATION 3: Using "current" contract length
# Contract was 24 months when we made prediction
# Contract is now 12 months (6 months later)
# ❌ Must use the value as of prediction time
```

### Validation

```python
def validate_no_lookahead(features: dict, as_of: datetime):
    """Assert no features use future data."""
    for feature_name, feature_value in features.items():
        if hasattr(feature_value, 'effective_from'):
            assert feature_value.effective_from <= as_of, \
                f"Feature {feature_name} uses future data: {feature_value.effective_from} > {as_of}"
```

---

## Summary: The Decision Tree

When you have new data, ask:

```
Is this a COMPLETED, OFFICIAL transfer?
├── YES → LEDGER (transfer_events)
│         source_confidence = 1.0
│         
└── NO → Is this an OBSERVATION about a player/club?
         ├── YES → SIGNALS (signal_events)
         │         - Set observed_at and effective_from
         │         - Set source and confidence
         │         - User-derived? confidence <= 0.6
         │         
         └── NO → Is this a MODEL OUTPUT?
                  ├── YES → MARKET (prediction_snapshots)
                  │         - Create new snapshot (never update)
                  │         - Include model_version and as_of
                  │         
                  └── NO → Is this USER BEHAVIOR?
                           ├── YES → UX (user_events)
                           │         - Ephemeral
                           │         - Will be aggregated to weak signals
                           │         
                           └── NO → Don't store it
```

---

## Enforcement

### Database Constraints

```sql
-- Signals: confidence check
ALTER TABLE signal_events
ADD CONSTRAINT chk_signal_confidence
CHECK (confidence >= 0 AND confidence <= 1);

-- Predictions: probability check
ALTER TABLE prediction_snapshots
ADD CONSTRAINT chk_prediction_probability
CHECK (probability >= 0 AND probability <= 1);

-- Predictions: immutability (no update trigger)
CREATE OR REPLACE FUNCTION prevent_prediction_update()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'prediction_snapshots are immutable';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER no_prediction_updates
BEFORE UPDATE ON prediction_snapshots
FOR EACH ROW EXECUTE FUNCTION prevent_prediction_update();
```

### Python Code Enforcement

The `time_guards.py` module provides strict enforcement:

```python
from worker.time_guards import (
    validate_signal_time_travel,
    validate_user_event_time_travel,
    validate_training_label_time_travel,
    get_signal_value_strict,
    TimeTravelViolationError,
    DataLeakageError,
)

# This WILL raise an exception if observed_at > as_of
validate_signal_time_travel(
    observed_at=signal.observed_at,
    effective_from=signal.effective_from,
    as_of=feature_date,
    signal_type=signal.signal_type,
    entity_id=str(signal.player_id),
)

# This ONLY returns signals where both:
# - observed_at <= as_of
# - effective_from <= as_of
value = get_signal_value_strict(
    session, "player", player_id, "market_value", as_of
)
```

### Unit Tests

Critical time-travel tests live in `apps/worker/tests/test_time_travel.py`:

```python
# Test that future signals are excluded
def test_future_signal_excluded_from_feature_build():
    """
    Insert a signal with observed_at in the future,
    verify it's excluded from features.
    
    CRITICAL: If this test fails, we're cheating!
    """
    # Insert signal with observed_at = 2025-01-20 (FUTURE)
    # but effective_from = 2025-01-10 (PAST)
    # ...
    
    # Query features as_of = 2025-01-15
    value = get_latest_signal_value(session, "player", player_id, "market_value", as_of)
    
    # Should NOT get the future signal
    assert value != future_signal_value
```

Run tests with:
```bash
docker compose exec worker pytest tests/test_time_travel.py -v
```

### Code Review Checklist

- [ ] Is ledger data from an official source?
- [ ] Do all signals have observed_at, effective_from, source, confidence?
- [ ] Are user-derived signals capped at confidence 0.6?
- [ ] Are predictions inserted (not updated)?
- [ ] Is feature building using only data from before as_of?
- [ ] Are signal queries using `AND observed_at <= :as_of`?
- [ ] Are user event queries using `AND occurred_at <= :as_of`?
- [ ] Do tests verify future data is excluded?

---

## See Also

- [Architecture](./architecture.md) — Layer explanations
- [Data Contracts](./data_contracts.md) — Table definitions
- [Runbook](./runbook_local.md) — How to run the system
