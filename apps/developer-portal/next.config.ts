import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  output: "standalone",
  outputFileTracingRoot: path.join(__dirname),
  transpilePackages: ["swagger-ui-react"],
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-Frame-Options", value: "SAMEORIGIN" }
        ]
      }
    ];
  },
  async redirects() {
    return [
      { source: "/docs", destination: "/docs/quick-start", permanent: false },
      { source: "/sdk", destination: "/docs/javascript-sdk", permanent: false }
    ];
  }
};

export default nextConfig;
