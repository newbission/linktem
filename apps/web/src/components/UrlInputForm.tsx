'use client';

import { ArrowRight, ClipboardPaste, Link2, LoaderCircle, X } from 'lucide-react';
import { useEffect, useRef, useState, type FormEvent } from 'react';

import { extractUrl, isSupportedUrl } from '@/lib/share';

interface Props {
  /** 분석 진행 중 — 입력/버튼 잠금, 버튼은 스피너 */
  loading?: boolean;
  /** 오프라인 등으로 분석 불가 */
  disabled?: boolean;
  /** 분석 성공 시 true — 성공했을 때만 입력창을 비운다 */
  onSubmit: (url: string) => Promise<boolean>;
}

export function UrlInputForm({ loading = false, disabled = false, onSubmit }: Props) {
  const [value, setValue] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [hint, setHint] = useState<string | null>(null);
  const [canReadClipboard, setCanReadClipboard] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const locked = loading || disabled;

  useEffect(() => {
    // 클립보드 읽기는 보안 컨텍스트 + 지원 브라우저에서만 버튼 노출 (Firefox 등은 미지원)
    setCanReadClipboard(window.isSecureContext && typeof navigator.clipboard?.readText === 'function');
  }, []);

  const submit = async (raw: string) => {
    if (locked) return;
    const url = extractUrl(raw) ?? raw.trim();
    if (!url) {
      setError('영상 링크를 붙여넣어 주세요.');
      return;
    }
    if (!isSupportedUrl(url)) {
      setError('유튜브, 인스타그램, 틱톡 링크만 지원해요.');
      return;
    }
    setError(null);
    setHint(null);
    setValue(url);
    if (await onSubmit(url)) setValue('');
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    void submit(value);
  };

  const paste = async () => {
    setError(null);
    try {
      const text = await navigator.clipboard.readText();
      if (!text.trim()) {
        setHint('클립보드가 비어 있어요. 영상 링크를 먼저 복사해 주세요.');
        return;
      }
      setValue(text);
      if (extractUrl(text)) void submit(text);
    } catch {
      // 권한 거부(사이트 설정에서 클립보드 차단) 또는 사용자가 권한 팝업을 닫은 경우
      setHint('클립보드 권한이 없어 자동으로 붙여넣지 못했어요. 입력창을 길게 누르거나 ⌘V / Ctrl+V 로 붙여넣어 주세요.');
      inputRef.current?.focus();
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-2" noValidate aria-busy={loading}>
      <label htmlFor="video-url" className="sr-only">
        영상 링크
      </label>
      <div
        className={`flex items-center gap-2 rounded-2xl border bg-white p-1.5 pl-3 shadow-sm transition ${
          loading
            ? 'border-brand-300 ring-4 ring-brand-50'
            : 'border-slate-200 focus-within:border-brand-500 focus-within:ring-4 focus-within:ring-brand-100'
        }`}
      >
        <Link2 size={18} className="shrink-0 text-slate-400" aria-hidden />
        <input
          ref={inputRef}
          id="video-url"
          type="url"
          inputMode="url"
          autoComplete="off"
          enterKeyHint="go"
          placeholder="유튜브 · 인스타 · 틱톡 링크 붙여넣기"
          value={value}
          onChange={(e) => {
            setValue(e.target.value);
            setError(null);
            setHint(null);
          }}
          readOnly={loading}
          disabled={disabled}
          className="min-w-0 flex-1 bg-transparent py-2 text-[15px] text-slate-900 placeholder:text-slate-400 read-only:text-slate-500 focus:outline-none disabled:opacity-50"
        />
        {!loading && value && (
          <button
            type="button"
            onClick={() => setValue('')}
            className="rounded-full p-1.5 text-slate-400 hover:bg-slate-100"
            aria-label="입력 지우기"
          >
            <X size={16} />
          </button>
        )}
        {!loading && !value && canReadClipboard && (
          <button
            type="button"
            onClick={paste}
            disabled={disabled}
            className="inline-flex shrink-0 items-center gap-1 rounded-xl px-2.5 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 disabled:opacity-50"
          >
            <ClipboardPaste size={16} aria-hidden />
            붙여넣기
          </button>
        )}
        <button
          type="submit"
          disabled={locked || !value.trim()}
          className="inline-flex shrink-0 items-center gap-1 rounded-xl bg-brand-600 px-4 py-2.5 text-sm font-bold text-white shadow-sm transition active:scale-95 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          {loading ? (
            <>
              <LoaderCircle size={16} className="animate-spin" aria-hidden />
              분석 중
            </>
          ) : (
            <>
              분석
              <ArrowRight size={16} aria-hidden />
            </>
          )}
        </button>
      </div>
      {error && (
        <p role="alert" className="px-1 text-sm text-red-600">
          {error}
        </p>
      )}
      {hint && !error && (
        <p role="status" className="px-1 text-sm text-slate-500">
          {hint}
        </p>
      )}
    </form>
  );
}
