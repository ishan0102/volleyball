import type { NextConfig } from "next"

const config: NextConfig = {
  devIndicators: false,
  // Rendering a reel from phone footage can take several minutes.
  experimental: { proxyTimeout: 600_000 },
  async rewrites() {
    return [
      "/match",
      "/touch-scan",
      "/scan-touches",
      "/review-touch",
      "/save",
      "/tag",
      "/review-appearance",
      "/undo-review",
      "/suggest",
      "/export",
      "/preview.mp4",
      "/thumb/:path*",
      "/scan-crop/:path*",
      "/exports/:path*",
    ].map((source) => ({
      source,
      destination: `http://127.0.0.1:8732${source}`,
    }))
  },
}
export default config
