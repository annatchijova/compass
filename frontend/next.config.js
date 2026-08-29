const path = require("node:path");

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Standalone output so the production server can be copied into a slim
  // Cloud Run image (.next/standalone + .next/static + public).
  output: "standalone",
  reactStrictMode: true,
  // Pin the file-tracing root to THIS directory. Without it, Next detects the
  // parent monorepo lockfile and roots the standalone trace one level up,
  // which breaks the Docker copy of .next/standalone.
  outputFileTracingRoot: path.join(__dirname),
};

module.exports = nextConfig;
