# Data Contracts

This document defines the schema, constraints, and invariants for every table in TransferLens.

---

## Reference Tables

### `competitions`

**Purpose**: Football leagues and tournaments.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Unique identifier |
| `name` | VARCHAR(200) | NOT NULL | Full name (e.g., "Premier League") |
| `short_name` | VARCHAR(20) | | Abbreviation (e.g., "PL") |
| `country` | VARCHAR(100) | NOT NULL | Country or "International" |
| `tier` | INT | DEFAULT 1 | Competition tier (1 = top flight) |
| `is_active` | BOOL | DEFAULT TRUE | Currently active |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() | Record creation |
| `updated_at` | TIMESTAMPTZ | | Last modification |

**Invariants**:
- `tier` MUST be >= 1
- `name` MUST be unique within `country`

---

### `seasons`

**Purpose**: Time periods for competitions.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Unique identifier |
| `competition_id` | UUID | FK → competitions | Parent competition |
| `name` | VARCHAR(50) | NOT NULL | Display name (e.g., "2024-25") |
| `start_date` | DATE | NOT NULL | Season start |
| `end_date` | DATE | NOT NULL | Season end |
| `is_current` | BOOL | DEFAULT FALSE | Currently active season |

**Invariants**:
- `end_date` > `start_date`
- Only ONE season per competition can have `is_current = TRUE`
- Seasons for same competition MUST NOT overlap

---

### `clubs`

**Purpose**: Football clubs.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Unique identifier |
| `name` | VARCHAR(200) | NOT NULL | Full name |
| `short_name` | VARCHAR(10) | | Abbreviation |
| `country` | VARCHAR(100) | NOT NULL | Country |
| `city` | VARCHAR(100) | | City |
| `stadium` | VARCHAR(200) | | Home stadium |
| `founded_year` | INT | | Year founded |
| `competition_id` | UUID | FK → competitions | Current competition |
| `logo_url` | TEXT | | Logo image URL |
| `primary_color` | VARCHAR(7) | | Hex color code |
| `is_active` | BOOL | DEFAULT TRUE | Currently active |

**Invariants**:
- `founded_year` MUST be <= current year
- `primary_color` MUST match `/^#[0-9A-Fa-f]{6}$/` if present

---

### `players`

**Purpose**: Football players.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Unique identifier |
| `name` | VARCHAR(200) | NOT NULL | Display name |
| `full_name` | VARCHAR(300) | | Legal full name |
| `date_of_birth` | DATE | | Birth date |
| `nationality` | VARCHAR(100) | | Primary nationality |
| `secondary_nationality` | VARCHAR(100) | | Secondary nationality |
| `position` | VARCHAR(20) | | Primary position |
| `foot` | VARCHAR(10) | | Preferred foot |
| `height_cm` | INT | | Height in centimeters |
| `current_club_id` | UUID | FK → clubs | Current club |
| `contract_until` | DATE | | Contract expiry |
| `photo_url` | TEXT | | Photo URL |
| `is_active` | BOOL | DEFAULT TRUE | Currently active |

**Invariants**:
- `date_of_birth` MUST be in the past
- `height_cm` MUST be between 140 and 220 if present
- `position` MUST be one of: GK, CB, LB, RB, LWB, RWB, CDM, CM, CAM, LM, RM, LW, RW, CF, ST
- `foot` MUST be one of: left, right, both

---

## Ledger Layer

### `transfer_events`

**Purpose**: Immutable record of confirmed, completed transfers.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Internal identifier |
| `event_id` | VARCHAR(100) | UNIQUE, NOT NULL | Deterministic external ID |
| `player_id` | UUID | FK → players, NOT NULL | Transferred player |
| `from_club_id` | UUID | FK → clubs | Origin club (NULL = from outside system) |
| `to_club_id` | UUID | FK → clubs, NOT NULL | Destination club |
| `transfer_type` | ENUM | NOT NULL | Type of transfer |
| `transfer_date` | DATE | NOT NULL | Effective date |
| `announced_at` | TIMESTAMPTZ | | Official announcement time |
| `fee_amount` | DECIMAL(15,2) | | Reported fee |
| `fee_currency` | VARCHAR(3) | | Fee currency (ISO 4217) |
| `fee_amount_eur` | DECIMAL(15,2) | | Fee in EUR |
| `fee_type` | ENUM | DEFAULT 'undisclosed' | Fee reliability |
| `contract_years` | DECIMAL(3,1) | | Contract length |
| `contract_until` | DATE | | Contract expiry |
| `loan_end_date` | DATE | | For loans: return date |
| `source` | VARCHAR(100) | NOT NULL | Where we learned this |
| `source_url` | TEXT | | Source URL |
| `source_confidence` | DECIMAL(3,2) | NOT NULL | Source reliability (0-1) |
| `notes` | TEXT | | Additional notes |
| `is_superseded` | BOOL | DEFAULT FALSE | Soft delete flag |
| `superseded_by` | UUID | FK → transfer_events | Replacement event |
| `superseded_reason` | TEXT | | Why superseded |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() | Record creation |

