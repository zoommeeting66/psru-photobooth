/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Lean container image for `docker compose` (produces .next/standalone/server.js)
  output: "standalone",
  // API-served images (captures/outputs) use plain <img>; no next/image domains needed.
};

export default nextConfig;
