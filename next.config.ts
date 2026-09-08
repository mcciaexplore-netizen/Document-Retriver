import type { NextConfig } from "next";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { parseEnv } from "node:util";

// Direct npm starts must use the same local API as the PowerShell launchers.
// Process/container settings take precedence over the root development file.
const envPath = resolve(process.cwd(), ".env");
const localEnv = !process.env.VERCEL && existsSync(envPath)
  ? parseEnv(readFileSync(envPath, "utf8"))
  : {};
if (process.env.VERCEL) {
  const value = process.env.BACKEND_URL;
  if (!value) {
    throw new Error("Set BACKEND_URL in Vercel Environment Variables to your deployed backend HTTPS URL, then redeploy. Use the repository root (.) as the Root Directory.");
  }
  const target = new URL(value);
  if (target.protocol !== "https:" || ["localhost", "127.0.0.1", "[::1]"].includes(target.hostname) || target.username || target.password || target.search || target.hash || target.pathname !== "/") {
    throw new Error("BACKEND_URL must be a public HTTPS origin such as https://your-backend.onrender.com, without /api, credentials, or query parameters.");
  }
}
const backendUrl = (
  process.env.BACKEND_URL ||
  localEnv.BACKEND_URL ||
  `http://127.0.0.1:${process.env.BACKEND_PORT || localEnv.BACKEND_PORT || "8000"}`
).replace(/\/+$/, "");
const config: NextConfig = {
  turbopack: { root: process.cwd() },
  output: "standalone",
  poweredByHeader: false,
  async rewrites() {
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
