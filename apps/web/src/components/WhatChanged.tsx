'use client';

import { SignalDelta } from '@/lib/api';
import { cn, getSeverityColor, getSeverityIcon, formatRelativeTime } from '@/lib/utils';

interface WhatChangedProps {
  changes: SignalDelta[];
  className?: string;
}

export function WhatChanged({ changes, className }: WhatChangedProps) {
  if (changes.length === 0) {
    return (
      <div className={cn('text-center py-6 text-text-secondary text-sm', className)}>
        No significant changes this week
      </div>
    );
  }
  
  return (
    <div className={cn('space-y-3', className)}>
      {changes.map((change, index) => (
        <div 
          key={`${change.signal_type}-${index}`}
          className="flex items-start gap-3 p-3 rounded bg-terminal-border/30 hover:bg-terminal-border/50 transition-colors"
        >
          <span className="text-lg mt-0.5" role="img" aria-label={change.severity}>
            {getSeverityIcon(change.severity)}
          </span>
          <div className="flex-1 min-w-0">
            <p className={cn('text-sm font-medium', getSeverityColor(change.severity))}>
              {change.description}
            </p>
            <div className="flex items-center gap-2 mt-1 text-xs text-text-muted">
              <span>{formatRelativeTime(change.observed_at)}</span>
              {change.change_percent && (
                <>
                  <span>•</span>
                  <span className={change.change_percent > 0 ? 'text-bloomberg-green' : 'text-bloomberg-red'}>
                    {change.change_percent > 0 ? '+' : ''}{change.change_percent.toFixed(1)}%
                  </span>
                </>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

// Compact inline version
export function WhatChangedInline({ changes }: { changes: SignalDelta[] }) {
  const alertCount = changes.filter(c => c.severity === 'alert').length;
  const warningCount = changes.filter(c => c.severity === 'warning').length;
  
  if (changes.length === 0) return null;
  
  return (
    <div className="flex items-center gap-2 text-xs">
      {alertCount > 0 && (
        <span className="flex items-center gap-1 text-bloomberg-red">
          🔴 {alertCount}
        </span>
      )}
      {warningCount > 0 && (
        <span className="flex items-center gap-1 text-bloomberg-orange">
          🟠 {warningCount}
        </span>
      )}
    </div>
  );
}
