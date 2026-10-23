import type { Metadata, Viewport } from 'next';

import { ServiceWorkerRegister } from '@/components/ServiceWorkerRegister';

import './globals.css';

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || 'http://localhost:3000';

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: 'Linktem 링크템 — 링크 하나로 완성되는 스마트 장보기 리스트',
    template: '%s | Linktem',
  },
  description:
    '유튜브·인스타그램·틱톡 장보기 영상 링크를 넣으면 AI가 영상 속 상품을 찾아 스틸컷·판매처·최저가가 붙은 체크리스트로 만들어 드려요.',
  applicationName: 'Linktem',
  manifest: '/manifest.json',
  appleWebApp: { capable: true, title: 'Linktem', statusBarStyle: 'default' },
  icons: {
    icon: [
      { url: '/icons/icon-192.png', sizes: '192x192', type: 'image/png' },
      { url: '/icons/icon-512.png', sizes: '512x512', type: 'image/png' },
    ],
    apple: [{ url: '/icons/apple-touch-icon.png', sizes: '180x180' }],
  },
  openGraph: {
    type: 'website',
    siteName: 'Linktem',
    title: 'Linktem — 링크 하나로 완성되는 스마트 장보기 리스트',
    description: 'SNS 장보기 영상을 체크리스트로. 오프라인에서도 체크하며 장보기.',
    locale: 'ko_KR',
    images: [{ url: '/icons/icon-512.png', width: 512, height: 512 }],
  },
  formatDetection: { telephone: false },
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  viewportFit: 'cover',
  themeColor: '#059669',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body className="min-h-dvh font-sans">
        {children}
        <ServiceWorkerRegister />
      </body>
    </html>
  );
}
