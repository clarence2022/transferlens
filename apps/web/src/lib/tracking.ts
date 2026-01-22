/**
 * User Event Tracking
 * 
 * Sends events to POST /events/user for:
 * - page_view
 * - player_view
 * - club_view
 * - search
 * - watchlist_add/remove
 * - share_click
 * - compare_use
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Session and user management
const SESSION_KEY = 'tl_session_id';
const USER_KEY = 'tl_anon_id';

function generateId(): string {
  return `${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 11)}`;
}

export function getSessionId(): string {
  if (typeof window === 'undefined') return '';
  
  let sessionId = sessionStorage.getItem(SESSION_KEY);
  if (!sessionId) {
    sessionId = `sess_${generateId()}`;
    sessionStorage.setItem(SESSION_KEY, sessionId);
  }
  return sessionId;
}

export function getAnonUserId(): string {
  if (typeof window === 'undefined') return '';
  
  let userId = localStorage.getItem(USER_KEY);
  if (!userId) {
    userId = `anon_${generateId()}`;
    localStorage.setItem(USER_KEY, userId);
  }
  return userId;
}

export type EventType =
  | 'page_view'
  | 'player_view'
  | 'club_view'
  | 'transfer_view'
  | 'prediction_view'
  | 'watchlist_add'
  | 'watchlist_remove'
  | 'search'
  | 'share'
  | 'filter_apply'
  | 'comparison_view';

interface TrackEventParams {
  event_type: EventType;
  player_id?: string;
  club_id?: string;
  props?: Record<string, unknown>;
}

export async function trackEvent(params: TrackEventParams): Promise<void> {
  // Don't track on server side
  if (typeof window === 'undefined') return;
  
  const payload = {
    user_anon_id: getAnonUserId(),
    session_id: getSessionId(),
    event_type: params.event_type,
    player_id: params.player_id || null,
    club_id: params.club_id || null,
    event_props_json: {
      ...params.props,
      page_url: window.location.pathname,
      referrer: document.referrer || null,
    },
    device_type: getDeviceType(),
  };
  
  try {
    // Fire and forget - don't block UI
    fetch(`${API_BASE_URL}/api/v1/events/user`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      keepalive: true, // Allow request to complete even if page navigates
    }).catch(() => {
      // Silently fail - tracking shouldn't break the app
    });
  } catch {
    // Silently fail
  }
}

function getDeviceType(): string {
  if (typeof window === 'undefined') return 'unknown';
  
  const ua = navigator.userAgent;
  if (/tablet|ipad|playbook|silk/i.test(ua)) return 'tablet';
  if (/mobile|iphone|ipod|android|blackberry|mini|windows\sce|palm/i.test(ua)) return 'mobile';
  return 'desktop';
}

// Convenience functions
export const track = {
  pageView: (props?: Record<string, unknown>) => 
    trackEvent({ event_type: 'page_view', props }),
  
  playerView: (playerId: string, props?: Record<string, unknown>) =>
    trackEvent({ event_type: 'player_view', player_id: playerId, props }),
  
  clubView: (clubId: string, props?: Record<string, unknown>) =>
    trackEvent({ event_type: 'club_view', club_id: clubId, props }),
  
  search: (query: string, resultsCount: number) =>
    trackEvent({ event_type: 'search', props: { query, results_count: resultsCount } }),
  
  watchlistAdd: (playerId: string) =>
    trackEvent({ event_type: 'watchlist_add', player_id: playerId }),
  
  watchlistRemove: (playerId: string) =>
    trackEvent({ event_type: 'watchlist_remove', player_id: playerId }),
  
  shareClick: (playerId: string, platform?: string) =>
    trackEvent({ event_type: 'share', player_id: playerId, props: { platform } }),
  
  compareUse: (player1Id: string, player2Id: string) =>
    trackEvent({ event_type: 'comparison_view', props: { player1_id: player1Id, player2_id: player2Id } }),
};
