'use client';

import Link from 'next/link';
import { ArrowRight, TrendingUp, TrendingDown, Minus, Building2 } from 'lucide-react';
import { PredictionBrief } from '@/lib/api';
import { cn, formatProbability, getProbabilityColor, getProbabilityBgColor, truncate } from '@/lib/utils';

interface DestinationCardProps {
  prediction: PredictionBrief;
  rank?: number;
  className?: string;
}

export function DestinationCard({ prediction, rank, className }: DestinationCardProps) {
  const isTopDestination = rank === 1;
  
  return (
    <div className={cn(
      'relative p-4 rounded-lg border transition-all',
      isTopDestination 
        ? 'bg-bloomberg-orange/10 border-bloomberg-orange/50' 
        : 'bg-terminal-panel border-terminal-border hover:border-terminal-border-bright',
      className
    )}>
      {rank && (
        <div className={cn(
          'absolute -top-2 -left-2 w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold',
          isTopDestination ? 'bg-bloomberg-orange text-white' : 'bg-terminal-border text-text-secondary'
        )}>
          {rank}
        </div>
      )}
      
      <div className="flex items-start justify-between gap-4">
        {/* Club info */}
        <div className="flex items-center gap-3">
          <div className={cn(
            'w-10 h-10 rounded-lg flex items-center justify-center',
            isTopDestination ? 'bg-bloomberg-orange/20' : 'bg-terminal-border'
          )}>
            <Building2 className={cn(
              'w-5 h-5',
              isTopDestination ? 'text-bloomberg-orange' : 'text-text-muted'
            )} />
          </div>
          <div>
            {prediction.to_club_id ? (
              <Link 
                href={`/c/${prediction.to_club_id}`}
                className="font-semibold text-text-primary hover:text-bloomberg-orange transition-colors"
              >
                {truncate(prediction.to_club_name || 'Unknown', 20)}
              </Link>
            ) : (
              <span className="font-semibold text-text-secondary">Any Transfer</span>
            )}
            <div className="text-xs text-text-muted">
              {prediction.horizon_days}d window
            </div>
          </div>
        </div>
        
        {/* Probability */}
        <div className="text-right">
          <div className={cn(
            'text-2xl font-mono font-bold',
            getProbabilityColor(prediction.probability)
          )}>
            {formatProbability(prediction.probability)}
          </div>
          <div className={cn(
            'mt-1 h-1.5 w-20 rounded-full overflow-hidden',
            isTopDestination ? 'bg-bloomberg-orange/20' : 'bg-terminal-border'
          )}>
            <div 
              className={cn(
                'h-full rounded-full transition-all duration-500',
                isTopDestination ? 'bg-bloomberg-orange' : getProbabilityColor(prediction.probability).replace('text-', 'bg-')
              )}
              style={{ width: `${prediction.probability * 100}%` }}
            />
          </div>
        </div>
      </div>
      
      {/* Drivers */}
      {prediction.drivers_json && Object.keys(prediction.drivers_json).length > 0 && (
        <div className="mt-3 pt-3 border-t border-terminal-border/50">
          <div className="text-xs text-text-muted mb-2">Key factors:</div>
          <div className="flex flex-wrap gap-2">
            {Object.entries(prediction.drivers_json)
              .sort(([, a], [, b]) => b - a)
              .slice(0, 3)
              .map(([key, value]) => (
                <span 
                  key={key}
                  className="px-2 py-0.5 rounded bg-terminal-border text-xs text-text-secondary"
                >
                  {formatDriverName(key)} {Math.round(value * 100)}%
                </span>
              ))}
          </div>
        </div>
      )}
    </div>
  );
}

function formatDriverName(key: string): string {
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, l => l.toUpperCase())
    .replace('Contract Months Remaining', 'Contract')
    .replace('Market Value', 'Value')
    .replace('User Destination Cooccurrence', 'Interest');
}

// Horizontal scrollable list
export function DestinationList({ predictions, className }: { predictions: PredictionBrief[]; className?: string }) {
  // Group by horizon
  const by90 = predictions.filter(p => p.horizon_days === 90);
  const by30 = predictions.filter(p => p.horizon_days === 30);
  const by180 = predictions.filter(p => p.horizon_days === 180);
  
  // Use 90-day predictions by default, fall back to others
  const displayPredictions = by90.length > 0 ? by90 : by30.length > 0 ? by30 : by180;
  
  // Sort by probability and dedupe by club
  const seen = new Set<string>();
  const uniquePredictions = displayPredictions
    .sort((a, b) => b.probability - a.probability)
    .filter(p => {
      const key = p.to_club_id || 'any';
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .slice(0, 5);
  
  return (
    <div className={cn('space-y-3', className)}>
      {uniquePredictions.map((prediction, index) => (
        <DestinationCard 
          key={`${prediction.to_club_id || 'any'}-${index}`}
          prediction={prediction}
          rank={index + 1}
        />
      ))}
    </div>
  );
}
