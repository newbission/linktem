/* Linktem Service Worker — 앱 셸 오프라인 캐시
 * - 탐색(HTML): network-first → 실패 시 캐시 → 최후에 '/' 셸
 * - /_next/static/*: cache-first (해시 파일명 → 불변)
 * - 아이콘/manifest: stale-while-revalidate
 * - API·R2 이미지(교차 출처)는 건드리지 않음: 이미지는 IndexedDB(오프라인 장보기 저장)가 담당
 */
const VERSION = 'v1';
const SHELL_CACHE = `linktem-shell-${VERSION}`;
const STATIC_CACHE = `linktem-static-${VERSION}`;
const SHELL_URLS = ['/', '/manifest.json', '/icons/icon-192.png', '/icons/icon-512.png'];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(SHELL_CACHE)
      .then((cache) => cache.addAll(SHELL_URLS))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((key) => key.startsWith('linktem-') && ![SHELL_CACHE, STATIC_CACHE].includes(key))
            .map((key) => caches.delete(key)),
        ),
      )
      .then(() => self.clients.claim()),
  );
});

// 첫 방문 시 SW 설치 전에 이미 받은 정적 리소스를 캐시 (ServiceWorkerRegister 가 전송)
self.addEventListener('message', (event) => {
  const data = event.data || {};
  if (data.type !== 'CACHE_URLS' || !Array.isArray(data.urls)) return;
  event.waitUntil(
    Promise.all(
      data.urls
        .filter((url) => typeof url === 'string')
        .map(async (url) => {
          const target = new URL(url, self.location.origin);
          if (target.origin !== self.location.origin) return;
          const cacheName = target.pathname.startsWith('/_next/static/') ? STATIC_CACHE : SHELL_CACHE;
          const cache = await caches.open(cacheName);
          if (await cache.match(target.href)) return;
          try {
            const res = await fetch(target.href, { credentials: 'same-origin' });
            if (res.ok) await cache.put(target.href, res);
          } catch {
            /* 오프라인 */
          }
        }),
    ),
  );
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (request.mode === 'navigate') {
    event.respondWith(networkFirstNavigation(request));
    return;
  }
  if (url.pathname.startsWith('/_next/static/')) {
    event.respondWith(cacheFirst(request, STATIC_CACHE));
    return;
  }
  if (url.pathname.startsWith('/icons/') || url.pathname === '/manifest.json') {
    event.respondWith(staleWhileRevalidate(request, SHELL_CACHE));
  }
});

async function networkFirstNavigation(request) {
  const cache = await caches.open(SHELL_CACHE);
  try {
    const response = await fetch(request);
    // 쿼리(?url=, ?source=) 와 무관하게 경로 단위로 셸 캐시
    if (response.ok) await cache.put(new URL(request.url).pathname, response.clone());
    return response;
  } catch {
    const pathname = new URL(request.url).pathname;
    return (
      (await cache.match(pathname)) ||
      (await cache.match('/')) ||
      new Response('<h1>오프라인</h1><p>인터넷 연결 후 다시 열어 주세요.</p>', {
        status: 503,
        headers: { 'Content-Type': 'text/html; charset=utf-8' },
      })
    );
  }
}

async function cacheFirst(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);
  if (cached) return cached;
  const response = await fetch(request);
  if (response.ok) await cache.put(request, response.clone());
  return response;
}

async function staleWhileRevalidate(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);
  const network = fetch(request)
    .then((response) => {
      if (response.ok) cache.put(request, response.clone());
      return response;
    })
    .catch(() => cached);
  return cached || network;
}
