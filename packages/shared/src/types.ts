/**
 * TransferLens API Types
 * ======================
 * 
 * TypeScript types matching the FastAPI Pydantic schemas.
 * Auto-generated structure based on OpenAPI spec.
 */

// =============================================================================
// ENUMS
// =============================================================================

export enum EntityType {
  PLAYER = 'player',
  CLUB = 'club',
  CLUB_PLAYER_PAIR = 'club_player_pair',
}

export enum SignalType {
  MINUTES_LAST_5 = 'minutes_last_5',
  INJURIES_STATUS = 'injuries_status',
  GOALS_LAST_10 = 'goals_last_10',
  ASSISTS_LAST_10 = 'assists_last_10',
  CLUB_LEAGUE_POSITION = 'club_league_position',
  CLUB_POINTS_PER_GAME = 'club_points_per_game',
  CLUB_NET_SPEND_12M = 'club_net_spend_12m',
  CONTRACT_MONTHS_REMAINING = 'contract_months_remaining',
  WAGE_ESTIMATE = 'wage_estimate',
  MARKET_VALUE = 'market_value',
  RELEASE_CLAUSE = 'release_clause',
  SOCIAL_MENTION_VELOCITY = 'social_mention_velocity',
  SOCIAL_SENTIMENT = 'social_sentiment',
  USER_ATTENTION_VELOCITY = 'user_attention_velocity',
  USER_DESTINATION_COOCCURRENCE = 'user_destination_cooccurrence',
  USER_WATCHLIST_ADDS = 'user_watchlist_adds',
}

export enum TransferType {
  PERMANENT = 'permanent',
  LOAN = 'loan',
  LOAN_WITH_OPTION = 'loan_with_option',
  LOAN_WITH_OBLIGATION = 'loan_with_obligation',
  FREE_TRANSFER = 'free_transfer',
  CONTRACT_EXPIRY = 'contract_expiry',
  YOUTH_PROMOTION = 'youth_promotion',
  RETIREMENT = 'retirement',
}

export enum FeeType {
  CONFIRMED = 'confirmed',
  REPORTED = 'reported',
  ESTIMATED = 'estimated',
  UNDISCLOSED = 'undisclosed',
  FREE = 'free',
}

export enum UserEventType {
  PAGE_VIEW = 'page_view',
  PLAYER_VIEW = 'player_view',
  CLUB_VIEW = 'club_view',
  TRANSFER_VIEW = 'transfer_view',
  PREDICTION_VIEW = 'prediction_view',
  WATCHLIST_ADD = 'watchlist_add',
  WATCHLIST_REMOVE = 'watchlist_remove',
  SEARCH = 'search',
  SHARE = 'share',
  FILTER_APPLY = 'filter_apply',
  COMPARISON_VIEW = 'comparison_view',
}

export enum SearchResultType {
  PLAYER = 'player',
  CLUB = 'club',
}

// =============================================================================
// HEALTH & STATUS
// =============================================================================

export interface HealthResponse {
  status: string;
  version: string;
  timestamp: string;
  database: string;
  redis: string;
  environment: string;
}

export interface ReadyResponse {
  ready: boolean;
  checks: Record<string, boolean>;
}

// =============================================================================
// COMPETITION
// =============================================================================

export interface CompetitionBrief {
  id: string;
  name: string;
  short_name: string | null;
  country: string;
}

export interface CompetitionRead extends CompetitionBrief {
  competition_type: string;
  tier: number;
  logo_url: string | null;
  is_active: boolean;
  created_at: string;
}

// =============================================================================
// CLUB
// =============================================================================

export interface ClubBrief {
  id: string;
  name: string;
  short_name: string | null;
  country: string;
  logo_url: string | null;
}

export interface ClubRead extends ClubBrief {
  city: string | null;
  stadium: string | null;
  stadium_capacity: number | null;
  founded_year: number | null;
  primary_color: string | null;
  secondary_color: string | null;
  competition_id: string | null;
  is_active: boolean;
  created_at: string;
}

export interface ClubDetail extends ClubRead {
  competition: CompetitionBrief | null;
  squad: PlayerBrief[];
  squad_count: number;
  outgoing_probabilities: ProbabilityRow[];
  incoming_probabilities: ProbabilityRow[];
  recent_transfers_in: TransferBrief[];
  recent_transfers_out: TransferBrief[];
}

// =============================================================================
// PLAYER
// =============================================================================

export interface PlayerBrief {
  id: string;
  name: string;
  position: string | null;
  nationality: string | null;
  photo_url: string | null;
  current_club_id: string | null;
}

export interface PlayerWithClub extends PlayerBrief {
  current_club: ClubBrief | null;
  age: number | null;
  contract_until: string | null;
}

export interface PlayerRead {
  id: string;
  name: string;
  full_name: string | null;
  date_of_birth: string | null;
  nationality: string | null;
  secondary_nationality: string | null;
  position: string | null;
  secondary_position: string | null;
  foot: string | null;
  height_cm: number | null;
  weight_kg: number | null;
  photo_url: string | null;
  current_club_id: string | null;
  shirt_number: number | null;
  contract_until: string | null;
  is_active: boolean;
  created_at: string;
}

export interface SignalDelta {
  signal_type: SignalType;
  description: string;
  old_value: unknown;
  new_value: unknown;
  change_percent: number | null;
  severity: 'info' | 'warning' | 'alert';
  observed_at: string;
}

export interface PlayerDetail extends PlayerRead {
  current_club: ClubBrief | null;
  age: number | null;
  
  // Key stats from latest signals
  market_value: number | null;
  contract_months_remaining: number | null;
  wage_estimate: number | null;
  goals_last_10: number | null;
  assists_last_10: number | null;
  minutes_last_5: number | null;
  
