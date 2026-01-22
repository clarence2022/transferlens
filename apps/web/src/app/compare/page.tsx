'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { Search, X, ArrowRight, Plus } from 'lucide-react';
import { search, getPlayer, PlayerDetail, SearchResult } from '@/lib/api';
import { track } from '@/lib/tracking';
import { DestinationList } from '@/components/DestinationCard';
import { WhatChanged } from '@/components/WhatChanged';
import { cn, formatCurrency, formatProbability, getPositionColor, getProbabilityColor } from '@/lib/utils';

export default function ComparePage() {
  const [player1, setPlayer1] = useState<PlayerDetail | null>(null);
  const [player2, setPlayer2] = useState<PlayerDetail | null>(null);
  const [loading1, setLoading1] = useState(false);
  const [loading2, setLoading2] = useState(false);
  
  // Track comparison when both players selected
  useEffect(() => {
    if (player1 && player2) {
      track.compareUse(player1.id, player2.id);
    }
  }, [player1?.id, player2?.id]);
  
  const loadPlayer = async (id: string, slot: 1 | 2) => {
    const setLoading = slot === 1 ? setLoading1 : setLoading2;
    const setPlayer = slot === 1 ? setPlayer1 : setPlayer2;
    
    setLoading(true);
    try {
      const data = await getPlayer(id);
      setPlayer(data);
    } catch (err) {
      console.error('Failed to load player:', err);
    } finally {
      setLoading(false);
    }
  };
  
  return (
    <div className="max-w-7xl mx-auto px-4 py-6">
      {/* Header */}
      <header className="mb-8">
        <div className="text-sm text-text-muted mb-4">
          <Link href="/" className="hover:text-text-secondary">Home</Link>
          <span className="mx-2">/</span>
          <span>Compare</span>
        </div>
        
        <h1 className="text-2xl md:text-3xl font-bold text-text-primary">
          Compare Players
        </h1>
        <p className="text-text-secondary mt-1">
          Side-by-side transfer probability analysis
        </p>
      </header>
      
      {/* Comparison grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Player 1 */}
        <div className="space-y-4">
          {player1 ? (
            <PlayerCard 
              player={player1} 
              onRemove={() => setPlayer1(null)}
              loading={loading1}
            />
          ) : (
            <PlayerSelector 
              onSelect={(id) => loadPlayer(id, 1)} 
              loading={loading1}
              placeholder="Select first player"
            />
          )}
          
          {player1 && (
            <>
              <div className="panel">
                <div className="panel-header">
                  <h3 className="panel-title">Top Destinations</h3>
                </div>
                <div className="p-4">
                  <DestinationList predictions={player1.latest_predictions} />
                </div>
              </div>
              
              <div className="panel">
                <div className="panel-header">
                  <h3 className="panel-title">What Changed</h3>
                </div>
                <div className="p-4">
                  <WhatChanged changes={player1.what_changed} />
                </div>
              </div>
            </>
          )}
        </div>
        
        {/* Player 2 */}
        <div className="space-y-4">
          {player2 ? (
            <PlayerCard 
              player={player2} 
              onRemove={() => setPlayer2(null)}
              loading={loading2}
            />
          ) : (
            <PlayerSelector 
              onSelect={(id) => loadPlayer(id, 2)} 
              loading={loading2}
              placeholder="Select second player"
            />
          )}
          
          {player2 && (
            <>
              <div className="panel">
                <div className="panel-header">
                  <h3 className="panel-title">Top Destinations</h3>
                </div>
                <div className="p-4">
                  <DestinationList predictions={player2.latest_predictions} />
                </div>
              </div>
              
              <div className="panel">
                <div className="panel-header">
                  <h3 className="panel-title">What Changed</h3>
                </div>
                <div className="p-4">
                  <WhatChanged changes={player2.what_changed} />
                </div>
              </div>
            </>
          )}
        </div>
      </div>
      
      {/* Stats comparison */}
      {player1 && player2 && (
        <div className="panel mt-6">
          <div className="panel-header">
            <h3 className="panel-title">Quick Comparison</h3>
          </div>
          <div className="p-4">
            <div className="grid grid-cols-3 gap-4 text-center">
              <div className="text-right">
                <div className="font-mono text-lg">{formatCurrency(player1.market_value)}</div>
              </div>
              <div className="text-text-muted text-sm">Market Value</div>
              <div className="text-left">
                <div className="font-mono text-lg">{formatCurrency(player2.market_value)}</div>
              </div>
              
              <div className="text-right">
                <div className={cn(
                  'font-mono text-lg',
                  (player1.contract_months_remaining ?? 0) <= 12 ? 'text-bloomberg-red' : ''
                )}>
                  {player1.contract_months_remaining ?? '-'}mo
                </div>
              </div>
              <div className="text-text-muted text-sm">Contract</div>
              <div className="text-left">
                <div className={cn(
                  'font-mono text-lg',
                  (player2.contract_months_remaining ?? 0) <= 12 ? 'text-bloomberg-red' : ''
                )}>
                  {player2.contract_months_remaining ?? '-'}mo
                </div>
              </div>
              
              <div className="text-right">
                <div className="font-mono text-lg">{player1.age ?? '-'}</div>
              </div>
              <div className="text-text-muted text-sm">Age</div>
              <div className="text-left">
                <div className="font-mono text-lg">{player2.age ?? '-'}</div>
              </div>
              
              <div className="text-right">
                <div className={cn(
                  'font-mono text-lg',
                  getProbabilityColor(player1.latest_predictions[0]?.probability ?? 0)
                )}>
                  {formatProbability(player1.latest_predictions[0]?.probability)}
                </div>
              </div>
              <div className="text-text-muted text-sm">Top Probability</div>
              <div className="text-left">
                <div className={cn(
                  'font-mono text-lg',
                  getProbabilityColor(player2.latest_predictions[0]?.probability ?? 0)
                )}>
                  {formatProbability(player2.latest_predictions[0]?.probability)}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function PlayerCard({ 
  player, 
  onRemove, 
  loading 
}: { 
  player: PlayerDetail; 
  onRemove: () => void; 
  loading: boolean;
}) {
  return (
    <div className="panel">
      <div className="p-4 flex items-center gap-4">
        <div className="w-16 h-16 rounded-lg bg-terminal-border flex items-center justify-center text-xl font-bold">
          {player.name.split(' ').map(n => n[0]).join('').slice(0, 2)}
        </div>
        <div className="flex-1 min-w-0">
          <Link 
            href={`/p/${player.id}`}
            className="font-semibold text-lg hover:text-bloomberg-orange transition-colors"
          >
            {player.name}
          </Link>
          <div className="flex items-center gap-2 text-sm text-text-secondary">
            <span className={getPositionColor(player.position)}>{player.position}</span>
            <span>•</span>
            <span>{player.current_club?.name || 'Free Agent'}</span>
          </div>
        </div>
        <button 
          onClick={onRemove}
          className="p-2 text-text-muted hover:text-text-primary hover:bg-terminal-border rounded transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}

function PlayerSelector({ 
  onSelect, 
  loading, 
  placeholder 
}: { 
  onSelect: (id: string) => void; 
  loading: boolean; 
  placeholder: string;
}) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [searching, setSearching] = useState(false);
  
  useEffect(() => {
    if (query.length < 2) {
      setResults([]);
      return;
    }
    
    const timer = setTimeout(async () => {
      setSearching(true);
      try {
        const res = await search(query, 10);
        setResults(res.results.filter(r => r.type === 'player'));
        setIsOpen(true);
      } catch (err) {
        console.error('Search failed:', err);
      } finally {
        setSearching(false);
      }
    }, 200);
    
    return () => clearTimeout(timer);
  }, [query]);
  
  const handleSelect = (result: SearchResult) => {
    setQuery('');
    setResults([]);
    setIsOpen(false);
    onSelect(result.id);
  };
  
  if (loading) {
    return (
      <div className="panel h-[140px] flex items-center justify-center">
        <div className="w-6 h-6 border-2 border-bloomberg-orange/30 border-t-bloomberg-orange rounded-full animate-spin" />
      </div>
    );
  }
  
  return (
    <div className="panel relative">
      <div className="p-4">
        <div className="flex items-center gap-4">
          <div className="w-16 h-16 rounded-lg bg-terminal-border flex items-center justify-center">
            <Plus className="w-6 h-6 text-text-muted" />
          </div>
          <div className="flex-1">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onFocus={() => query.length >= 2 && setIsOpen(true)}
                placeholder={placeholder}
                className="w-full pl-10 pr-4 py-2 bg-terminal-bg border border-terminal-border rounded
                           text-text-primary placeholder-text-muted
                           focus:outline-none focus:border-bloomberg-orange"
              />
            </div>
          </div>
        </div>
      </div>
      
      {/* Results dropdown */}
      {isOpen && results.length > 0 && (
        <div className="absolute left-0 right-0 top-full mt-1 bg-terminal-panel border border-terminal-border rounded-lg shadow-xl z-50 max-h-60 overflow-auto">
          {results.map((result) => (
            <button
              key={result.id}
              onClick={() => handleSelect(result)}
              className="w-full px-4 py-3 flex items-center gap-3 text-left hover:bg-terminal-border/50 transition-colors"
            >
              <div className="w-8 h-8 rounded-full bg-terminal-border flex items-center justify-center text-xs">
                {result.name.split(' ').map(n => n[0]).join('').slice(0, 2)}
              </div>
              <div>
                <div className="font-medium">{result.name}</div>
                {result.subtitle && (
                  <div className="text-xs text-text-secondary">{result.subtitle}</div>
                )}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
