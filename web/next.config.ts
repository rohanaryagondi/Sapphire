import type { NextConfig } from "next";

// The Python firm server (frontend2/server.py) is the backend. We proxy every /api/*
// call to it so the browser talks same-origin (no CORS) and SSE streams cleanly.
// Override the target with SAPPHIRE_API (e.g. http://127.0.0.1:8100) if the server runs
// on a different port. Default per the build brief: 127.0.0.1:8201.
const API_TARGET = process.env.SAPPHIRE_API ?? "http://127.0.0.1:8201";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${API_TARGET}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
