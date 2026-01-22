import { Suspense } from 'react';
import { notFound } from 'next/navigation';
import type { Metadata } from 'next';
import Link from 'next/link';
import { Calendar, MapPin, Ruler, Target, Clock, TrendingUp, ArrowRight, Building2 } from 'lucide-react';

import { getPlayer, getPlayerPredictions } from '@/lib/api';
import { WatchlistButton } from '@/components/WatchlistButton';
import { ShareCard } from '@/components/ShareCard';
import { WhatChanged } from '@/components/WhatChanged';
import { DestinationList } from '@/components/DestinationCard';
import { ProbabilityChart } from '@/components/ProbabilityChart';
import { PlayerPageTracker } from './tracker';
import { cn, formatCurrency, formatDate, getPositionColor, getCountryFlag } from '@/lib/utils';

export const revalidate = 60; // ISR: 60 second cache

interface Props {
  params: { playerId: string };
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  try {
    const player = await getPlayer(params.playerId);
    const topDest = player.latest_predictions?.[0];
    
    const description = topDest 
      ? `${player.name} → ${topDest.to_club_name}: ${(topDest.probability * 100).toFixed(0)}% probability`
      : `${player.name} transfer predictions and market intelligence`;
    
    return {
      title: `${player.name} - TransferLens`,
      description,
      openGraph: {
        title: `${player.name} | TransferLens`,
        description,
        type: 'profile',
        images: [`/api/og/player/${params.playerId}`],
      },
      twitter: {
        card: 'summary_large_image',
        title: `${player.name} | TransferLens`,
        description,
        images: [`/api/og/player/${params.playerId}`],
      },
    };
  } catch {
    return {
      title: 'Player Not Found - TransferLens',
    };
  }
}

