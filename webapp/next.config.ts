import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Allows opening the dev server through a tunnel (ngrok, cloudflared) inside Telegram.
  allowedDevOrigins: ["*.ngrok-free.app", "*.trycloudflare.com"],
};

export default nextConfig;
