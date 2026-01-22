'use client';

import { useMemo } from 'react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Area, AreaChart } from 'recharts';
import { PredictionBrief } from '@/lib/api';
import { cn, formatProbability } from '@/lib/utils';

interface ProbabilityChartProps {
  predictions: PredictionBrief[];
  clubName?: string;
  className?: string;
}

export function ProbabilityChart({ predictions, clubName, className }: ProbabilityChartProps) {
  const chartData = useMemo(() => {
    // Group by date and get latest per day
    const byDate = new Map<string, number>();
    
    predictions
      .sort((a, b) => new Date(a.as_of).getTime() - new Date(b.as_of).getTime())
      .forEach(p => {
        const date = new Date(p.as_of).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        byDate.set(date, p.probability * 100);
      });
    
    return Array.from(byDate.entries()).map(([date, probability]) => ({
      date,
      probability: Math.round(probability * 10) / 10,
    }));
  }, [predictions]);
  
  if (chartData.length < 2) {
    return (
      <div className={cn('h-[200px] flex items-center justify-center text-text-secondary text-sm', className)}>
        Not enough data for chart
      </div>
    );
  }
  
  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-terminal-panel border border-terminal-border rounded px-3 py-2 shadow-lg">
          <p className="text-xs text-text-secondary">{label}</p>
          <p className="text-sm font-mono font-semibold text-bloomberg-orange">
            {payload[0].value}%
          </p>
        </div>
      );
    }
    return null;
  };
  
  return (
    <div className={cn('h-[200px]', className)}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
          <defs>
            <linearGradient id="probGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#ff6b00" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#ff6b00" stopOpacity={0} />
            </linearGradient>
          </defs>
          <XAxis 
            dataKey="date" 
            tick={{ fontSize: 10, fill: '#555555' }}
            axisLine={{ stroke: '#2a2a2a' }}
            tickLine={false}
          />
          <YAxis 
            tick={{ fontSize: 10, fill: '#555555' }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(value) => `${value}%`}
            domain={[0, 'auto']}
          />
          <Tooltip content={<CustomTooltip />} />
          <Area
            type="monotone"
            dataKey="probability"
            stroke="#ff6b00"
            strokeWidth={2}
            fill="url(#probGradient)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

// Mini sparkline version
export function ProbabilitySparkline({ predictions, className }: { predictions: PredictionBrief[]; className?: string }) {
  const chartData = useMemo(() => {
    return predictions
      .sort((a, b) => new Date(a.as_of).getTime() - new Date(b.as_of).getTime())
      .slice(-10)
      .map(p => ({ value: p.probability * 100 }));
  }, [predictions]);
  
  if (chartData.length < 2) return null;
  
  return (
    <div className={cn('h-8 w-24', className)}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData}>
          <Line
            type="monotone"
            dataKey="value"
            stroke="#ff6b00"
            strokeWidth={1.5}
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