export default async function PlayerPage({ params }: Props) {
  let player;
  try {
    player = await getPlayer(params.playerId);
  } catch {
    notFound();
  }
  
  // Get historical predictions for chart
  let historicalPredictions = [];
  try {
    historicalPredictions = await getPlayerPredictions(params.playerId, { limit: 50 });
  } catch {
    // Non-critical, continue without
  }
  
  const topPrediction = player.latest_predictions?.[0];
  
  return (
    <div className="max-w-6xl mx-auto px-4 py-6">
      {/* Track page view */}
      <PlayerPageTracker playerId={params.playerId} />
      
      {/* Header */}
      <header className="mb-8">
        {/* Breadcrumb */}
        <div className="text-sm text-text-muted mb-4">
          <Link href="/" className="hover:text-text-secondary">Home</Link>
          <span className="mx-2">/</span>
          <span>Player</span>
        </div>
        
        <div className="flex flex-col md:flex-row md:items-start gap-6">
          {/* Player avatar */}
          <div className="flex-shrink-0">
            <div className="w-24 h-24 md:w-32 md:h-32 rounded-xl bg-terminal-panel border border-terminal-border flex items-center justify-center">
              {player.photo_url ? (
                <img src={player.photo_url} alt={player.name} className="w-full h-full object-cover rounded-xl" />
              ) : (
                <span className="text-3xl md:text-4xl font-bold text-text-muted">
                  {player.name.split(' ').map(n => n[0]).join('').slice(0, 2)}
                </span>
              )}
            </div>
          </div>
          
          {/* Player info */}
          <div className="flex-1 min-w-0">
            <div className="flex flex-wrap items-center gap-3 mb-2">
              <h1 className="text-2xl md:text-3xl font-bold text-text-primary">
                {player.name}
              </h1>
              <span className={cn(
                'px-2 py-0.5 rounded text-sm font-medium',
                'bg-terminal-border',
                getPositionColor(player.position)
              )}>
                {player.position || 'N/A'}
              </span>
            </div>
            
            {/* Current club */}
            {player.current_club && (
              <Link 
                href={`/c/${player.current_club.id}`}
                className="inline-flex items-center gap-2 text-text-secondary hover:text-bloomberg-orange transition-colors mb-4"
              >
                <Building2 className="w-4 h-4" />
                {player.current_club.name}
                {player.current_club.country && (
                  <span className="text-text-muted">• {player.current_club.country}</span>
                )}
              </Link>
            )}
            
            {/* Stats row */}
            <div className="flex flex-wrap gap-4 text-sm">
              {player.age && (
                <div className="flex items-center gap-1.5 text-text-secondary">
                  <Calendar className="w-4 h-4 text-text-muted" />
                  <span>{player.age} years old</span>
                </div>
              )}
              {player.nationality && (
                <div className="flex items-center gap-1.5 text-text-secondary">
                  <span>{getCountryFlag(player.nationality)}</span>
                  <span>{player.nationality}</span>
                </div>
              )}
              {player.market_value && (
                <div className="flex items-center gap-1.5 text-text-secondary">
                  <Target className="w-4 h-4 text-bloomberg-green" />
                  <span className="text-bloomberg-green font-mono">{formatCurrency(player.market_value)}</span>
                </div>
              )}
              {player.contract_months_remaining != null && (
                <div className={cn(
                  'flex items-center gap-1.5',
                  player.contract_months_remaining <= 12 ? 'text-bloomberg-red' :
                  player.contract_months_remaining <= 24 ? 'text-bloomberg-orange' : 'text-text-secondary'
                )}>
                  <Clock className="w-4 h-4" />
                  <span className="font-mono">{player.contract_months_remaining}mo</span>
                  <span className="text-text-muted">remaining</span>
                </div>
              )}
            </div>
          </div>
          
          {/* Actions */}
          <div className="flex items-center gap-3 flex-shrink-0">
            <WatchlistButton
              playerId={player.id}
              playerName={player.name}
              clubName={player.current_club?.name || null}
              position={player.position}
            />
            <ShareCard
              playerId={player.id}
              playerName={player.name}
              clubName={player.current_club?.name || null}
              destinationClub={topPrediction?.to_club_name || null}
              probability={topPrediction?.probability || null}
            />
          </div>
        </div>
      </header>
      
      {/* Main content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left column - Predictions */}
        <div className="lg:col-span-2 space-y-6">
          {/* Top Destinations */}
          <section className="panel">
            <div className="panel-header">
              <h2 className="panel-title flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-bloomberg-orange" />
                Transfer Probability
              </h2>
              <span className="text-xs text-text-muted">90-day window</span>
            </div>
            <div className="p-4">
              {player.latest_predictions.length > 0 ? (
                <DestinationList predictions={player.latest_predictions} />
              ) : (
                <div className="text-center py-8 text-text-secondary">
                  No active transfer predictions
                </div>
              )}
            </div>
          </section>
          
          {/* Probability Chart */}
          {historicalPredictions.length > 1 && (
            <section className="panel">
              <div className="panel-header">
                <h2 className="panel-title">Probability History</h2>
              </div>
              <div className="p-4">
                <ProbabilityChart predictions={historicalPredictions} />
              </div>
            </section>
          )}
          
          {/* Transfer History */}
          {player.transfer_history.length > 0 && (
            <section className="panel">
              <div className="panel-header">
                <h2 className="panel-title">Transfer History</h2>
              </div>
              <div className="p-4">
                <div className="space-y-3">
                  {player.transfer_history.slice(0, 5).map((transfer) => (
                    <div key={transfer.id} className="flex items-center gap-4 py-2 border-b border-terminal-border/50 last:border-0">
                      <div className="text-xs text-text-muted w-20">
                        {formatDate(transfer.transfer_date)}
                      </div>
                      <div className="flex-1 flex items-center gap-2">
                        <span className="text-text-secondary">{transfer.from_club_name || 'Unknown'}</span>
                        <ArrowRight className="w-3 h-3 text-bloomberg-orange" />
                        <span className="text-text-primary">{transfer.to_club_name || 'Unknown'}</span>
                      </div>
                      {transfer.fee_amount_eur && (
                        <div className="font-mono text-sm text-bloomberg-green">
                          {formatCurrency(transfer.fee_amount_eur)}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </section>
          )}
        </div>
        
        {/* Right column - What Changed + Stats */}
        <div className="space-y-6">
          {/* What Changed */}
          <section className="panel">
            <div className="panel-header">
              <h2 className="panel-title">What Changed This Week</h2>
            </div>
            <div className="p-4">
              <WhatChanged changes={player.what_changed} />
            </div>
          </section>
          
          {/* Key Stats */}
          <section className="panel">
            <div className="panel-header">
              <h2 className="panel-title">Key Stats</h2>
            </div>
            <div className="p-4 space-y-4">
              <StatRow 
                label="Market Value" 
                value={formatCurrency(player.market_value)} 
                highlight={player.market_value !== null}
              />
              <StatRow 
                label="Contract Until" 
                value={formatDate(player.contract_until)} 
              />
              <StatRow 
                label="Contract Remaining" 
                value={player.contract_months_remaining ? `${player.contract_months_remaining} months` : '-'} 
                highlight={player.contract_months_remaining !== null && player.contract_months_remaining <= 12}
                highlightColor="red"
              />
              <StatRow 
                label="Goals (Last 10)" 
                value={player.goals_last_10?.toString() || '-'} 
              />
              <StatRow 
                label="Assists (Last 10)" 
                value={player.assists_last_10?.toString() || '-'} 
              />
            </div>
          </section>
          
          {/* Compare CTA */}
          <Link 
            href={`/compare?p1=${player.id}`}
            className="block p-4 rounded-lg bg-terminal-panel border border-terminal-border hover:border-bloomberg-blue/50 transition-colors"
          >
            <div className="flex items-center gap-3">
              <svg className="w-8 h-8 text-bloomberg-blue" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="3" width="7" height="7" />
                <rect x="14" y="3" width="7" height="7" />
                <path d="M10 17h4M12 15v4" />
              </svg>
              <div>
                <div className="font-medium text-text-primary">Compare with another player</div>
                <div className="text-sm text-text-secondary">Side-by-side analysis</div>
              </div>
            </div>
          </Link>
        </div>
      </div>
    </div>
  );
}

function StatRow({ 
  label, 
  value, 
  highlight = false, 
  highlightColor = 'orange' 
}: { 
  label: string; 
  value: string; 
  highlight?: boolean;
  highlightColor?: 'orange' | 'red' | 'green';
}) {
  const colorClass = {
    orange: 'text-bloomberg-orange',
    red: 'text-bloomberg-red',
    green: 'text-bloomberg-green',
  }[highlightColor];
  
  return (
    <div className="flex items-center justify-between py-2 border-b border-terminal-border/30 last:border-0">
      <span className="text-sm text-text-secondary">{label}</span>
      <span className={cn('font-mono text-sm', highlight ? colorClass : 'text-text-primary')}>
        {value}
      </span>
    </div>
  );
}
