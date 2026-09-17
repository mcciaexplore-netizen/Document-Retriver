import type { NextConfig } from "next";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { parseEnv } from "node:util";

// Next.js runs from frontend/, while local Compose and launchers share root .env.
// Hosting dashboard / process settings always win over the local file.
const localEnvPath = resolve(process.cwd(), "..", ".env");
const localEnv =
  !process.env.VERCEL && existsSync(localEnvPath)
    ? parseEnv(readFileSync(localEnvPath, "utf8"))
    : {};
if (process.env.VERCEL) {
  const value = process.env.BACKEND_URL;
  if (!value) {
    throw new Error("BACKEND_URL is required for Vercel builds. Set it to the public HTTPS backend origin before deploying.");
  }
  const target = new URL(value);
  if (
    target.protocol !== "https:" ||
    ["localhost", "127.0.0.1", "[::1]"].includes(target.hostname) ||
    target.username ||
    target.password ||
    target.search ||
    target.hash ||
    target.pathname !== "/"
  ) {
    throw new Error(
      "BACKEND_URL must be a public HTTPS origin such as https://your-backend.onrender.com, without /api, credentials, or query parameters.",
    );
  }
}
const backendUrl = (
  process.env.BACKEND_URL ||
  localEnv.BACKEND_URL ||
  (process.env.VERCEL
    ? ""
    : `http://127.0.0.1:${process.env.BACKEND_PORT || localEnv.BACKEND_PORT || "8001"}`)
).replace(/\/+$/, "");
const config: NextConfig = {
  env: { NEXT_PUBLIC_BACKEND_CONFIGURED: backendUrl ? "true" : "false" },
  turbopack: { root: process.cwd() },
  // Vercel's adapter packages the app itself; standalone output is for Docker.
  output: process.env.VERCEL ? undefined : "standalone",
  poweredByHeader: false,
  async rewrites() {
    if (!backendUrl) return [];
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "same-origin" },
          { key: "X-Frame-Options", value: "SAMEORIGIN" },
        ],
      },
    ];
  },
};
export default config;
