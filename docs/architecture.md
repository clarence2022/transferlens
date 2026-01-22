# TransferLens Architecture

## Overview

TransferLens is a real-time football transfer intelligence platform built on a **four-layer data architecture**. This architecture enforces strict separation of concerns and prevents ontology pollution — the dangerous mixing of ground truth, signals, predictions, and user behavior.

```
┌─────────────────────────────────────────────────────────────────────┐
│                         UX LAYER                                     │
│   User events, watchlists, sessions                                  │
│   (ephemeral, never ground truth)                                    │
├─────────────────────────────────────────────────────────────────────┤
│                       MARKET LAYER                                   │
│   Predictions, probability snapshots, model outputs                  │
│   (derived, versioned, never overwritten)                            │
├─────────────────────────────────────────────────────────────────────┤
│                      SIGNALS LAYER                                   │
│   Time-stamped observations with source + confidence                 │
│   (bi-temporal, auditable, diverse sources)                          │
├─────────────────────────────────────────────────────────────────────┤
│                       LEDGER LAYER                                   │
│   Confirmed, completed transfers only                                │
│   (immutable, append-only, single source of truth)                   │
└─────────────────────────────────────────────────────────────────────┘
```

## The Four Layers

### 1. Ledger Layer (Ground Truth)

**Purpose**: Immutable record of confirmed, completed transfers.

**Tables**: `transfer_events`

**Key Properties**:
- ✅ Only contains transfers that have **actually happened**
- ✅ Append-only (soft delete via `is_superseded`, never hard delete)
- ✅ Each event has a unique, deterministic `event_id`
- ✅ Source and confidence tracked for each record
- ❌ NEVER contains rumours, predictions, or speculation
- ❌ NEVER modified after initial insert (only superseded)

**What Goes Here**:
- Official club announcements
- League registration confirmations
- Contract signings with dates

**What Does NOT Go Here**:
- Rumours (even "reliable" ones)
- "Done deals" before official announcement
- Loan extensions or renewals (separate event type)

### 2. Signals Layer (Observations)

**Purpose**: Time-stamped observations about players, clubs, and pairs.

**Tables**: `signal_events`

**Key Properties**:
- ✅ Every signal has `observed_at` (when we saw it) and `effective_from` (when it became true)
- ✅ Every signal has a `source` and `confidence` score
- ✅ Signals are bi-temporal (supports time-travel queries)
- ✅ Multiple conflicting signals can coexist
- ❌ NEVER overwrites previous signals
- ❌ User behavior signals have low confidence (≤0.6)

**Signal Types**:

| Category | Examples | Typical Confidence |
|----------|----------|-------------------|
| Official | Market value (Transfermarkt), contract dates | 0.9-1.0 |
| Stats | Goals, assists, minutes | 0.9-1.0 |
| Social | Mention velocity, sentiment | 0.6-0.8 |
| User-derived | Attention velocity, co-occurrence | 0.5-0.6 |

**What Goes Here**:
- Market valuations from data providers
- Performance statistics
- Social media metrics
- Injury reports
- User-derived weak signals

**What Does NOT Go Here**:
- Confirmed transfers (→ Ledger)
- Predictions (→ Market)
- Raw user clicks (→ UX)

### 3. Market Layer (Predictions)

**Purpose**: Probability snapshots and model outputs.

**Tables**: `prediction_snapshots`, `model_versions`, `feature_snapshots`

**Key Properties**:
- ✅ Predictions are stored as **immutable snapshots**
- ✅ Each snapshot has `as_of`, `model_version`, and `horizon_days`
- ✅ Historical predictions preserved for backtesting
- ✅ Feature importances ("drivers") stored with predictions
- ❌ NEVER overwrites previous predictions
- ❌ NEVER uses future data (strict time-travel correctness)

**What Goes Here**:
- Transfer probability scores
- Model metadata and metrics
- Feature vectors (for debugging)
- Prediction drivers/explanations

**What Does NOT Go Here**:
- Confirmed transfers (→ Ledger)
- Input signals (→ Signals)
- User data (→ UX)

### 4. UX Layer (User Behavior)

**Purpose**: Track user interactions for product analytics and weak signal derivation.

