import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'TransferLens - The Bloomberg Terminal for Football Transfers',
  description: 'Real-time transfer intelligence. Track probabilities, signals, and market movements.',
  keywords: ['football', 'transfers', 'soccer', 'predictions', 'market', 'analytics'],
  openGraph: {
    title: 'TransferLens',
    description: 'The Bloomberg Terminal for Football Transfers',
    type: 'website',
    siteName: 'TransferLens',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'TransferLens',
    description: 'Real-time transfer intelligence',
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link rel="icon" href="/favicon.ico" />
      </head>
      <body className="min-h-screen">
        <div className="flex flex-col min-h-screen">
          {/* Header */}
          <header className="sticky top-0 z-50 bg-terminal-bg/95 backdrop-blur border-b border-terminal-border">
            <nav className="max-w-7xl mx-auto px-4 h-14 flex items-center justify-between">
              <a href="/" className="flex items-center gap-2 hover:opacity-80 transition-opacity">
                <span className="text-bloomberg-orange font-bold text-xl tracking-tight">
                  TRANSFER<span className="text-white">LENS</span>
                </span>
                <span className="text-2xs text-text-muted border border-terminal-border px-1.5 py-0.5 rounded">
                  BETA
                </span>
              </a>
              
              <div className="flex items-center gap-6">
                <a href="/market" className="text-sm text-text-secondary hover:text-text-primary transition-colors">
                  Market
                </a>
                <a href="/compare" className="text-sm text-text-secondary hover:text-text-primary transition-colors">
                  Compare
                </a>
                <a href="/watchlist" className="text-sm text-text-secondary hover:text-text-primary transition-colors">
                  Watchlist
                </a>
              </div>
            </nav>
          </header>

          {/* Main content */}
          <main className="flex-1">
            {children}
          </main>

          {/* Footer */}
          <footer className="border-t border-terminal-border py-6 mt-auto">
            <div className="max-w-7xl mx-auto px-4">
              <div className="flex items-center justify-between text-xs text-text-muted">
                <span>© 2025 TransferLens. All rights reserved.</span>
                <div className="flex items-center gap-4">
                  <span className="flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-bloomberg-green animate-pulse" />
                    Live
                  </span>
                  <span>Data refreshed every 60s</span>
                </div>
              </div>
            </div>
          </footer>
        </div>
      </body>
    </html>
  );
}
