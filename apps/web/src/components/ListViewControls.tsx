'use client';

import { ChevronsDownUp, ChevronsUpDown, LayoutList, Rows3 } from 'lucide-react';

interface Props {
  compact: boolean;
  onCompactChange: (compact: boolean) => void;
  /** 판매처별/영상별 보기일 때만: 모든 묶음 접기·펼치기 */
  groupCount: number;
  allCollapsed: boolean;
  onCollapseAll: (collapsed: boolean) => void;
}

export function ListViewControls({ compact, onCompactChange, groupCount, allCollapsed, onCollapseAll }: Props) {
  return (
    <div className="flex items-center justify-between gap-2 px-1">
      <div role="radiogroup" aria-label="카드 보기 방식" className="inline-flex rounded-xl bg-slate-100 p-0.5 text-xs font-semibold">
        <button
          type="button"
          role="radio"
          aria-checked={!compact}
          onClick={() => onCompactChange(false)}
          className={`inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 ${!compact ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500'}`}
        >
          <LayoutList size={13} aria-hidden />
          자세히
        </button>
        <button
          type="button"
          role="radio"
          aria-checked={compact}
          onClick={() => onCompactChange(true)}
          className={`inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 ${compact ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500'}`}
        >
          <Rows3 size={13} aria-hidden />
          간단히
        </button>
      </div>
      {groupCount > 1 && (
        <button
          type="button"
          onClick={() => onCollapseAll(!allCollapsed)}
          className="inline-flex items-center gap-1 rounded-lg px-2 py-1.5 text-xs font-semibold text-slate-500 hover:bg-slate-100"
        >
          {allCollapsed ? <ChevronsUpDown size={14} aria-hidden /> : <ChevronsDownUp size={14} aria-hidden />}
          {allCollapsed ? '모두 펼치기' : '모두 접기'}
        </button>
      )}
    </div>
  );
}
