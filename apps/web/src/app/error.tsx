'use client';

import { useEffect } from 'react';
import { AlertCircle, RefreshCw, Home } from 'lucide-react';
import Link from 'next/link';

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error('Page error:', error);
  }, [error]);

  return (
    <div className="min-h-[60vh] flex items-center justify-center px-4">
      <div className="text-center">
        <AlertCircle className="w-16 h-16 text-bloomberg-red mx-auto mb-6" />
        <h1 className="text-2xl font-bold text-text-primary mb-2">Something went wrong</h1>
        <p className="text-text-secondary mb-8 max-w-md mx-auto">
          We encountered an error loading this page. Please try again.
        </p>
        <div className="flex items-center justify-center gap-4">
          <button
            onClick={reset}
            className="btn btn-primary flex items-center gap-2"
          >
            <RefreshCw className="w-4 h-4" />
            Try Again
          </button>
          <Link
            href="/"
            className="btn btn-secondary flex items-center gap-2"
          >
            <Home className="w-4 h-4" />
            Go Home
          </Link>
        </div>
      </div>
    </div>
  );
}
