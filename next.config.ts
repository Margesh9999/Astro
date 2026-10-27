import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  /* config options here */
  typescript: {
    ignoreBuildErrors: true,
  },
  reactStrictMode: false,
  // Allow the IM preview origin(s) to load /_next/* dev assets without warnings
  allowedDevOrigins: ["*.space-z.ai"],
};

export default nextConfig;
