'use client';

import { LoaderCircle } from 'lucide-react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense, useEffect } from 'react';

import { pickSharedUrl } from '@/lib/share';

/**
 * Web Share Target 진입점 (manifest.json share_target.action = "/share").
 * SNS 앱에서 [공유하기] → Linktem 을 고르면 title/text/url 파라미터로 열린다.
 */
function ShareHandler() {
  const router = useRouter();
  const params = useSearchParams();

  useEffect(() => {
    const url = pickSharedUrl({ url: params.get('url'), text: params.get('text'), title: params.get('title') });
    router.replace(url ? `/?url=${encodeURIComponent(url)}` : '/?share_error=1');
  }, [params, router]);

  return (
    <main className="flex min-h-dvh flex-col items-center justify-center gap-3 text-slate-600">
      <LoaderCircle className="animate-spin text-brand-600" size={28} aria-hidden />
      <p className="text-sm font-medium">공유한 링크를 여는 중…</p>
    </main>
  );
}

export default function SharePage() {
  return (
    <Suspense>
      <ShareHandler />
    </Suspense>
  );
}
