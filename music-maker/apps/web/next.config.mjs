/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  images: {
    remotePatterns: [
      { protocol: 'https', hostname: 'cdn.music-maker.app' },
      { protocol: 'http', hostname: 'localhost' },
    ],
  },
  async rewrites() {
    return [
      // dev 환경에서 BE proxy (필요 시): /api/v1/* → http://localhost:8000/api/v1/*
      // next-auth 경로는 protect 됨 (/api/auth/*)
    ];
  },
};

export default nextConfig;
