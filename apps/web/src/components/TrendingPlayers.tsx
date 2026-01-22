'use client';

import Link from 'next/link';
import { TrendingUp, ArrowUpRight, Flame } from 'lucide-react';
import { ProbabilityRow } from '@/lib/api';
import { cn, formatProbability, getProbabilityColor, getPositionColor, truncate } from '@/lib/utils';

interface TrendingPlayersProps {
  players: ProbabilityRow[];
  className?: string;
}

export function TrendingPlayers({ players, className }: TrendingPlayersProps) {
  if (players.length === 0) {
    return (
      <div className={cn('text-center py-8 text-text-secondary', className)}>
        No trending players
      </div>
    );
  }
  
  return (
    <div className={cn('space-y-2', className)}>
      {players.slice(0, 10).map((player, index) => (
        <Link
          key={`${player.player_id}-${index}`}
          href={`/p/${player.player_id}`}
          className="group flex items-center gap-3 p-3 rounded hover:bg-terminal-border/50 transition-colors"
        >
          {/* Rank */}
          <div className={cn(
            'w-6 h-6 rounded flex items-center justify-center text-xs font-bold',
            index < 3 ? 'bg-bloomberg-orange/20 text-bloomberg-orange' : 'bg-terminal-border text-text-muted'
          )}>
            {index + 1}
          </div>
          
          {/* Player info */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="font-medium text-text-primary group-hover:text-bloomberg-orange transition-colors">
                {truncate(player.player_name, 18)}
              </span>
              {index < 3 && (
                <Flame className="w-3.5 h-3.5 text-bloomberg-orange" />
              )}
            </div>
            <div className="text-xs text-text-secondary flex items-center gap-1">
              <span className={getPositionColor(player.player_position)}>{player.player_position}</span>
              <span>•</span>
              <span>{truncate(player.from_club_name || 'Unknown', 12)}</span>
            </div>
          </div>
          
          {/* Probability */}
          <div className="text-right">
            <div className={cn('font-mono text-sm font-semibold', getProbabilityColor(player.probability))}>
              {formatProbability(player.probability)}
            </div>
            <div className="text-xs text-text-muted flex items-center justify-end gap-1">
              <ArrowUpRight className="w-3 h-3" />
              {player.to_club_name ? truncate(player.to_club_name, 10) : 'TBD'}
            </div>
          </div>
        </Link>
      ))}
    </div>
  );
}

// Horizontal carousel version for mobile
export function TrendingPlayersCarousel({ players, className }: TrendingPlayersProps) {
  return (
    <div className={cn('flex gap-3 overflow-x-auto pb-2 hide-scrollbar', className)}>
      {players.slice(0, 8).map((player, index) => (
        <Link
          key={`${player.player_id}-${index}`}
          href={`/p/${player.player_id}`}
          className="flex-shrink-0 w-[160px] p-3 rounded-lg bg-terminal-panel border border-terminal-border hover:border-bloomberg-orange/50 transition-colors"
        >
          <div className="flex items-center gap-2 mb-2">
            <span className={cn(
              'w-5 h-5 rounded flex items-center justify-center text-xs font-bold',
              index < 3 ? 'bg-bloomberg-orange text-white' : 'bg-terminal-border text-text-muted'
            )}>
              {index + 1}
            </span>
            <Flame className={cn('w-3 h-3', index < 3 ? 'text-bloomberg-orange' : 'text-transparent')} />
          </div>
          
          <div className="font-medium text-sm truncate">{player.player_name}</div>
          <div className="text-xs text-text-secondary truncate mb-2">
            {player.from_club_name}
          </div>
          
          <div className={cn('font-mono text-lg font-bold', getProbabilityColor(player.probability))}>
            {formatProbability(player.probability)}
          </div>
        </Link>
      ))}
    </div>
  );
}
