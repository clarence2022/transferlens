/**
 * Utility Functions
 */

import { clsx, type ClassValue } from 'clsx';

export function cn(...inputs: ClassValue[]): string {
  return clsx(inputs);
}

export function formatCurrency(value: number | null | undefined): string {
  if (value == null) return '-';
  
  if (value >= 1_000_000) {
    return `€${(value / 1_000_000).toFixed(1)}M`;
  }
  if (value >= 1_000) {
    return `€${(value / 1_000).toFixed(0)}K`;
  }
  return `€${value.toFixed(0)}`;
}

export function formatProbability(value: number | null | undefined): string {
  if (value == null) return '-';
  return `${(value * 100).toFixed(1)}%`;
}

export function formatProbabilityShort(value: number | null | undefined): string {
  if (value == null) return '-';
  const pct = value * 100;
  if (pct >= 10) return `${pct.toFixed(0)}%`;
  return `${pct.toFixed(1)}%`;
}

export function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '-';
  
  try {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-GB', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    });
  } catch {
    return dateStr;
  }
}

export function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);
  
  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  
  return formatDate(dateStr);
}

export function getPositionColor(position: string | null): string {
  if (!position) return 'text-text-secondary';
  
  const pos = position.toUpperCase();
  if (['ST', 'CF', 'LW', 'RW'].includes(pos)) return 'text-bloomberg-red';
  if (['CAM', 'CM', 'CDM', 'LM', 'RM'].includes(pos)) return 'text-bloomberg-green';
  if (['CB', 'LB', 'RB', 'LWB', 'RWB'].includes(pos)) return 'text-bloomberg-blue';
  if (pos === 'GK') return 'text-bloomberg-yellow';
  return 'text-text-secondary';
}

export function getProbabilityColor(probability: number): string {
  if (probability >= 0.7) return 'text-bloomberg-red';
  if (probability >= 0.4) return 'text-bloomberg-orange';
  if (probability >= 0.2) return 'text-bloomberg-yellow';
  return 'text-bloomberg-green';
}

export function getProbabilityBgColor(probability: number): string {
  if (probability >= 0.7) return 'bg-bloomberg-red/20';
  if (probability >= 0.4) return 'bg-bloomberg-orange/20';
  if (probability >= 0.2) return 'bg-bloomberg-yellow/20';
  return 'bg-bloomberg-green/20';
}

export function getSeverityColor(severity: string): string {
  switch (severity) {
    case 'alert': return 'text-bloomberg-red';
    case 'warning': return 'text-bloomberg-orange';
    default: return 'text-bloomberg-blue';
  }
}

export function getSeverityIcon(severity: string): string {
  switch (severity) {
    case 'alert': return '🔴';
    case 'warning': return '🟠';
    default: return '🔵';
  }
}

export function truncate(str: string, maxLength: number): string {
  if (str.length <= maxLength) return str;
  return str.slice(0, maxLength - 1) + '…';
}

export function getInitials(name: string): string {
  return name
    .split(' ')
    .map(n => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);
}

export function getCountryFlag(country: string): string {
  // Map common country names to flag emojis
  const flags: Record<string, string> = {
    'England': '🏴󠁧󠁢󠁥󠁮󠁧󠁿',
    'Spain': '🇪🇸',
    'Germany': '🇩🇪',
    'Italy': '🇮🇹',
    'France': '🇫🇷',
    'Brazil': '🇧🇷',
    'Argentina': '🇦🇷',
    'Portugal': '🇵🇹',
    'Netherlands': '🇳🇱',
    'Belgium': '🇧🇪',
    'Norway': '🇳🇴',
    'Poland': '🇵🇱',
    'Croatia': '🇭🇷',
    'Serbia': '🇷🇸',
    'Egypt': '🇪🇬',
  };
  
  return flags[country] || '🏳️';
}