**Transfer Types**:
- `permanent` - Outright purchase
- `loan` - Temporary move
- `loan_with_option` - Loan with purchase option
- `loan_with_obligation` - Loan with mandatory purchase
- `free_transfer` - No fee
- `contract_expiry` - Contract ended
- `youth_promotion` - Academy to first team
- `retirement` - Player retired

**Fee Types**:
- `confirmed` - Officially disclosed
- `reported` - Media reports (reliable)
- `estimated` - Market estimate
- `undisclosed` - Fee not known
- `free` - No fee

**Invariants**:
- ⚠️ `event_id` format: `TL-{YYYYMMDD}-{PLAYERID_SHORT}-{FROMCLUBID_SHORT}`
- ⚠️ `transfer_date` MUST be in the past or today
- ⚠️ `source_confidence` MUST be between 0.0 and 1.0
- ⚠️ `loan_end_date` required if `transfer_type` starts with 'loan'
- ⚠️ `from_club_id` ≠ `to_club_id`
- ⚠️ NEVER UPDATE rows — only set `is_superseded = TRUE`

**Indexes**:
- `ix_transfer_events_player_id`
- `ix_transfer_events_from_club_id`
- `ix_transfer_events_to_club_id`
- `ix_transfer_events_transfer_date`
- `ix_transfer_events_event_id` (unique)

---

## Signals Layer

### `signal_events`

**Purpose**: Time-stamped observations with source and confidence.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Unique identifier |
| `entity_type` | ENUM | NOT NULL | What entity this describes |
| `player_id` | UUID | FK → players | Player (if applicable) |
| `club_id` | UUID | FK → clubs | Club (if applicable) |
| `signal_type` | ENUM | NOT NULL | Type of signal |
| `value_num` | DECIMAL(20,4) | | Numeric value |
| `value_text` | TEXT | | Text value |
| `value_json` | JSONB | | Complex value |
| `unit` | VARCHAR(50) | | Value unit |
| `source` | VARCHAR(100) | NOT NULL | Data source |
| `source_url` | TEXT | | Source URL |
| `confidence` | DECIMAL(3,2) | NOT NULL | Reliability (0-1) |
| `observed_at` | TIMESTAMPTZ | NOT NULL | When we observed this |
| `effective_from` | TIMESTAMPTZ | NOT NULL | When this became true |
| `effective_to` | TIMESTAMPTZ | | When this stopped being true |

**Entity Types**:
- `player` - About a single player
- `club` - About a single club
- `club_player_pair` - About player-club relationship

**Signal Types**:
| Signal | Entity | Value Type | Unit |
|--------|--------|------------|------|
| `minutes_last_5` | player | numeric | minutes |
| `injuries_status` | player | text | - |
| `goals_last_10` | player | numeric | goals |
| `assists_last_10` | player | numeric | assists |
| `club_league_position` | club | numeric | position |
| `club_points_per_game` | club | numeric | points |
| `club_net_spend_12m` | club | numeric | EUR |
| `contract_months_remaining` | player | numeric | months |
| `wage_estimate` | player | numeric | EUR/week |
| `market_value` | player | numeric | EUR |
| `release_clause` | player | numeric | EUR |
| `social_mention_velocity` | player | numeric | mentions/day |
| `social_sentiment` | player | numeric | -1 to 1 |
| `user_attention_velocity` | player | numeric | views/hour |
| `user_destination_cooccurrence` | club_player_pair | numeric | score |
| `user_watchlist_adds` | player | numeric | count |

**Invariants**:
- ⚠️ `confidence` MUST be between 0.0 and 1.0
- ⚠️ `confidence` ≤ 0.6 for `source = 'tl_user_derived'`
- ⚠️ `observed_at` MUST be <= NOW()
- ⚠️ `effective_from` MUST be <= `observed_at`
- ⚠️ `effective_to` MUST be > `effective_from` if present
- ⚠️ At least one of `player_id`, `club_id` MUST be NOT NULL
- ⚠️ NEVER UPDATE rows — always INSERT new observations

**Indexes**:
- `ix_signal_events_player_type_effective` (player_id, signal_type, effective_from, effective_to)
- `ix_signal_events_club_type_effective` (club_id, signal_type, effective_from)
- `ix_signal_events_observed_at`

---

## Market Layer

