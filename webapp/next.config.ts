import type { NextConfig } from "next";

// Project site is served at https://<user>.github.io/planerok/
const basePath = process.env.NEXT_PUBLIC_BASE_PATH || undefined;

const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  ...(basePath ? { basePath } : {}),
  reactStrictMode: true,
  // Allows opening the dev server through a tunnel (ngrok, cloudflared) inside Telegram.
  allowedDevOrigins: ["*.ngrok-free.app", "*.trycloudflare.com"],
};

export default nextConfig;
