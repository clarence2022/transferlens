'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { Search, X, User, Building2 } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { search, SearchResult } from '@/lib/api';
import { track } from '@/lib/tracking';
import { cn, truncate } from '@/lib/utils';

interface SearchBarProps {
  className?: string;
  autoFocus?: boolean;
  placeholder?: string;
}

export function SearchBar({ className, autoFocus = false, placeholder = 'Search players, clubs...' }: SearchBarProps) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const router = useRouter();
  
  // Debounced search
  useEffect(() => {
    if (query.length < 2) {
      setResults([]);
      setIsOpen(false);
      return;
    }
    
    const timer = setTimeout(async () => {
      setIsLoading(true);
      try {
        const res = await search(query, 8);
        setResults(res.results);
        setIsOpen(true);
        track.search(query, res.results.length);
      } catch (err) {
        console.error('Search failed:', err);
      } finally {
        setIsLoading(false);
      }
    }, 200);
    
    return () => clearTimeout(timer);
  }, [query]);
  
  // Close on click outside
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);
  
  const handleSelect = useCallback((result: SearchResult) => {
    setIsOpen(false);
    setQuery('');
    
    if (result.type === 'player') {
      router.push(`/p/${result.id}`);
    } else {
      router.push(`/c/${result.id}`);
    }
  }, [router]);
  
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!isOpen) return;
    
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setSelectedIndex(i => Math.min(i + 1, results.length - 1));
        break;
      case 'ArrowUp':
        e.preventDefault();
        setSelectedIndex(i => Math.max(i - 1, -1));
        break;
      case 'Enter':
        e.preventDefault();
        if (selectedIndex >= 0 && results[selectedIndex]) {
          handleSelect(results[selectedIndex]);
        }
        break;
      case 'Escape':
        setIsOpen(false);
        break;
    }
  };
  
  return (
    <div ref={containerRef} className={cn('relative', className)}>
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => query.length >= 2 && setIsOpen(true)}
          placeholder={placeholder}
          autoFocus={autoFocus}
          className="w-full pl-10 pr-10 py-3 bg-terminal-panel border border-terminal-border rounded-lg
                     text-text-primary placeholder-text-muted
                     focus:outline-none focus:border-bloomberg-orange focus:ring-1 focus:ring-bloomberg-orange/30
                     transition-all"
        />
        {query && (
          <button
            onClick={() => { setQuery(''); setResults([]); }}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-primary"
          >
            <X className="w-4 h-4" />
          </button>
        )}
        {isLoading && (
          <div className="absolute right-3 top-1/2 -translate-y-1/2">
            <div className="w-4 h-4 border-2 border-bloomberg-orange/30 border-t-bloomberg-orange rounded-full animate-spin" />
          </div>
        )}
      </div>
      
      {/* Results dropdown */}
      {isOpen && results.length > 0 && (
        <div className="absolute top-full left-0 right-0 mt-2 bg-terminal-panel border border-terminal-border rounded-lg shadow-xl overflow-hidden z-50 animate-fade-in">
          {results.map((result, index) => (
            <button
              key={result.id}
              onClick={() => handleSelect(result)}
              onMouseEnter={() => setSelectedIndex(index)}
              className={cn(
                'w-full px-4 py-3 flex items-center gap-3 text-left transition-colors',
                index === selectedIndex ? 'bg-terminal-border' : 'hover:bg-terminal-border/50'
              )}
            >
              <div className={cn(
                'w-8 h-8 rounded-full flex items-center justify-center',
                result.type === 'player' ? 'bg-bloomberg-blue/20' : 'bg-bloomberg-green/20'
              )}>
                {result.type === 'player' 
                  ? <User className="w-4 h-4 text-bloomberg-blue" />
                  : <Building2 className="w-4 h-4 text-bloomberg-green" />
                }
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-text-primary">
                  {truncate(result.name, 30)}
                </div>
                {result.subtitle && (
                  <div className="text-xs text-text-secondary">
                    {result.subtitle}
                  </div>
                )}
              </div>
              <span className={cn(
                'text-2xs px-1.5 py-0.5 rounded uppercase',
                result.type === 'player' ? 'bg-bloomberg-blue/10 text-bloomberg-blue' : 'bg-bloomberg-green/10 text-bloomberg-green'
              )}>
                {result.type}
              </span>
            </button>
          ))}
        </div>
      )}
      
      {/* No results */}
      {isOpen && query.length >= 2 && results.length === 0 && !isLoading && (
        <div className="absolute top-full left-0 right-0 mt-2 bg-terminal-panel border border-terminal-border rounded-lg p-4 text-center text-text-secondary text-sm">
          No results found for "{query}"
        </div>
      )}
    </div>
  );
}
