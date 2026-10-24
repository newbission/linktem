'use client';

import { ChevronLeft, ChevronRight, ImageOff, Play, X, ZoomIn, ZoomOut } from 'lucide-react';
import { useCallback, useEffect, useRef, useState, type MouseEvent, type TouchEvent } from 'react';

import type { ListEntry } from '@/lib/grouping';
import { formatTimestamp, retailerStyle, timestampUrl } from '@/lib/format';

import { ItemNotes } from './ItemCard';

const SWIPE_MIN_PX = 50;
const ZOOM_SCALE = 2.5;

interface Props {
  /** 확대 가능한 항목 (화면에 보이는 순서) */
  entries: ListEntry[];
  index: number;
  /** image_url → 오프라인 저장본 object URL */
  imageMap: Record<string, string>;
  online: boolean;
  onIndexChange: (index: number) => void;
  onClose: () => void;
}

/** 스틸컷 확대 보기: 확대용 이미지(짧은 변 720px) + 상품 정보·메모. 좌우 넘기기, 두 번 탭해 확대 */
export function ImageViewer({ entries, index, imageMap, online, onIndexChange, onClose }: Props) {
  const entry = entries[index];
  const [zoom, setZoom] = useState<{ x: number; y: number } | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [failed, setFailed] = useState(false);
  const closeRef = useRef<HTMLButtonElement>(null);
  const touchStart = useRef<{ x: number; y: number } | null>(null);
  const lastTap = useRef(0);

  const hasPrev = index > 0;
  const hasNext = index < entries.length - 1;
  const go = useCallback(
    (delta: number) => {
      const next = index + delta;
      if (next >= 0 && next < entries.length) onIndexChange(next);
    },
    [index, entries.length, onIndexChange],
  );

  // 항목이 바뀌면 확대·로딩 상태 초기화
  useEffect(() => {
    setZoom(null);
    setLoaded(false);
    setFailed(false);
  }, [index]);

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const previousFocus = document.activeElement as HTMLElement | null;
    closeRef.current?.focus();
    return () => {
      document.body.style.overflow = previousOverflow;
      previousFocus?.focus?.();
    };
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
      else if (e.key === 'ArrowLeft') go(-1);
      else if (e.key === 'ArrowRight') go(1);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [go, onClose]);

  if (!entry) return null;
  const { item, video } = entry;
  // 오프라인 저장본 → 확대용 → 썸네일
  const src = imageMap[item.image_url] ?? (item.image_url || item.thumb_url || '');
  const sceneUrl = timestampUrl(video.source_url, item.timestamp_sec);

  const toggleZoom = (clientX: number, clientY: number, rect: DOMRect) => {
    setZoom((current) =>
      current
        ? null
        : { x: ((clientX - rect.left) / rect.width) * 100, y: ((clientY - rect.top) / rect.height) * 100 },
    );
  };

  const onImageDoubleClick = (e: MouseEvent<HTMLImageElement>) => {
    toggleZoom(e.clientX, e.clientY, e.currentTarget.getBoundingClientRect());
  };

  const onTouchStart = (e: TouchEvent<HTMLDivElement>) => {
    if (e.touches.length !== 1) return;
    touchStart.current = { x: e.touches[0].clientX, y: e.touches[0].clientY };
  };

  const onTouchEnd = (e: TouchEvent<HTMLDivElement>) => {
    const start = touchStart.current;
    touchStart.current = null;
    if (!start || e.changedTouches.length !== 1) return;
    const touch = e.changedTouches[0];
    const dx = touch.clientX - start.x;
    const dy = touch.clientY - start.y;
    // 확대 중이 아닐 때 가로 스와이프 → 이전/다음
    if (!zoom && Math.abs(dx) > SWIPE_MIN_PX && Math.abs(dx) > Math.abs(dy) * 1.5) {
      go(dx < 0 ? 1 : -1);
      return;
    }
    // 두 번 탭 → 확대/축소
    if (Math.abs(dx) < 10 && Math.abs(dy) < 10) {
      const now = Date.now();
      const target = e.target as HTMLElement;
      if (now - lastTap.current < 300 && target.tagName === 'IMG') {
        e.preventDefault();
        toggleZoom(touch.clientX, touch.clientY, target.getBoundingClientRect());
        lastTap.current = 0;
      } else {
        lastTap.current = now;
      }
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={`${item.name_ko} 스틸컷`}
      className="fixed inset-0 z-50 flex flex-col bg-black/95 text-white"
    >
      <div className="flex items-center justify-between gap-2 px-3 pb-2 pt-[max(0.75rem,env(safe-area-inset-top))]">
        <span className="text-sm font-semibold text-white/70">
          {index + 1} / {entries.length}
        </span>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => setZoom((z) => (z ? null : { x: 50, y: 50 }))}
            disabled={!src || failed}
            className="rounded-full p-2 text-white/80 hover:bg-white/10 disabled:opacity-30"
            aria-label={zoom ? '축소' : '확대'}
          >
            {zoom ? <ZoomOut size={20} /> : <ZoomIn size={20} />}
          </button>
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            className="rounded-full p-2 text-white/80 hover:bg-white/10"
            aria-label="닫기"
          >
            <X size={22} />
          </button>
        </div>
      </div>

      <div
        className="relative min-h-0 flex-1 overflow-hidden"
        onTouchStart={onTouchStart}
        onTouchEnd={onTouchEnd}
        onClick={(e) => {
          // 이미지 바깥(배경)을 누르면 닫기
          if (e.target === e.currentTarget && !zoom) onClose();
        }}
      >
        {src && !failed ? (
          <img
            key={src}
            src={src}
            alt={`${item.name_ko} 영상 스틸컷`}
            decoding="async"
            onLoad={() => setLoaded(true)}
            onError={() => setFailed(true)}
            onDoubleClick={onImageDoubleClick}
            draggable={false}
            style={zoom ? { transform: `scale(${ZOOM_SCALE})`, transformOrigin: `${zoom.x}% ${zoom.y}%` } : undefined}
            className={`absolute inset-0 m-auto max-h-full max-w-full select-none object-contain transition-[transform,opacity] duration-200 ${
              loaded ? 'opacity-100' : 'opacity-0'
            } ${zoom ? 'cursor-zoom-out' : 'cursor-zoom-in'}`}
          />
        ) : (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-white/50">
            <ImageOff size={28} aria-hidden />
            <p className="text-sm">{online ? '이미지를 불러오지 못했어요' : '오프라인이라 이미지를 볼 수 없어요'}</p>
          </div>
        )}
        {src && !failed && !loaded && (
          <div className="absolute inset-0 m-auto h-8 w-8 animate-spin rounded-full border-2 border-white/20 border-t-white/80" />
        )}

        {hasPrev && (
          <button
            type="button"
            onClick={() => go(-1)}
            className="absolute left-2 top-1/2 -translate-y-1/2 rounded-full bg-black/50 p-2 text-white hover:bg-black/70"
            aria-label="이전 상품"
          >
            <ChevronLeft size={22} />
          </button>
        )}
        {hasNext && (
          <button
            type="button"
            onClick={() => go(1)}
            className="absolute right-2 top-1/2 -translate-y-1/2 rounded-full bg-black/50 p-2 text-white hover:bg-black/70"
            aria-label="다음 상품"
          >
            <ChevronRight size={22} />
          </button>
        )}
      </div>

      <div className="max-h-[38vh] overflow-y-auto rounded-t-3xl bg-white px-4 pb-[max(1rem,env(safe-area-inset-bottom))] pt-4 text-slate-900">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-base font-extrabold leading-snug">{item.name_ko}</p>
            <p className="mt-0.5 truncate text-xs text-slate-500">{item.name_en}</p>
          </div>
          <span
            className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-bold ring-1 ring-inset ${retailerStyle(item.retailer)}`}
          >
            {item.retailer}
          </span>
        </div>
        {item.edition_note && <p className="mt-1.5 text-sm font-medium text-brand-700">{item.edition_note}</p>}
        <ItemNotes reason={item.reason} caution={item.caution} large />
        <div className="mt-3 flex items-center justify-between gap-2 text-xs text-slate-500">
          <span className="truncate">{video.creator_name || video.source_title}</span>
          {sceneUrl && online && (
            <a
              href={sceneUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex shrink-0 items-center gap-1 rounded-full bg-slate-900 px-3 py-1.5 font-semibold text-white"
            >
              <Play size={11} fill="currentColor" aria-hidden />
              영상 {formatTimestamp(item.timestamp_sec)}에서 보기
            </a>
          )}
        </div>
      </div>
    </div>
  );
}
