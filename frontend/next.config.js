/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    const apiBase = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000/api/v1';
    return [{ source: '/api/v1/:path*', destination: `${apiBase}/:path*` }];
  },
};

module.exports = nextConfig;
