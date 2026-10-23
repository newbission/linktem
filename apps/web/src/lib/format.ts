export function formatTimestamp(sec: number): string {
  const total = Math.max(0, Math.floor(sec));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const mmss = `${m.toString().padStart(h ? 2 : 1, '0')}:${s.toString().padStart(2, '0')}`;
  return h ? `${h}:${mmss}` : mmss;
}

/** 원본 영상의 해당 시점으로 이동하는 URL (유튜브만 타임스탬프 지원) */
export function timestampUrl(sourceUrl: string | undefined, sec: number): string | undefined {
  if (!sourceUrl) return undefined;
  try {
    const url = new URL(sourceUrl);
    if (url.hostname.includes('youtube.com') || url.hostname === 'youtu.be') {
      url.searchParams.set('t', `${Math.floor(sec)}s`);
    }
    return url.toString();
  } catch {
    return sourceUrl;
  }
}

export function formatRelativeTime(ts: number): string {
  const diff = Date.now() - ts;
  const min = Math.floor(diff / 60_000);
  if (min < 1) return '방금';
  if (min < 60) return `${min}분 전`;
  const hours = Math.floor(min / 60);
  if (hours < 24) return `${hours}시간 전`;
  return `${Math.floor(hours / 24)}일 전`;
}

const RETAILER_STYLES: Record<string, string> = {
  이마트: 'bg-yellow-100 text-yellow-800 ring-yellow-200',
  이마트에브리데이: 'bg-yellow-100 text-yellow-800 ring-yellow-200',
  트레이더스: 'bg-lime-100 text-lime-800 ring-lime-200',
  노브랜드: 'bg-yellow-50 text-yellow-900 ring-yellow-200',
  코스트코: 'bg-red-100 text-red-800 ring-red-200',
  홈플러스: 'bg-rose-100 text-rose-800 ring-rose-200',
  롯데마트: 'bg-red-50 text-red-700 ring-red-200',
  쿠팡: 'bg-sky-100 text-sky-800 ring-sky-200',
  다이소: 'bg-pink-100 text-pink-800 ring-pink-200',
  올리브영: 'bg-lime-50 text-lime-800 ring-lime-200',
  컬리: 'bg-purple-100 text-purple-800 ring-purple-200',
  이케아: 'bg-blue-100 text-blue-800 ring-blue-200',
};

export function retailerStyle(retailer: string): string {
  return RETAILER_STYLES[retailer] ?? 'bg-slate-100 text-slate-700 ring-slate-200';
}