**Tables**: `user_events`, `watchlists`, `watchlist_items`

**Key Properties**:
- ✅ Ephemeral — can be purged after aggregation
- ✅ Anonymous by default (anon_id, not PII)
- ✅ Aggregated into weak signals, never used directly
- ❌ NEVER treated as ground truth
- ❌ NEVER directly influences predictions without confidence discount

**What Goes Here**:
- Page views, searches, clicks
- Watchlist additions/removals
- Session data
- Device/referrer metadata

**What Does NOT Go Here**:
- Anything that should persist long-term
- Anything used as strong signal

---

## Anti-Leakage Rules

These rules prevent data from "leaking" between layers inappropriately:

### Rule 1: Ledger is Sacred
```
NEVER write to transfer_events unless:
1. The transfer is officially confirmed
2. The source is verifiable
3. The event_id is deterministic and unique
```

### Rule 2: Signals Must Be Sourced
```
EVERY signal_event MUST have:
1. source (where did this come from?)
2. confidence (how reliable is the source?)
3. observed_at (when did we observe this?)
4. effective_from (when did this become true?)
```

### Rule 3: User Behavior is Weak
```
When deriving signals from user_events:
1. Confidence MUST be ≤ 0.6
2. Source MUST be 'tl_user_derived'
3. Aggregation window MUST be specified
```

### Rule 4: Predictions are Snapshots
```
prediction_snapshots are IMMUTABLE:
1. NEVER UPDATE existing rows
2. ALWAYS INSERT new snapshots
3. snapshot_id MUST be unique and deterministic
4. as_of MUST reflect the prediction timestamp
```

### Rule 5: No Time Travel Violations
```
When training models or generating predictions:
1. ONLY use signals with effective_from <= as_of
2. NEVER use transfer outcomes that occur after as_of
3. Validate with: assert max(signal_dates) <= prediction_as_of
```

---

## Data Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   External  │     │   User      │     │   Official  │
│   Data      │     │   Browser   │     │   Sources   │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │
       ▼                   ▼                   ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Signals   │     │   UX Layer  │     │   Ledger    │
│   Layer     │     │             │     │   Layer     │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │
       │    ┌──────────────┘                   │
       │    │ (aggregation,                    │
       │    │  confidence=0.6)                 │
       │    ▼                                  │
       ├────────────────────┐                  │
       │                    │                  │
       ▼                    │                  │
┌─────────────┐             │                  │
│   Feature   │◄────────────┴──────────────────┘
│   Builder   │      (labels for training)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Model     │
│   Training  │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Market    │
│   Layer     │
│ (snapshots) │
└─────────────┘
```

---

## Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Database | PostgreSQL 15+ | Primary data store |
| API | FastAPI (Python) | REST API with OpenAPI |
| Worker | Python CLI | Background jobs |
| Web | Next.js 14 | Frontend |
| Cache | Redis | Session store, job queue |

---

## Key Design Decisions

### 1. Why Bi-temporal Signals?

Signals have two timestamps:
- `observed_at`: When we learned about this signal
- `effective_from`: When the signal became true (e.g., contract signed Jan 1)

This enables:
- Time-travel queries ("what did we know on date X?")
- Proper backtesting without lookahead bias
- Audit trails

### 2. Why Snapshot-based Predictions?

Instead of maintaining "current" predictions, we store every prediction as an immutable snapshot. This enables:
- Historical accuracy tracking
- Probability-over-time charts
- Model comparison (same player, different models)
- Accountability (we never "memory hole" bad predictions)

### 3. Why Low Confidence for User Signals?

User behavior (views, searches) is:
- Easily manipulated
- Subject to virality bias
- Not causal (correlation only)

By capping confidence at 0.6, we ensure user signals can influence predictions but never dominate them.

### 4. Why Deterministic Event IDs?

Event IDs like `TL-20250115-PLAYERID-FROMCLUBID` enable:
- Idempotent ingestion (re-run safely)
- Easy deduplication
- Human-readable debugging

---

## See Also

- [Data Contracts](./data_contracts.md) — Table-by-table definitions
- [Ontology Rules](./ontology_rules.md) — What goes where
- [Local Runbook](./runbook_local.md) — How to run the system
