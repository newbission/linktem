'use client';

import { Check, ChevronDown, Flag, TriangleAlert } from 'lucide-react';
import { useState, type ReactNode } from 'react';

import type { FeedbackType, ShoppingItem, VideoAnalysisResponse } from '@linktem/types';

import { retailerStyle } from '@/lib/format';

interface Props {
  item: ShoppingItem;
  video: VideoAnalysisResponse;
  number?: number;
  reports: FeedbackType[];
  online: boolean;
  showVideoTitle?: boolean;
  /** 판매처별 보기에서는 묶음 제목이 판매처라 생략 */
  showRetailer: boolean;
  onToggle: (itemId: string) => void;
  /** 펼쳤을 때 보여줄 자세한 카드 (onCollapse: 다시 접기) */
  renderDetail: (onCollapse: () => void) => ReactNode;
}

/** 간단히 보기 한 줄: 체크 · 번호 · 이름(+에디션) · 주의 표시 · 판매처. 누르면 자세한 카드로 펼침 */
export function ItemRow({ item, number, reports, showRetailer, onToggle, renderDetail }: Props) {
  const [expanded, setExpanded] = useState(false);
  const checked = item.is_checked;
  const reported = reports.some((t) => t !== 'SAME');

  if (expanded) {
    return <li className="p-1.5">{renderDetail(() => setExpanded(false))}</li>;
  }

  return (
    <li className={`flex items-center gap-2.5 px-3 py-2.5 ${checked ? 'opacity-55' : ''}`}>
      <button
        type="button"
        role="checkbox"
        aria-checked={checked}
        aria-label={`${item.name_ko} ${checked ? '체크 해제' : '장바구니에 담음으로 체크'}`}
        onClick={() => onToggle(item.id)}
        className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-md border-2 transition active:scale-90 ${
          checked ? 'border-brand-600 bg-brand-600 text-white' : 'border-slate-300 bg-white text-transparent'
        }`}
      >
        <Check size={14} strokeWidth={3.5} aria-hidden />
      </button>
      <button
        type="button"
        onClick={() => setExpanded(true)}
        aria-expanded={false}
        className="flex min-w-0 flex-1 items-center gap-2 text-left"
        aria-label={`${number ? `${number}번 ` : ''}${item.name_ko} 자세히 보기`}
      >
        {number !== undefined && (
          <span
            className={`inline-flex h-5 min-w-5 shrink-0 items-center justify-center rounded-md px-1 text-[11px] font-extrabold ${
              checked ? 'bg-slate-200 text-slate-500' : 'bg-slate-900 text-white'
            }`}
          >
            {number}
          </span>
        )}
        <span className="min-w-0 flex-1">
          <span className={`block truncate text-[15px] font-semibold text-slate-900 ${checked ? 'line-through' : ''}`}>
            {item.name_ko}
          </span>
          {item.edition_note && <span className="block truncate text-[11px] text-brand-700">{item.edition_note}</span>}
        </span>
        {item.caution && (
          <TriangleAlert size={15} className="shrink-0 text-amber-500" aria-label="헷갈리지 말 점 있음" />
        )}
        {reported && <Flag size={13} className="shrink-0 text-amber-500" aria-label="제보함" />}
        {showRetailer && (
          <span
            className={`max-w-[5.5rem] shrink-0 truncate rounded-full px-1.5 py-0.5 text-[10px] font-bold ring-1 ring-inset ${retailerStyle(item.retailer)}`}
          >
            {item.retailer}
          </span>
        )}
        <ChevronDown size={15} className="shrink-0 text-slate-300" aria-hidden />
      </button>
    </li>
  );
}
