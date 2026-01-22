import { Suspense } from 'react';
import { SearchBar } from '@/components/SearchBar';
import { ProbabilityTable } from '@/components/ProbabilityTable';
import { TrendingPlayers } from '@/components/TrendingPlayers';
import { getMarketLatest } from '@/lib/api';
import { ArrowRight, TrendingUp, Zap, Activity } from 'lucide-react';
import Link from 'next/link';

export const revalidate = 30; // ISR: revalidate every 30 seconds

async function LatestMarket() {
  try {
    const data = await getMarketLatest({ limit: 10, horizon_days: 90 });
    return <ProbabilityTable predictions={data.predictions} compact />;
  } catch (error) {
    return (
      <div className="text-center py-8 text-text-secondary">
        Failed to load market data
      </div>
    );
  }
}

async function TrendingSection() {
  try {
    const data = await getMarketLatest({ 
      limit: 10, 
      horizon_days: 90,
      min_probability: 0.2,
    });
    const sorted = [...data.predictions].sort((a, b) => b.probability - a.probability);
    return <TrendingPlayers players={sorted} />;
  } catch (error) {
    return (
      <div className="text-center py-8 text-text-secondary">
        Failed to load trending players
      </div>
    );
  }
}

export default function HomePage() {
  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      {/* Hero Section */}
      <section className="text-center py-12 mb-12">
        <h1 className="text-4xl md:text-5xl font-bold mb-4">
          <span className="text-gradient-orange">Transfer Intelligence</span>
          <br />
          <span className="text-text-primary">in Real-Time</span>
        </h1>
        <p className="text-text-secondary text-lg mb-8 max-w-2xl mx-auto">
          Track transfer probabilities, market signals, and emerging moves 
          before they happen. The Bloomberg Terminal for football.
        </p>
        
        <div className="max-w-xl mx-auto mb-8">
          <SearchBar autoFocus placeholder="Search any player or club..." />
        </div>
        
        <div className="flex items-center justify-center gap-8 text-sm text-text-muted">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-bloomberg-green" />
            <span>Live predictions</span>
          </div>
          <div className="flex items-center gap-2">
            <Zap className="w-4 h-4 text-bloomberg-orange" />
            <span>Updated every minute</span>
          </div>
          <div className="flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-bloomberg-blue" />
            <span>1000+ players tracked</span>
          </div>
        </div>
      </section>
      
      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 panel">
          <div className="panel-header">
            <h2 className="panel-title flex items-center gap-2">
              <Activity className="w-4 h-4 text-bloomberg-orange" />
              Latest Market
            </h2>
            <Link 
              href="/market" 
              className="text-sm text-bloomberg-orange hover:text-bloomberg-orange-dim flex items-center gap-1"
            >
              View all <ArrowRight className="w-3 h-3" />
            </Link>
          </div>
          <div className="p-4">
            <Suspense fallback={<TableSkeleton />}>
              <LatestMarket />
            </Suspense>
          </div>
        </div>
        
        <div className="panel">
          <div className="panel-header">
            <h2 className="panel-title flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-bloomberg-orange" />
              Trending
            </h2>
          </div>
          <div className="p-4">
            <Suspense fallback={<TrendingSkeleton />}>
              <TrendingSection />
            </Suspense>
          </div>
        </div>
      </div>
      
      {/* Bottom CTAs */}
      <section className="mt-12 grid grid-cols-1 md:grid-cols-3 gap-4">
        <Link 
          href="/market"
          className="p-6 rounded-lg bg-terminal-panel border border-terminal-border hover:border-bloomberg-orange/50 transition-colors group"
        >
          <Activity className="w-8 h-8 text-bloomberg-orange mb-3" />
          <h3 className="font-semibold text-lg mb-1 group-hover:text-bloomberg-orange transition-colors">
            Full Market
          </h3>
          <p className="text-sm text-text-secondary">
            Browse all predictions with advanced filters
          </p>
        </Link>
        
        <Link 
          href="/compare"
          className="p-6 rounded-lg bg-terminal-panel border border-terminal-border hover:border-bloomberg-blue/50 transition-colors group"
        >
          <svg className="w-8 h-8 text-bloomberg-blue mb-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="3" y="3" width="7" height="7" />
            <rect x="14" y="3" width="7" height="7" />
            <path d="M10 17h4M12 15v4" />
          </svg>
          <h3 className="font-semibold text-lg mb-1 group-hover:text-bloomberg-blue transition-colors">
            Compare Players
          </h3>
          <p className="text-sm text-text-secondary">
            Side-by-side destination analysis
          </p>
        </Link>
        
        <Link 
          href="/watchlist"
          className="p-6 rounded-lg bg-terminal-panel border border-terminal-border hover:border-bloomberg-yellow/50 transition-colors group"
        >
          <svg className="w-8 h-8 text-bloomberg-yellow mb-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
          </svg>
          <h3 className="font-semibold text-lg mb-1 group-hover:text-bloomberg-yellow transition-colors">
            My Watchlist
          </h3>
          <p className="text-sm text-text-secondary">
            Track players and get alerts
          </p>
        </Link>
      </section>
    </div>
  );
}

function TableSkeleton() {
  return (
    <div className="space-y-3">
      {[...Array(5)].map((_, i) => (
        <div key={i} className="flex items-center gap-4 p-2">
          <div className="skeleton w-8 h-8 rounded-full" />
          <div className="flex-1 space-y-2">
            <div className="skeleton h-4 w-32" />
            <div className="skeleton h-3 w-24" />
          </div>
          <div className="skeleton h-6 w-16" />
        </div>
      ))}
    </div>
  );
}

function TrendingSkeleton() {
  return (
    <div className="space-y-3">
      {[...Array(5)].map((_, i) => (
        <div key={i} className="flex items-center gap-3 p-2">
          <div className="skeleton w-6 h-6 rounded" />
          <div className="flex-1 space-y-2">
            <div className="skeleton h-4 w-28" />
            <div className="skeleton h-3 w-20" />
          </div>
          <div className="skeleton h-5 w-12" />
        </div>
      ))}
    </div>
  );
}
