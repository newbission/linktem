'use client';

import { useEffect } from 'react';

/** 서비스 워커 등록 + 이미 로드된 정적 리소스를 SW 캐시에 넘겨 첫 방문부터 오프라인 동작 보장 */
export function ServiceWorkerRegister() {
  useEffect(() => {
    if (!('serviceWorker' in navigator) || process.env.NODE_ENV !== 'production') return;

    const register = async () => {
      try {
        const registration = await navigator.serviceWorker.register('/sw.js', { scope: '/' });
        await navigator.serviceWorker.ready;
        const urls = [
          window.location.pathname,
          ...performance
            .getEntriesByType('resource')
            .map((e) => e.name)
            .filter((u) => u.startsWith(window.location.origin) && u.includes('/_next/static/')),
        ];
        (registration.active ?? navigator.serviceWorker.controller)?.postMessage({ type: 'CACHE_URLS', urls });
      } catch (err) {
        console.warn('[Linktem] service worker registration failed', err);
      }
    };

    if (document.readyState === 'complete') void register();
    else window.addEventListener('load', register, { once: true });
  }, []);

  return null;
}
