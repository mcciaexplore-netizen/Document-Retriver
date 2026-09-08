import type { NextConfig } from "next";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { parseEnv } from "node:util";

// Direct npm starts must use the same local API as the PowerShell launchers.
// Process/container settings take precedence over the root development file.
const envPath = resolve(process.cwd(), "../.env");
const localEnv = existsSync(envPath) ? parseEnv(readFileSync(envPath, "utf8")) : {};
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
