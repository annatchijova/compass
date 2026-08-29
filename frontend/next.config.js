/** @type {import('next').NextConfig} */
const nextConfig = {
  // Standalone output so the production server can be copied into a slim
  // Cloud Run image (.next/standalone + .next/static + public).
  output: "standalone",
  reactStrictMode: true,
};

module.exports = nextConfig;
