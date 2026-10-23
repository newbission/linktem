import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const isStandalone = process.env.NEXT_OUTPUT === 'standalone';

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Docker 이미지(apps/web/Dockerfile)에서만 standalone 출력. Vercel 은 기본 출력 사용
  ...(isStandalone && { output: 'standalone' }),
  ...(isStandalone && { experimental: { outputFileTracingRoot: path.join(__dirname, '../..') } }),
  // /api/*, /health 는 src/app 의 Route Handler 가 API_PROXY_TARGET 으로 프록시한다 (lib/server/api-proxy.ts)
  poweredByHeader: false,
  transpilePackages: ['@linktem/types'],
  async headers() {
    return [
      {
        // 서비스 워커는 항상 최신 버전을 받아야 함
        source: '/sw.js',
        headers: [
          { key: 'Cache-Control', value: 'no-cache, no-store, must-revalidate' },
          { key: 'Service-Worker-Allowed', value: '/' },
          { key: 'Content-Type', value: 'application/javascript; charset=utf-8' },
        ],
      },
      {
        source: '/manifest.json',
        headers: [{ key: 'Content-Type', value: 'application/manifest+json; charset=utf-8' }],
      },
      {
        source: '/(.*)',
        headers: [
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
          { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=()' },
        ],
      },
    ];
  },
};

export default nextConfig;