### `prediction_snapshots`

**Purpose**: Immutable probability snapshots.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Internal identifier |
| `snapshot_id` | VARCHAR(150) | UNIQUE, NOT NULL | Deterministic external ID |
| `model_version` | VARCHAR(50) | NOT NULL | Model version |
| `model_name` | VARCHAR(100) | NOT NULL | Model identifier |
| `player_id` | UUID | FK → players, NOT NULL | Subject player |
| `from_club_id` | UUID | FK → clubs | Origin club |
| `to_club_id` | UUID | FK → clubs | Destination club (NULL = any) |
| `horizon_days` | INT | NOT NULL | Prediction window |
| `probability` | DECIMAL(6,4) | NOT NULL | Transfer probability |
| `drivers_json` | JSONB | | Feature contributions |
| `features_json` | JSONB | | Input features |
| `as_of` | TIMESTAMPTZ | NOT NULL | Prediction timestamp |
| `window_start` | DATE | NOT NULL | Window start date |
| `window_end` | DATE | NOT NULL | Window end date |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() | Record creation |

**Invariants**:
- ⚠️ `snapshot_id` format: `SNAP-{PLAYERID_SHORT}-{TOCLUBID_SHORT}-H{HORIZON}-{TIMESTAMP}`
- ⚠️ `probability` MUST be between 0.0 and 1.0
- ⚠️ `horizon_days` MUST be one of: 30, 90, 180
- ⚠️ `window_end` = `window_start` + `horizon_days`
- ⚠️ NEVER UPDATE rows — always INSERT new snapshots
- ⚠️ All features in `features_json` MUST have `effective_from` <= `as_of`

**Indexes**:
- `ix_prediction_snapshots_player_as_of`
- `ix_prediction_snapshots_to_club_id`
- `ix_prediction_snapshots_horizon`

---

### `model_versions`

**Purpose**: Track trained model versions.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Unique identifier |
| `model_name` | VARCHAR(100) | NOT NULL | Model identifier |
| `model_version` | VARCHAR(50) | NOT NULL | Version string |
| `horizon_days` | INT | NOT NULL | Prediction horizon |
| `training_as_of` | TIMESTAMPTZ | NOT NULL | Training data cutoff |
| `training_samples` | INT | NOT NULL | Training set size |
| `positive_samples` | INT | NOT NULL | Positive labels |
| `negative_samples` | INT | NOT NULL | Negative labels |
| `feature_count` | INT | NOT NULL | Feature count |
| `features_used` | JSONB | | Feature list |
| `metrics` | JSONB | | Performance metrics |
| `feature_importances` | JSONB | | Feature importances |
| `artifact_path` | VARCHAR(500) | | Model file path |
| `status` | ENUM | NOT NULL | Training status |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() | Record creation |
| `completed_at` | TIMESTAMPTZ | | Training completion |
| `deployed_at` | TIMESTAMPTZ | | Deployment time |
| `error_message` | TEXT | | Error details |

**Status Values**:
- `training` - In progress
- `completed` - Training successful
- `failed` - Training failed
- `deployed` - In production
- `archived` - No longer used

**Invariants**:
- ⚠️ `(model_name, model_version)` MUST be unique
- ⚠️ `training_samples` = `positive_samples` + `negative_samples`
- ⚠️ No training data with dates > `training_as_of`

---

### `feature_snapshots`

**Purpose**: Cache built feature vectors.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Unique identifier |
| `player_id` | UUID | NOT NULL | Subject player |
| `candidate_club_id` | UUID | | Destination club |
| `as_of` | TIMESTAMPTZ | NOT NULL | Feature timestamp |
| `features` | JSONB | NOT NULL | Feature vector |
| `feature_version` | VARCHAR(50) | DEFAULT 'v1' | Schema version |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() | Record creation |

**Invariants**:
- ⚠️ `(player_id, candidate_club_id, as_of)` MUST be unique
- ⚠️ All signal values in `features` MUST have `effective_from` <= `as_of`

---

## UX Layer

### `user_events`

**Purpose**: Track user interactions.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Unique identifier |
| `user_anon_id` | VARCHAR(100) | NOT NULL | Anonymous user ID |
| `session_id` | VARCHAR(100) | | Session identifier |
| `event_type` | ENUM | NOT NULL | Event type |
| `player_id` | UUID | FK → players | Related player |
| `club_id` | UUID | FK → clubs | Related club |
| `event_props_json` | JSONB | | Additional properties |
| `page_url` | TEXT | | Page URL |
| `referrer_url` | TEXT | | Referrer URL |
| `device_type` | VARCHAR(20) | | Device category |
| `occurred_at` | TIMESTAMPTZ | DEFAULT NOW() | Event time |

