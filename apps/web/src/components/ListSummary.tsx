'use client';

import { Eraser, RotateCcw } from 'lucide-react';

interface Props {
  done: number;
  total: number;
  videoCount: number;
  onResetChecks: () => void;
  onClearAll: () => void;
}

export function ListSummary({ done, total, videoCount, onResetChecks, onClearAll }: Props) {
  const percent = total ? Math.round((done / total) * 100) : 0;
  return (
    <div className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-200/80">
      <div className="flex items-baseline justify-between">
        <p className="text-sm text-slate-600">
          영상 <b className="text-slate-900">{videoCount}</b>개 · 상품 <b className="text-slate-900">{total}</b>개
        </p>
        <p className="text-sm font-bold text-brand-700">
          {done === total && total > 0 ? '장보기 완료! 🎉' : `${done}개 담음`}
        </p>
      </div>
      <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100">
        <div className="h-full rounded-full bg-brand-500 transition-[width]" style={{ width: `${percent}%` }} />
      </div>
      <div className="mt-3 flex justify-end gap-1">
        <button
          type="button"
          onClick={onResetChecks}
          disabled={done === 0}
          className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-medium text-slate-500 hover:bg-slate-100 disabled:opacity-40"
        >
          <RotateCcw size={12} aria-hidden />
          체크 초기화
        </button>
        <button
          type="button"
          onClick={() => {
            if (window.confirm('리스트를 모두 지울까요?')) onClearAll();
          }}
          className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-medium text-slate-500 hover:bg-slate-100 hover:text-red-600"
        >
          <Eraser size={12} aria-hidden />
          전체 지우기
        </button>
      </div>
    </div>
  );
}
