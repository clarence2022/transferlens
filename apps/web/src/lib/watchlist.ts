/**
 * Watchlist Management
 * 
 * MVP: Uses localStorage for persistence
 * Later: Sync with backend when user accounts are added
 */

const WATCHLIST_KEY = 'tl_watchlist';

export interface WatchlistItem {
  playerId: string;
  playerName: string;
  clubName: string | null;
  position: string | null;
  addedAt: string;
  alertOnTransfer: boolean;
  alertThreshold: number; // Probability threshold for alerts
}

export function getWatchlist(): WatchlistItem[] {
  if (typeof window === 'undefined') return [];
  
  try {
    const data = localStorage.getItem(WATCHLIST_KEY);
    return data ? JSON.parse(data) : [];
  } catch {
    return [];
  }
}

export function addToWatchlist(item: Omit<WatchlistItem, 'addedAt'>): void {
  if (typeof window === 'undefined') return;
  
  const watchlist = getWatchlist();
  
  // Don't add duplicates
  if (watchlist.some(w => w.playerId === item.playerId)) return;
  
  watchlist.push({
    ...item,
    addedAt: new Date().toISOString(),
  });
  
  localStorage.setItem(WATCHLIST_KEY, JSON.stringify(watchlist));
  
  // Dispatch event for real-time updates
  window.dispatchEvent(new CustomEvent('watchlist-updated', { detail: watchlist }));
}

export function removeFromWatchlist(playerId: string): void {
  if (typeof window === 'undefined') return;
  
  const watchlist = getWatchlist().filter(w => w.playerId !== playerId);
  localStorage.setItem(WATCHLIST_KEY, JSON.stringify(watchlist));
  
  window.dispatchEvent(new CustomEvent('watchlist-updated', { detail: watchlist }));
}

export function isInWatchlist(playerId: string): boolean {
  return getWatchlist().some(w => w.playerId === playerId);
}

export function updateWatchlistItem(playerId: string, updates: Partial<WatchlistItem>): void {
  if (typeof window === 'undefined') return;
  
  const watchlist = getWatchlist().map(w => 
    w.playerId === playerId ? { ...w, ...updates } : w
  );
  
  localStorage.setItem(WATCHLIST_KEY, JSON.stringify(watchlist));
  window.dispatchEvent(new CustomEvent('watchlist-updated', { detail: watchlist }));
}
