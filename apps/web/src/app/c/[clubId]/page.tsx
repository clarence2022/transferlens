import { notFound } from 'next/navigation';
import type { Metadata } from 'next';
import Link from 'next/link';
import { Building2, Users, ArrowUpRight, ArrowDownLeft, MapPin, Calendar } from 'lucide-react';

import { getClub } from '@/lib/api';
import { ProbabilityTable } from '@/components/ProbabilityTable';
import { ClubPageTracker } from './tracker';
import { cn, formatCurrency, formatDate, getPositionColor, truncate } from '@/lib/utils';

export const revalidate = 60;

interface Props {
  params: { clubId: string };
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  try {
    const club = await getClub(params.clubId);
    return {
      title: `${club.name} - TransferLens`,
      description: `${club.name} transfer activity, incoming and outgoing probabilities`,
      openGraph: {
        title: `${club.name} | TransferLens`,
        description: `Transfer intelligence for ${club.name}`,
      },
    };
  } catch {
    return { title: 'Club Not Found - TransferLens' };
  }
}

export default async function ClubPage({ params }: Props) {
  let club;
  try {
    club = await getClub(params.clubId);
  } catch {
    notFound();
  }
  
  return (
    <div className="max-w-6xl mx-auto px-4 py-6">
      <ClubPageTracker clubId={params.clubId} />
      
      {/* Header */}
      <header className="mb-8">
        <div className="text-sm text-text-muted mb-4">
          <Link href="/" className="hover:text-text-secondary">Home</Link>
          <span className="mx-2">/</span>
          <span>Club</span>
        </div>
        
        <div className="flex flex-col md:flex-row md:items-start gap-6">
          {/* Club logo */}
          <div className="flex-shrink-0">
            <div className="w-24 h-24 md:w-32 md:h-32 rounded-xl bg-terminal-panel border border-terminal-border flex items-center justify-center">
              {club.logo_url ? (
                <img src={club.logo_url} alt={club.name} className="w-full h-full object-contain p-2" />
              ) : (
                <Building2 className="w-12 h-12 text-text-muted" />
              )}
            </div>
          </div>
          
          {/* Club info */}
          <div className="flex-1">
            <h1 className="text-2xl md:text-3xl font-bold text-text-primary mb-2">
              {club.name}
            </h1>
            
            {club.competition && (
              <div className="flex items-center gap-2 text-text-secondary mb-4">
                <span>{club.competition.name}</span>
                <span className="text-text-muted">•</span>
                <span>{club.country}</span>
              </div>
            )}
            
            <div className="flex flex-wrap gap-4 text-sm">
              {club.city && (
                <div className="flex items-center gap-1.5 text-text-secondary">
                  <MapPin className="w-4 h-4 text-text-muted" />
                  <span>{club.city}</span>
                </div>
              )}
              {club.stadium && (
                <div className="flex items-center gap-1.5 text-text-secondary">
                  <Building2 className="w-4 h-4 text-text-muted" />
                  <span>{club.stadium}</span>
                </div>
              )}
              <div className="flex items-center gap-1.5 text-text-secondary">
                <Users className="w-4 h-4 text-text-muted" />
                <span>{club.squad_count} players</span>
              </div>
            </div>
          </div>
        </div>
      </header>
      
      {/* Main content */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Outgoing */}
        <section className="panel">
          <div className="panel-header">
            <h2 className="panel-title flex items-center gap-2">
              <ArrowUpRight className="w-4 h-4 text-bloomberg-red" />
              Likely Departures
            </h2>
          </div>
          <div className="p-4">
            {club.outgoing_probabilities.length > 0 ? (
              <ProbabilityTable 
                predictions={club.outgoing_probabilities} 
                showPlayer 
                showFromClub={false}
                showToClub 
                compact 
              />
            ) : (
              <div className="text-center py-8 text-text-secondary">
                No outgoing predictions
              </div>
            )}
          </div>
        </section>
        
        {/* Incoming */}
        <section className="panel">
          <div className="panel-header">
            <h2 className="panel-title flex items-center gap-2">
              <ArrowDownLeft className="w-4 h-4 text-bloomberg-green" />
              Potential Targets
            </h2>
          </div>
          <div className="p-4">
            {club.incoming_probabilities.length > 0 ? (
              <ProbabilityTable 
                predictions={club.incoming_probabilities} 
                showPlayer 
                showFromClub 
                showToClub={false}
                compact 
              />
            ) : (
              <div className="text-center py-8 text-text-secondary">
                No incoming predictions
              </div>
            )}
          </div>
        </section>
      </div>
      
      {/* Squad */}
      <section className="panel mt-6">
        <div className="panel-header">
          <h2 className="panel-title flex items-center gap-2">
            <Users className="w-4 h-4 text-bloomberg-orange" />
            Current Squad
          </h2>
          <span className="text-xs text-text-muted">{club.squad_count} players</span>
        </div>
        <div className="p-4">
          {club.squad.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {club.squad.map((player) => (
                <Link
                  key={player.id}
                  href={`/p/${player.id}`}
                  className="flex items-center gap-3 p-3 rounded bg-terminal-border/30 hover:bg-terminal-border/50 transition-colors"
                >
                  <div className="w-10 h-10 rounded-full bg-terminal-border flex items-center justify-center text-xs font-medium">
                    {player.name.split(' ').map(n => n[0]).join('').slice(0, 2)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-medium truncate">{player.name}</div>
                    <div className={cn('text-xs', getPositionColor(player.position))}>
                      {player.position || 'N/A'}
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-text-secondary">
              No squad data available
            </div>
          )}
        </div>
      </section>
      
      {/* Recent Transfers */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
        {/* Transfers In */}
        <section className="panel">
          <div className="panel-header">
            <h2 className="panel-title">Recent Arrivals</h2>
          </div>
          <div className="p-4">
            {club.recent_transfers_in.length > 0 ? (
              <div className="space-y-3">
                {club.recent_transfers_in.slice(0, 5).map((transfer) => (
                  <Link
                    key={transfer.id}
                    href={`/p/${transfer.player_id}`}
                    className="flex items-center gap-3 p-2 rounded hover:bg-terminal-border/30 transition-colors"
                  >
                    <ArrowDownLeft className="w-4 h-4 text-bloomberg-green" />
                    <div className="flex-1 min-w-0">
                      <div className="font-medium truncate">{transfer.player_name}</div>
                      <div className="text-xs text-text-muted">
                        from {transfer.from_club_name || 'Unknown'}
                      </div>
                    </div>
                    <div className="text-right">
                      {transfer.fee_amount_eur && (
                        <div className="font-mono text-sm text-bloomberg-green">
                          {formatCurrency(transfer.fee_amount_eur)}
                        </div>
                      )}
                      <div className="text-xs text-text-muted">
                        {formatDate(transfer.transfer_date)}
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            ) : (
              <div className="text-center py-6 text-text-secondary text-sm">
                No recent arrivals
              </div>
            )}
          </div>
        </section>
        
        {/* Transfers Out */}
        <section className="panel">
          <div className="panel-header">
            <h2 className="panel-title">Recent Departures</h2>
          </div>
          <div className="p-4">
            {club.recent_transfers_out.length > 0 ? (
              <div className="space-y-3">
                {club.recent_transfers_out.slice(0, 5).map((transfer) => (
                  <Link
                    key={transfer.id}
                    href={`/p/${transfer.player_id}`}
                    className="flex items-center gap-3 p-2 rounded hover:bg-terminal-border/30 transition-colors"
                  >
                    <ArrowUpRight className="w-4 h-4 text-bloomberg-red" />
                    <div className="flex-1 min-w-0">
                      <div className="font-medium truncate">{transfer.player_name}</div>
                      <div className="text-xs text-text-muted">
                        to {transfer.to_club_name || 'Unknown'}
                      </div>
                    </div>
                    <div className="text-right">
                      {transfer.fee_amount_eur && (
                        <div className="font-mono text-sm text-bloomberg-green">
                          {formatCurrency(transfer.fee_amount_eur)}
                        </div>
                      )}
                      <div className="text-xs text-text-muted">
                        {formatDate(transfer.transfer_date)}
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            ) : (
              <div className="text-center py-6 text-text-secondary text-sm">
                No recent departures
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
