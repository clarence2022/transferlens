'use client';

import { useRouter, useSearchParams } from 'next/navigation';
import { Filter } from 'lucide-react';
import { cn } from '@/lib/utils';

interface MarketFiltersProps {
  searchParams: {
    horizon?: string;
    min_prob?: string;
    club?: string;
  };
}

export function MarketFilters({ searchParams }: MarketFiltersProps) {
  const router = useRouter();
  const currentParams = useSearchParams();
  
  const updateFilter = (key: string, value: string | null) => {
    const params = new URLSearchParams(currentParams.toString());
    if (value) {
      params.set(key, value);
    } else {
      params.delete(key);
    }
    router.push(`/market?${params.toString()}`);
  };
  
  const horizonOptions = [
    { value: '30', label: '30 days' },
    { value: '90', label: '90 days' },
    { value: '180', label: '180 days' },
  ];
  
  const probOptions = [
    { value: '0.1', label: '10%+' },
    { value: '0.2', label: '20%+' },
    { value: '0.3', label: '30%+' },
    { value: '0.5', label: '50%+' },
  ];
  
  const currentHorizon = searchParams.horizon || '90';
  const currentProb = searchParams.min_prob || '0.1';
  
  return (
    <div className="flex flex-wrap items-center gap-4">
      <div className="flex items-center gap-2 text-text-muted">
        <Filter className="w-4 h-4" />
        <span className="text-sm">Filters:</span>
      </div>
      
      {/* Horizon */}
      <div className="flex items-center gap-1">
        <span className="text-xs text-text-muted mr-2">Window:</span>
        {horizonOptions.map(opt => (
          <button
            key={opt.value}
            onClick={() => updateFilter('horizon', opt.value)}
            className={cn(
              'px-3 py-1.5 text-sm rounded transition-colors',
              currentHorizon === opt.value 
                ? 'bg-bloomberg-orange text-white' 
                : 'bg-terminal-border text-text-secondary hover:text-text-primary'
            )}
          >
            {opt.label}
          </button>
        ))}
      </div>
      
      {/* Min Probability */}
      <div className="flex items-center gap-1">
        <span className="text-xs text-text-muted mr-2">Min prob:</span>
        {probOptions.map(opt => (
          <button
            key={opt.value}
            onClick={() => updateFilter('min_prob', opt.value)}
            className={cn(
              'px-3 py-1.5 text-sm rounded transition-colors',
              currentProb === opt.value 
                ? 'bg-bloomberg-orange text-white' 
                : 'bg-terminal-border text-text-secondary hover:text-text-primary'
            )}
          >
            {opt.label}
          </button>
        ))}
      </div>
      
      {/* Clear filters */}
      {(currentHorizon !== '90' || currentProb !== '0.1') && (
        <button
          onClick={() => router.push('/market')}
          className="px-3 py-1.5 text-sm text-text-muted hover:text-text-primary transition-colors"
        >
          Clear all
        </button>
      )}
    </div>
  );
}
