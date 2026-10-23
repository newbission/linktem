const URL_IN_TEXT = /https?:\/\/[^\s<>"']+/i;

const SUPPORTED_HOSTS = [
  'youtube.com',
  'youtu.be',
  'instagram.com',
  'tiktok.com',
];

/** 공유 텍스트("이 영상 봐! https://...")에서 첫 URL 추출 */
export function extractUrl(text: string | null | undefined): string | null {
  if (!text) return null;
  const match = text.match(URL_IN_TEXT);
  if (!match) return null;
  return match[0].replace(/[).,!?\]}>]+$/, '');
}

export function isSupportedUrl(url: string): boolean {
  try {
    const host = new URL(url).hostname.toLowerCase();
    return SUPPORTED_HOSTS.some((h) => host === h || host.endsWith(`.${h}`));
  } catch {
    return false;
  }
}

/** Web Share Target 파라미터(title/text/url)에서 분석할 URL 고르기 — 인스타그램은 text 에 URL 을 담아 보냄 */
export function pickSharedUrl(params: { url?: string | null; text?: string | null; title?: string | null }): string | null {
  return extractUrl(params.url) ?? extractUrl(params.text) ?? extractUrl(params.title);
}

const YT_ID = /^[A-Za-z0-9_-]{11}$/;

/**
 * 같은 영상을 가리키는 여러 URL 형태를 하나의 키로 (백엔드 url_utils.normalize_video_url 와 같은 규칙).
 * youtu.be/ID, /shorts/ID, watch?v=ID&si=… → "youtube:ID"
 */
export function canonicalVideoKey(raw: string | undefined | null): string | null {
  if (!raw) return null;
  let url: URL;
  try {
    url = new URL(raw);
  } catch {
    return null;
  }
  const host = url.hostname.toLowerCase().replace(/^(www|m|music)\./, '');
  const parts = url.pathname.split('/').filter(Boolean);

  if (host === 'youtu.be' || host === 'youtube.com') {
    let id: string | null = null;
    if (host === 'youtu.be') id = parts[0] ?? null;
    else if (parts[0] === 'watch') id = url.searchParams.get('v');
    else if (['shorts', 'embed', 'live', 'v'].includes(parts[0] ?? '')) id = parts[1] ?? null;
    return id && YT_ID.test(id) ? `youtube:${id}` : null;
  }
  if (host === 'instagram.com') {
    const idx = parts.findIndex((p) => ['reel', 'reels', 'p', 'tv'].includes(p));
    return idx >= 0 && parts[idx + 1] ? `instagram:${parts[idx + 1]}` : null;
  }
  if (host === 'tiktok.com') {
    const idx = parts.findIndex((p) => p === 'video' || p === 'photo');
    const id = idx >= 0 ? parts[idx + 1] : undefined;
    return id && /^\d+$/.test(id) ? `tiktok:${id}` : null;
  }
  return null;
}
