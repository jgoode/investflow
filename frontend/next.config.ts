import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Monorepo: lock this app to frontend/ (root pnpm-lock.yaml for Playwright confuses inference).
  turbopack: {
    root: __dirname,
  },
};

export default nextConfig;
