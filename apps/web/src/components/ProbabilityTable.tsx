'use client';

import Link from 'next/link';
import { ArrowUpRight, TrendingUp } from 'lucide-react';
import { ProbabilityRow } from '@/lib/api';
import { cn, formatProbability, formatCurrency, getProbabilityColor, getPositionColor, truncate } from '@/lib/utils';

interface ProbabilityTableProps {
  predictions: ProbabilityRow[];
  showPlayer?: boolean;
  showFromClub?: boolean;
  showToClub?: boolean;
  compact?: boolean;
  className?: string;
}

export function ProbabilityTable({ 
  predictions, 
  showPlayer = true, 
  showFromClub = true, 
  showToClub = true,
  compact = false,
  className 
}: ProbabilityTableProps) {
  if (predictions.length === 0) {
    return (
      <div className="text-center py-8 text-text-secondary">
        No predictions available
      </div>
    );
  }
  
  return (
    <div className={cn('overflow-x-auto', className)}>
      <table className="data-table">
        <thead>
          <tr>
            {showPlayer && <th className="min-w-[180px]">Player</th>}
            {showFromClub && <th className="min-w-[120px]">From</th>}
            {showToClub && <th className="min-w-[120px]">To</th>}
            <th className="w-[100px] text-right">Probability</th>
            {!compact && <th className="w-[100px] text-right">Value</th>}
            {!compact && <th className="w-[80px] text-right">Contract</th>}
            <th className="w-[60px]"></th>
          </tr>
        </thead>
        <tbody>
          {predictions.map((pred, index) => (
            <tr key={`${pred.player_id}-${pred.to_club_id}-${index}`} className="group">
              {showPlayer && (
                <td>
                  <Link href={`/p/${pred.player_id}`} className="flex items-center gap-2 hover:text-bloomberg-orange transition-colors">
                    <div className="w-8 h-8 rounded-full bg-terminal-border flex items-center justify-center text-xs font-medium">
                      {pred.player_name?.split(' ').map(n => n[0]).join('').slice(0, 2)}
                    </div>
                    <div>
                      <div className="font-medium">{truncate(pred.player_name || 'Unknown', 20)}</div>
                      <div className="text-xs text-text-secondary flex items-center gap-1">
                        <span className={getPositionColor(pred.player_position)}>{pred.player_position}</span>
                        {pred.player_age && <span>• {pred.player_age}y</span>}
                      </div>
                    </div>
                  </Link>
                </td>
              )}
              
              {showFromClub && (
                <td>
                  {pred.from_club_id ? (
                    <Link href={`/c/${pred.from_club_id}`} className="text-text-secondary hover:text-text-primary transition-colors">
                      {truncate(pred.from_club_name || '-', 15)}
                    </Link>
                  ) : (
                    <span className="text-text-muted">-</span>
                  )}
                </td>
              )}
              
              {showToClub && (
                <td>
                  {pred.to_club_id ? (
                    <Link href={`/c/${pred.to_club_id}`} className="flex items-center gap-1 text-text-secondary hover:text-text-primary transition-colors">
                      <ArrowUpRight className="w-3 h-3 text-bloomberg-orange" />
                      {truncate(pred.to_club_name || 'Unknown', 15)}
                    </Link>
                  ) : (
                    <span className="text-text-muted flex items-center gap-1">
                      <TrendingUp className="w-3 h-3" />
                      Any move
                    </span>
                  )}
                </td>
              )}
              
              <td className="text-right">
                <div className="flex flex-col items-end">
                  <span className={cn('font-mono font-semibold', getProbabilityColor(pred.probability))}>
                    {formatProbability(pred.probability)}
                  </span>
                  <div className="w-16 h-1 bg-terminal-border rounded-full overflow-hidden mt-1">
                    <div 
                      className={cn('h-full rounded-full transition-all', getProbabilityColor(pred.probability).replace('text-', 'bg-'))}
                      style={{ width: `${pred.probability * 100}%` }}
                    />
                  </div>
                </div>
              </td>
              
              {!compact && (
                <td className="text-right font-mono text-text-secondary">
                  {formatCurrency(pred.market_value)}
                </td>
              )}
              
              {!compact && (
                <td className="text-right">
                  {pred.contract_months_remaining != null ? (
                    <span className={cn(
                      'font-mono',
                      pred.contract_months_remaining <= 12 ? 'text-bloomberg-red' :
                      pred.contract_months_remaining <= 24 ? 'text-bloomberg-orange' : 'text-text-secondary'
                    )}>
                      {pred.contract_months_remaining}mo
                    </span>
                  ) : (
                    <span className="text-text-muted">-</span>
                  )}
                </td>
              )}
              
              <td>
                <Link 
                  href={`/p/${pred.player_id}`}
                  className="opacity-0 group-hover:opacity-100 transition-opacity btn btn-ghost px-2 py-1"
                >
                  <ArrowUpRight className="w-4 h-4" />
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Compact version for sidebars
export function ProbabilityList({ predictions, className }: { predictions: ProbabilityRow[]; className?: string }) {
  return (
    <div className={cn('space-y-2', className)}>
      {predictions.slice(0, 5).map((pred, index) => (
        <Link
          key={`${pred.player_id}-${pred.to_club_id}-${index}`}
          href={`/p/${pred.player_id}`}
          className="flex items-center gap-3 p-2 rounded hover:bg-terminal-border/50 transition-colors"
        >
          <span className="text-xs text-text-muted w-4">{index + 1}.</span>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium truncate">{pred.player_name}</div>
            <div className="text-xs text-text-secondary">
              {pred.from_club_name} → {pred.to_club_name || 'TBD'}
            </div>
          </div>
          <span className={cn('font-mono text-sm font-semibold', getProbabilityColor(pred.probability))}>
            {formatProbability(pred.probability)}
          </span>
        </Link>
      ))}
    </div>
  );
}
