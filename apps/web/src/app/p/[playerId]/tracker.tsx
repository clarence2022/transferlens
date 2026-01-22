'use client';

import { useEffect } from 'react';
import { track } from '@/lib/tracking';

export function PlayerPageTracker({ playerId }: { playerId: string }) {
  useEffect(() => {
    track.playerView(playerId);
  }, [playerId]);
  
  return null;
}
