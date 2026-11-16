import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Standard ISR: pages declare their own `revalidate` window so job and
  // startup listings refresh without a full rebuild.
  cacheComponents: false,
  // Emit a self-contained server bundle for the Docker image.
  output: "standalone",
  async rewrites() {
    // Proxy the API through the frontend so the browser talks to a single
    // origin. The backend location is a runtime variable (API_PROXY_TARGET),
    // which means the backend can move without rebuilding the frontend.
    const target = process.env.API_PROXY_TARGET ?? "http://localhost:8000";
    return [
      { source: "/api/:path*", destination: `${target}/api/:path*` },
    ];
  },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