  // Latest predictions
  latest_predictions: PredictionBrief[];
  
  // What changed (last 7 days)
  what_changed: SignalDelta[];
  
  // Transfer history
  transfer_history: TransferBrief[];
}

// =============================================================================
// SEARCH
// =============================================================================

export interface SearchResult {
  type: SearchResultType;
  id: string;
  name: string;
  subtitle: string | null;
  image_url: string | null;
  score: number;
}

export interface SearchResponse {
  query: string;
  results: SearchResult[];
  total: number;
}

// =============================================================================
// TRANSFER EVENT (LEDGER)
// =============================================================================

export interface TransferBrief {
  id: string;
  event_id: string;
  player_id: string;
  player_name: string | null;
  from_club_id: string | null;
  from_club_name: string | null;
  to_club_id: string;
  to_club_name: string | null;
  transfer_type: TransferType;
  transfer_date: string;
  fee_amount_eur: number | null;
}

export interface TransferEventCreate {
  player_id: string;
  from_club_id: string | null;
  to_club_id: string;
  transfer_type: TransferType;
  transfer_date: string;
  announced_date: string | null;
  fee_amount: number | null;
  fee_currency: string;
  fee_type: FeeType;
  add_ons_amount: number | null;
  contract_start: string | null;
  contract_end: string | null;
  loan_end_date: string | null;
  option_to_buy: boolean | null;
  option_to_buy_amount: number | null;
  sell_on_percent: number | null;
  source: string;
  source_url: string | null;
  source_confidence: number;
  notes: string | null;
  metadata: Record<string, unknown> | null;
}

export interface TransferEventRead extends TransferEventCreate {
  id: string;
  event_id: string;
  fee_amount_eur: number | null;
  is_superseded: boolean;
  created_at: string;
}

// =============================================================================
// SIGNAL EVENT
// =============================================================================

export interface SignalEventCreate {
  entity_type: EntityType;
  player_id: string | null;
  club_id: string | null;
  signal_type: SignalType;
  value_json: Record<string, unknown> | null;
  value_num: number | null;
  value_text: string | null;
  source: string;
  source_id: string | null;
  confidence: number;
  observed_at: string;
  effective_from: string;
  effective_to: string | null;
  metadata: Record<string, unknown> | null;
}

export interface SignalEventRead extends SignalEventCreate {
  id: string;
  created_at: string;
}

// =============================================================================
// PREDICTION SNAPSHOT (MARKET)
// =============================================================================

export interface PredictionBrief {
  id: string;
  to_club_id: string | null;
  to_club_name: string | null;
  horizon_days: number;
  probability: number;
  drivers_json: Record<string, number>;
  as_of: string;
  window_end: string;
}

export interface ProbabilityRow {
  player_id: string;
  player_name: string;
  player_position: string | null;
  player_nationality: string | null;
  player_photo_url: string | null;
  player_age: number | null;
  
  from_club_id: string | null;
  from_club_name: string | null;
  from_club_logo_url: string | null;
  
  to_club_id: string | null;
  to_club_name: string | null;
  to_club_logo_url: string | null;
  
  horizon_days: number;
  probability: number;
  drivers_json: Record<string, number>;
  
  market_value: number | null;
  contract_months_remaining: number | null;
  
  as_of: string;
  window_end: string;
}

export interface MarketLatestResponse {
  predictions: ProbabilityRow[];
  total: number;
  as_of: string;
  filters_applied: {
    competition_id: string | null;
    club_id: string | null;
    horizon_days: number | null;
    min_probability: number | null;
  };
}

export interface PredictionSnapshotCreate {
  player_id: string;
  from_club_id: string | null;
  to_club_id: string | null;
  horizon_days: number;
  probability: number;
  model_version: string;
  model_name: string;
  drivers_json: Record<string, number>;
  as_of: string;
  window_start: string;
  window_end: string;
  features_json: Record<string, unknown> | null;
}

// =============================================================================
// USER EVENT
// =============================================================================

export interface UserEventCreate {
  user_anon_id: string;
  session_id: string;
  event_type: UserEventType;
  event_props_json: Record<string, unknown> | null;
  player_id: string | null;
  club_id: string | null;
  occurred_at: string | null;
  device_type: string | null;
  country_code: string | null;
}

export interface UserEventResponse {
  success: boolean;
  event_id: string;
}

// =============================================================================
// ADMIN
// =============================================================================

export interface AdminResponse {
  success: boolean;
  message: string;
  details: Record<string, unknown> | null;
}

export interface MaterializedViewRefreshResponse {
  success: boolean;
  views_refreshed: string[];
  duration_ms: number;
}

// =============================================================================
// ERROR
// =============================================================================

export interface ErrorResponse {
  error: string;
  message: string;
  details: Record<string, unknown> | null;
}

export interface ValidationErrorDetail {
  loc: string[];
  msg: string;
  type: string;
}

export interface ValidationErrorResponse {
  error: string;
  message: string;
  details: ValidationErrorDetail[];
}

// =============================================================================
// PAGINATION
// =============================================================================

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// =============================================================================
// API PARAMETERS
// =============================================================================

export interface SearchParams {
  q: string;
  limit?: number;
}

export interface PlayerSignalsParams {
  as_of?: string;
  signal_type?: SignalType;
  limit?: number;
}

export interface PlayerPredictionsParams {
  as_of?: string;
  horizon_days?: number;
  limit?: number;
}

export interface MarketLatestParams {
  competition_id?: string;
  club_id?: string;
  horizon_days?: number;
  min_probability?: number;
  limit?: number;
}
