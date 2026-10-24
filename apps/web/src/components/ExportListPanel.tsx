'use client';

import { ChevronDown, Copy, Share2 } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';

import { copyText, formatListText, type ExportOptions } from '@/lib/export';
import type { StoredList } from '@/lib/list-store';

interface Props {
  list: StoredList;
  onNotice: (message: string) => void;
}

/** 리스트를 텍스트로 복사하거나 다른 앱(카카오톡·메모 등)으로 공유 */
export function ExportListPanel({ list, onNotice }: Props) {
  const [open, setOpen] = useState(false);
  const [options, setOptions] = useState<ExportOptions>({ remainingOnly: false, includeNotes: true });
  const [canShare, setCanShare] = useState(false);

  useEffect(() => {
    setCanShare(typeof navigator.share === 'function');
  }, []);

  const text = useMemo(
    () =>
      formatListText(
        list.videos,
        list.checked,
        options,
        process.env.NEXT_PUBLIC_SITE_URL || (typeof window !== 'undefined' ? window.location.origin : undefined),
      ),
    [list.videos, list.checked, options],
  );

  const copy = async () => {
    onNotice((await copyText(text)) ? '리스트를 복사했어요. 원하는 곳에 붙여넣어 주세요.' : '복사하지 못했어요.');
  };

  const share = async () => {
    try {
      await navigator.share({ title: 'Linktem 장보기 리스트', text });
    } catch (err) {
      // 사용자가 공유 시트를 닫은 경우(AbortError)는 조용히 무시
      if (!(err instanceof DOMException && err.name === 'AbortError')) await copy();
    }
  };

  const toggle = (key: keyof ExportOptions) => setOptions((prev) => ({ ...prev, [key]: !prev[key] }));

  return (
    <div className="rounded-2xl bg-white shadow-sm ring-1 ring-slate-200/80">
      <div className="flex items-center gap-2 p-2">
        <button
          type="button"
          onClick={copy}
          className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-xl bg-slate-100 px-3 py-2.5 text-sm font-bold text-slate-800 transition active:scale-[0.98]"
        >
          <Copy size={15} aria-hidden />
          리스트 복사
        </button>
        {canShare && (
          <button
            type="button"
            onClick={share}
            className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-xl bg-brand-600 px-3 py-2.5 text-sm font-bold text-white transition active:scale-[0.98]"
          >
            <Share2 size={15} aria-hidden />
            공유하기
          </button>
        )}
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          aria-controls="export-options"
          className="rounded-xl p-2.5 text-slate-500 hover:bg-slate-100"
          aria-label="내보내기 옵션"
        >
          <ChevronDown size={16} className={`transition ${open ? 'rotate-180' : ''}`} />
        </button>
      </div>

      {open && (
        <div id="export-options" className="space-y-3 border-t border-slate-100 p-3">
          <div className="flex flex-wrap gap-x-4 gap-y-2 text-sm text-slate-700">
            <label className="inline-flex items-center gap-2">
              <input
                type="checkbox"
                checked={options.remainingOnly}
                onChange={() => toggle('remainingOnly')}
                className="h-4 w-4 accent-brand-600"
              />
              남은 항목만
            </label>
            <label className="inline-flex items-center gap-2">
              <input
                type="checkbox"
                checked={options.includeNotes}
                onChange={() => toggle('includeNotes')}
                className="h-4 w-4 accent-brand-600"
              />
              메모 포함 (헷갈리지 말 점·추천 이유)
            </label>
          </div>
          <pre className="max-h-56 overflow-auto whitespace-pre-wrap break-all rounded-xl bg-slate-50 p-3 text-xs leading-relaxed text-slate-700">
            {text}
          </pre>
        </div>
      )}
    </div>
  );
}