**Event Types**:
- `page_view` - Generic page view
- `player_view` - Player page view
- `club_view` - Club page view
- `transfer_view` - Transfer detail view
- `prediction_view` - Prediction detail view
- `watchlist_add` - Added to watchlist
- `watchlist_remove` - Removed from watchlist
- `search` - Search performed
- `share` - Content shared
- `filter_apply` - Filter applied
- `comparison_view` - Comparison tool used

**Invariants**:
- ⚠️ `user_anon_id` MUST NOT contain PII
- ⚠️ Data can be purged after 90 days
- ⚠️ NEVER used directly as prediction input

---

### `watchlists`

**Purpose**: User watchlist containers.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Unique identifier |
| `user_anon_id` | VARCHAR(100) | NOT NULL | Owner |
| `name` | VARCHAR(100) | DEFAULT 'Default' | Watchlist name |
| `is_public` | BOOL | DEFAULT FALSE | Visibility |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() | Creation time |
| `updated_at` | TIMESTAMPTZ | | Last update |

---

### `watchlist_items`

**Purpose**: Players in watchlists.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Unique identifier |
| `watchlist_id` | UUID | FK → watchlists | Parent watchlist |
| `player_id` | UUID | FK → players | Watched player |
| `added_at` | TIMESTAMPTZ | DEFAULT NOW() | When added |
| `notes` | TEXT | | User notes |
| `alert_threshold` | DECIMAL(3,2) | | Probability alert threshold |

---

## Candidate Generation Layer

### `candidate_sets`

**Purpose**: Auditable record of which destination clubs were considered for each player.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Unique identifier |
| `player_id` | UUID | FK → players, NOT NULL | Subject player |
| `as_of` | TIMESTAMPTZ | NOT NULL | Generation timestamp |
| `horizon_days` | INT | NOT NULL | Prediction horizon |
| `from_club_id` | UUID | FK → clubs | Current club at generation time |
| `total_candidates` | INT | NOT NULL | Total candidates generated |
| `league_candidates` | INT | DEFAULT 0 | From league source |
| `social_candidates` | INT | DEFAULT 0 | From social signals |
| `user_attention_candidates` | INT | DEFAULT 0 | From user cooccurrence |
| `constraint_fit_candidates` | INT | DEFAULT 0 | From position/affordability fit |
| `random_candidates` | INT | DEFAULT 0 | Random calibration samples |
| `candidates_json` | JSONB | NOT NULL | Full candidate list |
| `player_context_json` | JSONB | | Player context at generation |
| `generation_version` | VARCHAR(50) | DEFAULT 'v1' | Algorithm version |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() | Record creation |

**Candidate Sources**:

| Source | Description | Priority |
|--------|-------------|----------|
| `league` | Top clubs from same/major leagues by position | High |
| `social` | Clubs with social co-mention velocity spike | Medium |
| `user_attention` | Clubs with user destination cooccurrence | Medium |
| `constraint_fit` | Clubs matching position need + affordability | Medium |
| `random` | Random sample for calibration | Low |

**candidates_json Format**:
```json
[
  {
    "club_id": "uuid",
    "source": "league",
    "score": 0.85,
    "reason": "Top 3 in Premier League"
  },
  {
    "club_id": "uuid",
    "source": "social",
    "score": 0.72,
    "reason": "Social co-mention velocity: 5.2x"
  }
]
```

**Invariants**:
- ⚠️ `(player_id, as_of, horizon_days)` MUST be unique
- ⚠️ Candidates stored in score-descending order
- ⚠️ Always includes random negatives for calibration
- ⚠️ `candidates_json` MUST match sum of source counts

**Indexes**:
- `ix_candidate_sets_player_as_of`
- `ix_candidate_sets_as_of`

---

## Materialized Views

### `player_market_view`

**Purpose**: Pre-computed view for fast market queries.

```sql
CREATE MATERIALIZED VIEW player_market_view AS
SELECT DISTINCT ON (ps.player_id, ps.to_club_id, ps.horizon_days)
    ps.*,
    p.name as player_name,
    p.position as player_position,
    -- ... additional joined fields
FROM prediction_snapshots ps
JOIN players p ON ps.player_id = p.id
-- ... joins
ORDER BY ps.player_id, ps.to_club_id, ps.horizon_days, ps.as_of DESC;
```

**Refresh**: `REFRESH MATERIALIZED VIEW CONCURRENTLY player_market_view`

**Invariants**:
- ⚠️ Refresh after every prediction batch
- ⚠️ Has unique index for concurrent refresh

---

## See Also

- [Architecture](./architecture.md) — Layer explanations
- [Ontology Rules](./ontology_rules.md) — What goes where
