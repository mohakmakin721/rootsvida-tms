/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    // Proxy API calls to the FastAPI domain service in local dev.
    const api = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";
    return [{ source: "/api/v1/:path*", destination: `${api}/:path*` }];
  },
};

export default nextConfig;
