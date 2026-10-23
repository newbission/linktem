/**
 * 구글 애드센스 규격 배너 플레이스홀더.
 * 승인 전에는 정적 영역만 확보해 레이아웃 이동(CLS)을 방지하고,
 * 승인 후 NEXT_PUBLIC_ADSENSE_CLIENT 와 slot 을 넣어 <ins class="adsbygoogle"> 로 교체한다.
 */
const SIZES = {
  // 모바일 배너 (320x100 Large Mobile Banner)
  banner: { width: 320, height: 100, label: '320 × 100' },
  // 로딩 화면용 (300x250 Medium Rectangle)
  rectangle: { width: 300, height: 250, label: '300 × 250' },
} as const;

export function AdSlot({ size = 'banner', slot }: { size?: keyof typeof SIZES; slot?: string }) {
  const { width, height, label } = SIZES[size];
  return (
    <aside
      aria-label="광고"
      data-ad-client={process.env.NEXT_PUBLIC_ADSENSE_CLIENT || undefined}
      data-ad-slot={slot}
      className="mx-auto flex max-w-full flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 bg-slate-50 text-slate-400"
      style={{ width, height, minHeight: height }}
    >
      <span className="text-[10px] font-semibold uppercase tracking-widest">AD</span>
      <span className="text-[11px]">{label}</span>
    </aside>
  );
}
