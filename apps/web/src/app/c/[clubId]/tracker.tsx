'use client';

import { useEffect } from 'react';
import { track } from '@/lib/tracking';

export function ClubPageTracker({ clubId }: { clubId: string }) {
  useEffect(() => {
    track.clubView(clubId);
  }, [clubId]);
  
  return null;
}
