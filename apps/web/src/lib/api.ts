/**
 * API Client for TransferLens
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Types matching the API
export interface SearchResult {
  type: 'player' | 'club';
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

export interface ClubBrief {
  id: string;
  name: string;
  short_name: string | null;
  country: string;
  logo_url: string | null;
}

export interface SignalDelta {
  signal_type: string;
  description: string;
  old_value: unknown;
  new_value: unknown;
  change_percent: number | null;
  severity: 'info' | 'warning' | 'alert';
  observed_at: string;
}

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

export interface TransferBrief {
  id: string;
  event_id: string;
  player_id: string;
  player_name: string | null;
  from_club_id: string | null;
  from_club_name: string | null;
  to_club_id: string;
  to_club_name: string | null;
  transfer_type: string;
  transfer_date: string;
  fee_amount_eur: number | null;
}

export interface PlayerDetail {
  id: string;
  name: string;
  full_name: string | null;
  date_of_birth: string | null;
  nationality: string | null;
  position: string | null;
  photo_url: string | null;
  current_club_id: string | null;
  contract_until: string | null;
  current_club: ClubBrief | null;
  age: number | null;
  market_value: number | null;
  contract_months_remaining: number | null;
  goals_last_10: number | null;
  assists_last_10: number | null;
  latest_predictions: PredictionBrief[];
  what_changed: SignalDelta[];
  transfer_history: TransferBrief[];
}

export interface PlayerBrief {
  id: string;
  name: string;
  position: string | null;
  nationality: string | null;
  photo_url: string | null;
  current_club_id: string | null;
}

export interface CompetitionBrief {
  id: string;
  name: string;
  short_name: string | null;
  country: string;
}

export interface ClubDetail {
  id: string;
  name: string;
  short_name: string | null;
  country: string;
  city: string | null;
  stadium: string | null;
  logo_url: string | null;
  primary_color: string | null;
  competition: CompetitionBrief | null;
  squad: PlayerBrief[];
  squad_count: number;
  outgoing_probabilities: ProbabilityRow[];
  incoming_probabilities: ProbabilityRow[];
  recent_transfers_in: TransferBrief[];
  recent_transfers_out: TransferBrief[];
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
  filters_applied: Record<string, unknown>;
}

// API Functions
export async function search(q: string, limit = 20): Promise<SearchResponse> {
  const res = await fetch(`${API_BASE_URL}/api/v1/search?q=${encodeURIComponent(q)}&limit=${limit}`);
  if (!res.ok) throw new Error('Search failed');
  return res.json();
}

export async function getPlayer(id: string): Promise<PlayerDetail> {
  const res = await fetch(`${API_BASE_URL}/api/v1/players/${id}`, {
    next: { revalidate: 60 }, // ISR: 60 second cache
  });
  if (!res.ok) throw new Error('Player not found');
  return res.json();
}

export async function getPlayerPredictions(
  id: string, 
  params?: { as_of?: string; horizon_days?: number }
): Promise<PredictionBrief[]> {
  const searchParams = new URLSearchParams();
  if (params?.as_of) searchParams.set('as_of', params.as_of);
  if (params?.horizon_days) searchParams.set('horizon_days', String(params.horizon_days));
  
  const url = `${API_BASE_URL}/api/v1/players/${id}/predictions?${searchParams}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error('Failed to fetch predictions');
  return res.json();
}

export async function getClub(id: string): Promise<ClubDetail> {
  const res = await fetch(`${API_BASE_URL}/api/v1/clubs/${id}`, {
    next: { revalidate: 60 },
  });
  if (!res.ok) throw new Error('Club not found');
  return res.json();
}

export async function getMarketLatest(params?: {
  competition_id?: string;
  club_id?: string;
  horizon_days?: number;
  min_probability?: number;
  limit?: number;
}): Promise<MarketLatestResponse> {
  const searchParams = new URLSearchParams();
  if (params?.competition_id) searchParams.set('competition_id', params.competition_id);
  if (params?.club_id) searchParams.set('club_id', params.club_id);
  if (params?.horizon_days) searchParams.set('horizon_days', String(params.horizon_days));
  if (params?.min_probability) searchParams.set('min_probability', String(params.min_probability));
  if (params?.limit) searchParams.set('limit', String(params.limit));
  
  const url = `${API_BASE_URL}/api/v1/market/latest?${searchParams}`;
  const res = await fetch(url, {
    next: { revalidate: 30 }, // 30 second cache
  });
  if (!res.ok) throw new Error('Failed to fetch market data');
  return res.json();
}

// Client-side API
export const clientApi = {
  search,
  getPlayer,
  getClub,
  getMarketLatest,
  getPlayerPredictions,
};
