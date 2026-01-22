'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { Star, Trash2, Bell, BellOff, ArrowUpRight } from 'lucide-react';
import { getWatchlist, removeFromWatchlist, updateWatchlistItem, WatchlistItem } from '@/lib/watchlist';
import { cn, formatRelativeTime, getPositionColor, truncate } from '@/lib/utils';

export default function WatchlistPage() {
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [mounted, setMounted] = useState(false);
  
  useEffect(() => {
    setMounted(true);
    setWatchlist(getWatchlist());
    
    const handleUpdate = (e: CustomEvent<WatchlistItem[]>) => {
      setWatchlist(e.detail);
    };
    
    window.addEventListener('watchlist-updated', handleUpdate as EventListener);
    return () => window.removeEventListener('watchlist-updated', handleUpdate as EventListener);
  }, []);
  
  const handleRemove = (playerId: string) => {
    removeFromWatchlist(playerId);
  };
  
  const handleToggleAlert = (playerId: string, currentValue: boolean) => {
    updateWatchlistItem(playerId, { alertOnTransfer: !currentValue });
  };
  
  // Prevent hydration mismatch
  if (!mounted) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-6">
        <div className="h-96 flex items-center justify-center">
          <div className="w-6 h-6 border-2 border-bloomberg-orange/30 border-t-bloomberg-orange rounded-full animate-spin" />
        </div>
      </div>
    );
  }
  
  return (
    <div className="max-w-4xl mx-auto px-4 py-6">
      {/* Header */}
      <header className="mb-8">
        <div className="text-sm text-text-muted mb-4">
          <Link href="/" className="hover:text-text-secondary">Home</Link>
          <span className="mx-2">/</span>
          <span>Watchlist</span>
        </div>
        
        <div className="flex items-center gap-3">
          <Star className="w-8 h-8 text-bloomberg-yellow" />
          <div>
            <h1 className="text-2xl md:text-3xl font-bold text-text-primary">
              My Watchlist
            </h1>
            <p className="text-text-secondary">
              {watchlist.length} player{watchlist.length !== 1 ? 's' : ''} tracked
            </p>
          </div>
        </div>
      </header>
      
      {/* Watchlist */}
      {watchlist.length > 0 ? (
        <div className="panel">
          <div className="divide-y divide-terminal-border">
            {watchlist.map((item) => (
              <div 
                key={item.playerId}
                className="p-4 flex items-center gap-4 hover:bg-terminal-border/20 transition-colors"
              >
                {/* Player info */}
                <div className="flex-1 min-w-0">
                  <Link 
                    href={`/p/${item.playerId}`}
                    className="group flex items-center gap-3"
                  >
                    <div className="w-10 h-10 rounded-full bg-terminal-border flex items-center justify-center text-sm font-medium">
                      {item.playerName.split(' ').map(n => n[0]).join('').slice(0, 2)}
                    </div>
                    <div>
                      <div className="font-medium group-hover:text-bloomberg-orange transition-colors">
                        {truncate(item.playerName, 25)}
                      </div>
                      <div className="text-sm text-text-secondary flex items-center gap-2">
                        <span className={getPositionColor(item.position)}>{item.position || 'N/A'}</span>
                        {item.clubName && (
                          <>
                            <span>•</span>
                            <span>{truncate(item.clubName, 15)}</span>
                          </>
                        )}
                      </div>
                    </div>
                  </Link>
                </div>
                
                {/* Added time */}
                <div className="text-xs text-text-muted hidden md:block">
                  Added {formatRelativeTime(item.addedAt)}
                </div>
                
                {/* Actions */}
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleToggleAlert(item.playerId, item.alertOnTransfer)}
                    className={cn(
                      'p-2 rounded transition-colors',
                      item.alertOnTransfer 
                        ? 'text-bloomberg-orange hover:bg-bloomberg-orange/20' 
                        : 'text-text-muted hover:bg-terminal-border'
                    )}
                    title={item.alertOnTransfer ? 'Alerts enabled' : 'Alerts disabled'}
                  >
                    {item.alertOnTransfer ? <Bell className="w-4 h-4" /> : <BellOff className="w-4 h-4" />}
                  </button>
                  
                  <Link
                    href={`/p/${item.playerId}`}
                    className="p-2 text-text-muted hover:text-text-primary hover:bg-terminal-border rounded transition-colors"
                  >
                    <ArrowUpRight className="w-4 h-4" />
                  </Link>
                  
                  <button
                    onClick={() => handleRemove(item.playerId)}
                    className="p-2 text-text-muted hover:text-bloomberg-red hover:bg-bloomberg-red/10 rounded transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="panel">
          <div className="p-12 text-center">
            <Star className="w-12 h-12 text-text-muted mx-auto mb-4" />
            <h2 className="text-lg font-medium text-text-primary mb-2">No players in watchlist</h2>
            <p className="text-text-secondary mb-6">
              Add players to your watchlist to track their transfer probabilities
            </p>
            <Link
              href="/market"
              className="btn btn-primary"
            >
              Browse Market
            </Link>
          </div>
        </div>
      )}
      
      {/* Alert info */}
      {watchlist.length > 0 && (
        <div className="mt-6 p-4 rounded-lg bg-terminal-panel border border-terminal-border">
          <div className="flex items-start gap-3">
            <Bell className="w-5 h-5 text-bloomberg-orange flex-shrink-0 mt-0.5" />
            <div>
              <h3 className="font-medium text-text-primary mb-1">Transfer Alerts (Coming Soon)</h3>
              <p className="text-sm text-text-secondary">
                Enable alerts to get notified when a player's transfer probability changes significantly 
                or when a transfer is confirmed. Email notifications coming in the next update.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
