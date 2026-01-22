'use client';

import { useState, useEffect } from 'react';
import { Star, Bell, BellOff } from 'lucide-react';
import { isInWatchlist, addToWatchlist, removeFromWatchlist } from '@/lib/watchlist';
import { track } from '@/lib/tracking';
import { cn } from '@/lib/utils';

interface WatchlistButtonProps {
  playerId: string;
  playerName: string;
  clubName: string | null;
  position: string | null;
  className?: string;
  showLabel?: boolean;
}

export function WatchlistButton({ 
  playerId, 
  playerName, 
  clubName, 
  position,
  className,
  showLabel = true 
}: WatchlistButtonProps) {
  const [isWatching, setIsWatching] = useState(false);
  const [isAnimating, setIsAnimating] = useState(false);
  
  // Check initial state
  useEffect(() => {
    setIsWatching(isInWatchlist(playerId));
    
    // Listen for updates
    const handleUpdate = () => setIsWatching(isInWatchlist(playerId));
    window.addEventListener('watchlist-updated', handleUpdate);
    return () => window.removeEventListener('watchlist-updated', handleUpdate);
  }, [playerId]);
  
  const handleClick = () => {
    setIsAnimating(true);
    setTimeout(() => setIsAnimating(false), 300);
    
    if (isWatching) {
      removeFromWatchlist(playerId);
      track.watchlistRemove(playerId);
    } else {
      addToWatchlist({
        playerId,
        playerName,
        clubName,
        position,
        alertOnTransfer: true,
        alertThreshold: 0.5,
      });
      track.watchlistAdd(playerId);
    }
  };
  
  return (
    <button
      onClick={handleClick}
      className={cn(
        'flex items-center gap-2 px-3 py-2 rounded transition-all',
        isWatching 
          ? 'bg-bloomberg-orange/20 text-bloomberg-orange hover:bg-bloomberg-orange/30' 
          : 'bg-terminal-border text-text-secondary hover:text-text-primary hover:bg-terminal-border-bright',
        isAnimating && 'scale-95',
        className
      )}
    >
      <Star className={cn('w-4 h-4 transition-transform', isAnimating && 'scale-125', isWatching && 'fill-bloomberg-orange')} />
      {showLabel && (
        <span className="text-sm font-medium">
          {isWatching ? 'Watching' : 'Watch'}
        </span>
      )}
    </button>
  );
}

// Alert toggle for watchlist page
export function AlertToggle({ playerId, enabled, onToggle }: { playerId: string; enabled: boolean; onToggle: (enabled: boolean) => void }) {
  return (
    <button
      onClick={() => onToggle(!enabled)}
      className={cn(
        'p-2 rounded transition-colors',
        enabled ? 'text-bloomberg-orange hover:bg-bloomberg-orange/20' : 'text-text-muted hover:bg-terminal-border'
      )}
      title={enabled ? 'Alerts enabled' : 'Alerts disabled'}
    >
      {enabled ? <Bell className="w-4 h-4" /> : <BellOff className="w-4 h-4" />}
    </button>
  );
}
