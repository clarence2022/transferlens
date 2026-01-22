'use client';

import { useState } from 'react';
import { Share2, Twitter, Link2, Check, Download } from 'lucide-react';
import { track } from '@/lib/tracking';
import { cn, formatProbability } from '@/lib/utils';

interface ShareCardProps {
  playerId: string;
  playerName: string;
  clubName: string | null;
  destinationClub: string | null;
  probability: number | null;
  className?: string;
}

export function ShareCard({ playerId, playerName, clubName, destinationClub, probability, className }: ShareCardProps) {
  const [showMenu, setShowMenu] = useState(false);
  const [copied, setCopied] = useState(false);
  
  const shareUrl = typeof window !== 'undefined' 
    ? `${window.location.origin}/p/${playerId}` 
    : '';
  
  const shareText = probability && destinationClub
    ? `${playerName} → ${destinationClub}: ${formatProbability(probability)} transfer probability on TransferLens`
    : `Check out ${playerName}'s transfer probabilities on TransferLens`;
  
  const handleShare = async (platform: string) => {
    track.shareClick(playerId, platform);
    
    switch (platform) {
      case 'twitter':
        window.open(
          `https://twitter.com/intent/tweet?text=${encodeURIComponent(shareText)}&url=${encodeURIComponent(shareUrl)}`,
          '_blank'
        );
        break;
      case 'copy':
        await navigator.clipboard.writeText(shareUrl);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
        break;
      case 'native':
        if (navigator.share) {
          await navigator.share({ title: playerName, text: shareText, url: shareUrl });
        }
        break;
    }
    
    setShowMenu(false);
  };
  
  return (
    <div className={cn('relative', className)}>
      <button
        onClick={() => setShowMenu(!showMenu)}
        className="flex items-center gap-2 px-3 py-2 rounded bg-terminal-border text-text-secondary 
                   hover:text-text-primary hover:bg-terminal-border-bright transition-colors"
      >
        <Share2 className="w-4 h-4" />
        <span className="text-sm font-medium">Share</span>
      </button>
      
      {showMenu && (
        <>
          {/* Backdrop */}
          <div 
            className="fixed inset-0 z-40" 
            onClick={() => setShowMenu(false)} 
          />
          
          {/* Menu */}
          <div className="absolute right-0 top-full mt-2 bg-terminal-panel border border-terminal-border rounded-lg shadow-xl z-50 overflow-hidden animate-fade-in min-w-[180px]">
            <button
              onClick={() => handleShare('twitter')}
              className="w-full px-4 py-3 flex items-center gap-3 text-sm text-text-secondary hover:text-text-primary hover:bg-terminal-border/50 transition-colors"
            >
              <Twitter className="w-4 h-4" />
              Share on X
            </button>
            
            <button
              onClick={() => handleShare('copy')}
              className="w-full px-4 py-3 flex items-center gap-3 text-sm text-text-secondary hover:text-text-primary hover:bg-terminal-border/50 transition-colors"
            >
              {copied ? <Check className="w-4 h-4 text-bloomberg-green" /> : <Link2 className="w-4 h-4" />}
              {copied ? 'Copied!' : 'Copy link'}
            </button>
            
            {typeof navigator !== 'undefined' && navigator.share && (
              <button
                onClick={() => handleShare('native')}
                className="w-full px-4 py-3 flex items-center gap-3 text-sm text-text-secondary hover:text-text-primary hover:bg-terminal-border/50 transition-colors"
              >
                <Share2 className="w-4 h-4" />
                More options
              </button>
            )}
          </div>
        </>
      )}
    </div>
  );
}

// Visual share card preview (for OG image generation)
export function ShareCardPreview({ 
  playerName, 
  clubName, 
  destinationClub, 
  probability 
}: { 
  playerName: string; 
  clubName: string | null;
  destinationClub: string | null; 
  probability: number | null;
}) {
  return (
    <div className="w-[600px] h-[315px] bg-terminal-bg p-8 flex flex-col justify-between border border-terminal-border">
      {/* Header */}
      <div className="flex items-center justify-between">
        <span className="text-bloomberg-orange font-bold text-xl tracking-tight">
          TRANSFER<span className="text-white">LENS</span>
        </span>
        <span className="text-xs text-text-muted">transferlens.io</span>
      </div>
      
      {/* Content */}
      <div className="flex-1 flex flex-col justify-center">
        <h1 className="text-3xl font-bold text-white mb-2">{playerName}</h1>
        <p className="text-text-secondary mb-6">{clubName || 'Free Agent'}</p>
        
        {destinationClub && probability && (
          <div className="flex items-center gap-4">
            <div className="text-bloomberg-orange">→</div>
            <div>
              <p className="text-lg text-white">{destinationClub}</p>
              <p className="text-3xl font-mono font-bold text-bloomberg-orange">
                {formatProbability(probability)}
              </p>
            </div>
          </div>
        )}
      </div>
      
      {/* Footer */}
      <div className="text-xs text-text-muted">
        Real-time transfer intelligence
      </div>
    </div>
  );
}
