/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Run middleware on the Node.js runtime (stable since Next 15.5) instead of the
  // Edge runtime. On Vercel the Edge runtime was crashing this middleware
  // (MIDDLEWARE_INVOCATION_FAILED); the same code runs fine on Node. This is the
  // opt-in flag; the middleware also sets `runtime: "nodejs"` in its config.
  experimental: {
    nodeMiddleware: true,
  },
  async rewrites() {
    // Proxy API calls to the FastAPI domain service in local dev.
    const api = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";
    return [{ source: "/api/v1/:path*", destination: `${api}/:path*` }];
  },
};

export default nextConfig;
