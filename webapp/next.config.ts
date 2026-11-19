import { mkdirSync, writeFileSync } from "node:fs";
import type { NextConfig } from "next";

// Project site is served at https://<user>.github.io/planerok/
const basePath = process.env.NEXT_PUBLIC_BASE_PATH || undefined;

// Each build gets its own id. The page bakes it in and compares it with public/version.json,
// so an open Mini App notices a new deploy and reloads itself.
const buildId = process.env.NEXT_PUBLIC_BUILD_ID || Date.now().toString(36);
mkdirSync("public", { recursive: true });
writeFileSync("public/version.json", JSON.stringify({ build: buildId }));

const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  ...(basePath ? { basePath } : {}),
  reactStrictMode: true,
  env: { NEXT_PUBLIC_BUILD_ID: buildId },
  // Allows opening the dev server through a tunnel (ngrok, cloudflared) inside Telegram.
  allowedDevOrigins: ["*.ngrok-free.app", "*.trycloudflare.com"],
};

export default nextConfig;
