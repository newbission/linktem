'use client';

import { Film, LayoutList, Store } from 'lucide-react';

import type { FilterTab } from '@/lib/grouping';

const TABS: { id: FilterTab; label: string; icon: typeof LayoutList }[] = [
  { id: 'all', label: '전체 보기', icon: LayoutList },
  { id: 'retailer', label: '판매처별', icon: Store },
  { id: 'video', label: '영상별', icon: Film },
];

export function FilterTabs({ value, onChange }: { value: FilterTab; onChange: (tab: FilterTab) => void }) {
  return (
    <div role="tablist" aria-label="리스트 보기 방식" className="grid grid-cols-3 gap-1 rounded-2xl bg-slate-100 p-1">
      {TABS.map(({ id, label, icon: Icon }) => {
        const active = value === id;
        return (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(id)}
            className={`inline-flex items-center justify-center gap-1.5 rounded-xl py-2 text-sm font-semibold transition ${
              active ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500'
            }`}
          >
            <Icon size={15} aria-hidden />
            {label}
          </button>
        );
      })}
    </div>
  );
}
