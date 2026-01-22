import { Suspense } from 'react';
import type { Metadata } from 'next';
import Link from 'next/link';
import { Activity, Filter } from 'lucide-react';

import { getMarketLatest } from '@/lib/api';
import { ProbabilityTable } from '@/components/ProbabilityTable';
import { MarketFilters } from './filters';

export const metadata: Metadata = {
  title: 'Transfer Market - TransferLens',
  description: 'Live transfer probability table with real-time market intelligence',
};

export const revalidate = 30;

interface Props {
  searchParams: {
    horizon?: string;
    min_prob?: string;
    club?: string;
  };
}

async function MarketTable({ searchParams }: Props) {
  const horizonDays = searchParams.horizon ? parseInt(searchParams.horizon) : 90;
  const minProbability = searchParams.min_prob ? parseFloat(searchParams.min_prob) : 0.1;
  
  try {
    const data = await getMarketLatest({
      horizon_days: horizonDays,
      min_probability: minProbability,
      club_id: searchParams.club,
      limit: 50,
    });
    
    return (
      <>
        <div className="flex items-center justify-between mb-4 text-sm text-text-muted">
          <span>Showing {data.predictions.length} of {data.total} predictions</span>
          <span>Updated {new Date(data.as_of).toLocaleTimeString()}</span>
        </div>
        <ProbabilityTable predictions={data.predictions} />
      </>
    );
  } catch (error) {
    return (
      <div className="text-center py-12 text-text-secondary">
        Failed to load market data. Please try again.
      </div>
    );
  }
}

export default function MarketPage({ searchParams }: Props) {
  return (
    <div className="max-w-7xl mx-auto px-4 py-6">
      {/* Header */}
      <header className="mb-6">
        <div className="text-sm text-text-muted mb-4">
          <Link href="/" className="hover:text-text-secondary">Home</Link>
          <span className="mx-2">/</span>
          <span>Market</span>
        </div>
        
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl md:text-3xl font-bold text-text-primary flex items-center gap-3">
              <Activity className="w-8 h-8 text-bloomberg-orange" />
              Transfer Market
            </h1>
            <p className="text-text-secondary mt-1">
              Live probability table • Updated every minute
            </p>
          </div>
        </div>
      </header>
      
      {/* Filters */}
      <div className="panel mb-6">
        <div className="p-4">
          <MarketFilters searchParams={searchParams} />
        </div>
      </div>
      
      {/* Market Table */}
      <div className="panel">
        <div className="p-4">
          <Suspense fallback={<TableSkeleton />}>
            <MarketTable searchParams={searchParams} />
          </Suspense>
        </div>
      </div>
    </div>
  );
}

function TableSkeleton() {
  return (
    <div className="space-y-3">
      {[...Array(10)].map((_, i) => (
        <div key={i} className="flex items-center gap-4 p-3 border-b border-terminal-border/30">
          <div className="skeleton w-10 h-10 rounded-full" />
          <div className="flex-1 space-y-2">
            <div className="skeleton h-4 w-40" />
            <div className="skeleton h-3 w-28" />
          </div>
          <div className="skeleton h-4 w-20" />
          <div className="skeleton h-4 w-20" />
          <div className="skeleton h-6 w-16" />
        </div>
      ))}
    </div>
  );
}
