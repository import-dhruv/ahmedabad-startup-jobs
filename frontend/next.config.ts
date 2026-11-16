import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Standard ISR: pages declare their own `revalidate` window so job and
  // startup listings refresh without a full rebuild.
  cacheComponents: false,
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
