import Link from 'next/link';
import { AlertCircle, Home, ArrowLeft } from 'lucide-react';

export default function NotFound() {
  return (
    <div className="min-h-[60vh] flex items-center justify-center px-4">
      <div className="text-center">
        <AlertCircle className="w-16 h-16 text-bloomberg-orange mx-auto mb-6" />
        <h1 className="text-4xl font-bold text-text-primary mb-2">404</h1>
        <h2 className="text-xl text-text-secondary mb-6">Page not found</h2>
        <p className="text-text-muted mb-8 max-w-md mx-auto">
          The page you're looking for doesn't exist or has been moved.
        </p>
        <div className="flex items-center justify-center gap-4">
          <Link
            href="/"
            className="btn btn-primary flex items-center gap-2"
          >
            <Home className="w-4 h-4" />
            Go Home
          </Link>
          <button
            onClick={() => window.history.back()}
            className="btn btn-secondary flex items-center gap-2"
          >
            <ArrowLeft className="w-4 h-4" />
            Go Back
          </button>
        </div>
      </div>
    </div>
  );
}
