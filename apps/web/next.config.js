/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  reactStrictMode: true,
  
  // Image domains for player/club photos
  images: {
    domains: ['localhost', 'transferlens.io'],
    unoptimized: process.env.NODE_ENV === 'development',
  },
  
  // API proxy rewrites (exclude our own /api routes)
  async rewrites() {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    return [
      {
        source: '/api/v1/:path*',
        destination: `${apiUrl}/api/v1/:path*`,
      },
    ];
  },
  
  // Headers for caching
  async headers() {
    return [
      {
        source: '/api/og/:path*',
        headers: [
          {
            key: 'Cache-Control',
            value: 'public, max-age=3600, stale-while-revalidate=86400',
          },
        ],
      },
    ];
  },
};

module.exports = nextConfig;
