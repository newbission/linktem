'use client';

import { Download, ImageIcon, LoaderCircle, PackageSearch, X } from 'lucide-react';
import { useEffect, useState } from 'react';

import { AdSlot } from './AdSlot';

const STEPS = [
  { icon: Download, text: '영상을 가져오고 있어요', until: 8 },
  { icon: PackageSearch, text: 'AI가 영상 속 상품을 찾고 있어요', until: 35 },
  { icon: ImageIcon, text: '상품 스틸컷을 만들고 있어요', until: 55 },
  { icon: LoaderCircle, text: '거의 다 됐어요. 조금만 기다려 주세요', until: Infinity },
] as const;

/** connecting: 서버 응답 확인 중(무료 서버 콜드 스타트 포함) / analyzing: 분석 요청 진행 중 */
export type AnalysisPhase = 'connecting' | 'analyzing';

// 연결이 이보다 오래 걸리면 안내 문구를 한 줄 덧붙인다
const SLOW_CONNECT_SEC = 15;

interface Props {
  url: string;
  phase: AnalysisPhase;
  onCancel: () => void;
}

/** 연결 대기와 분석을 사용자에게는 하나의 '분석 중' 흐름으로 보여준다 */
export function AnalysisLoading({ url, phase, onCancel }: Props) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const started = Date.now();
    const timer = setInterval(() => setElapsed((Date.now() - started) / 1000), 500);
    return () => clearInterval(timer);
  }, []);

  const connecting = phase === 'connecting';
  // 연결 대기 중에는 첫 단계('영상을 가져오고 있어요')에 머문다
  const step = connecting ? STEPS[0] : (STEPS.find((s) => elapsed < s.until) ?? STEPS[STEPS.length - 1]);
  const Icon = step.icon;
  const slowConnect = connecting && elapsed >= SLOW_CONNECT_SEC;
  // 체감 진행률: 60초에 걸쳐 92% 까지 감속 곡선 (연결 대기 중에는 15% 에서 멈춤)
  const curve = Math.round(100 * (1 - Math.exp(-elapsed / 25)));
  const progress = connecting ? Math.min(15, curve) : Math.min(92, curve);

  return (
    <section aria-live="polite" aria-busy="true" className="space-y-5 rounded-3xl bg-white p-5 shadow-sm ring-1 ring-slate-100">
      <div className="flex items-start gap-3">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-brand-50 text-brand-600">
          <Icon size={22} className={step.icon === LoaderCircle ? 'animate-spin' : 'animate-pulse'} aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <p className="font-bold text-slate-900">{step.text}</p>
          <p className="mt-0.5 truncate text-xs text-slate-500">
            {slowConnect ? '서버 연결에 시간이 조금 걸리고 있어요. 최대 1분 정도 걸릴 수 있어요.' : url}
          </p>
        </div>
        <button
          type="button"
          onClick={onCancel}
          className="rounded-full p-1.5 text-slate-400 hover:bg-slate-100"
          aria-label="분석 취소"
        >
          <X size={18} />
        </button>
      </div>

      <div className="h-2 overflow-hidden rounded-full bg-slate-100" role="progressbar" aria-valuenow={progress} aria-valuemin={0} aria-valuemax={100}>
        <div className="h-full rounded-full bg-brand-500 transition-[width] duration-500" style={{ width: `${progress}%` }} />
      </div>

      <ul className="space-y-2" aria-hidden>
        {[0, 1, 2].map((i) => (
          <li key={i} className="flex gap-3 rounded-2xl bg-slate-50 p-3">
            <div className="relative h-16 w-16 shrink-0 overflow-hidden rounded-xl bg-slate-200">
              <div className="absolute inset-0 animate-shimmer bg-gradient-to-r from-transparent via-white/60 to-transparent" />
            </div>
            <div className="flex-1 space-y-2 py-1">
              <div className="h-3.5 w-3/4 rounded bg-slate-200" />
              <div className="h-3 w-1/2 rounded bg-slate-200" />
              <div className="h-5 w-16 rounded-full bg-slate-200" />
            </div>
          </li>
        ))}
      </ul>

      <p className="text-center text-xs text-slate-500">
        처음 분석하는 영상은 30초~1분 정도 걸려요. 한 번 분석된 영상은 바로 열려요.
      </p>

      <AdSlot size="rectangle" slot="loading" />
    </section>
  );
}
