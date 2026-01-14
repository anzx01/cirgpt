/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Remove 'output: export' for development mode
  // Uncomment this for production build: output: 'export',
  images: {
    unoptimized: true,
  },
}

module.exports = nextConfig