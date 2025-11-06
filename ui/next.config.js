/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,
  poweredByHeader: false,

  // API configuration
  async rewrites() {
    return [
      {
        source: '/api/sandbox/:path*',
        destination: 'http://localhost:4000/:path*',
      },
      {
        source: '/api/daemon/:path*',
        destination: 'http://localhost:8000/:path*',
      },
    ];
  },

  // Environment variables
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3000',
    NEXT_PUBLIC_SANDBOX_URL: process.env.NEXT_PUBLIC_SANDBOX_URL || 'http://localhost:4000',
    NEXT_PUBLIC_DAEMON_URL: process.env.NEXT_PUBLIC_DAEMON_URL || 'http://localhost:8000',
  },

  // Webpack configuration for syntax highlighting
  webpack: (config) => {
    config.resolve.fallback = {
      ...config.resolve.fallback,
      fs: false,
      path: false,
    };
    return config;
  },
};

module.exports = nextConfig;
