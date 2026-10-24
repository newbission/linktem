'use client';

import { Check, Clapperboard, ImageOff, MessageSquareQuote, Play, ThumbsDown, TriangleAlert, Undo2, ZoomIn } from 'lucide-react';
import { useState } from 'react';

import type { FeedbackType, RelatedVideo, ShoppingItem, VideoAnalysisResponse } from '@linktem/types';

import { formatTimestamp, retailerStyle, timestampUrl } from '@/lib/format';

interface Props {
  item: ShoppingItem;
  video: VideoAnalysisResponse;
  imageSrc?: string;
  related?: RelatedVideo[];
  feedback?: FeedbackType;
  online: boolean;
  showVideoTitle?: boolean;
  onToggle: (itemId: string) => void;
  onFeedback: (itemId: string, type: FeedbackType | null) => void;
  onOpenRelated: (url: string) => void;
  /** 스틸컷을 누르면 확대 보기 */
  onOpenImage: (itemId: string) => void;
}

export function ItemCard({
  item,
  video,
  imageSrc,
  related,
  feedback,
  online,
  showVideoTitle,
  onToggle,
  onFeedback,
  onOpenRelated,
  onOpenImage,
}: Props) {
  const [imageFailed, setImageFailed] = useState(false);
  const checked = item.is_checked;
  // 오프라인 저장본 → 썸네일 → (썸네일 도입 전 캡처) 확대용 이미지
  const src = imageSrc ?? (item.thumb_url || item.image_url);
  const canZoom = Boolean(src) && !imageFailed;
  const sceneUrl = timestampUrl(video.source_url, item.timestamp_sec);
  const markedDifferent = feedback === 'DIFFERENT';

  return (
    <li
      className={`rounded-2xl bg-white p-3 shadow-sm ring-1 transition ${
        checked ? 'ring-slate-100 opacity-60' : 'ring-slate-200/80'
      }`}
    >
      <div className="flex gap-3">
        {/* 체크박스 */}
        <button
          type="button"
          role="checkbox"
          aria-checked={checked}
          aria-label={`${item.name_ko} ${checked ? '체크 해제' : '장바구니에 담음으로 체크'}`}
          onClick={() => onToggle(item.id)}
          className={`mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border-2 transition active:scale-90 ${
            checked ? 'border-brand-600 bg-brand-600 text-white' : 'border-slate-300 bg-white text-transparent'
          }`}
        >
          <Check size={16} strokeWidth={3.5} aria-hidden />
        </button>

        {/* 스틸컷 */}
        <div className="relative h-[84px] w-[84px] shrink-0 overflow-hidden rounded-xl bg-slate-100">
          {canZoom ? (
            <button
              type="button"
              onClick={() => onOpenImage(item.id)}
              className="group block h-full w-full"
              aria-label={`${item.name_ko} 스틸컷 크게 보기`}
            >
              <img
                src={src}
                alt={`${item.name_ko} 영상 스틸컷`}
                loading="lazy"
                decoding="async"
                onError={() => setImageFailed(true)}
                className={`h-full w-full object-cover ${checked ? 'grayscale' : ''}`}
              />
              <span className="absolute left-1 top-1 rounded-md bg-black/50 p-0.5 text-white opacity-80 group-active:opacity-100">
                <ZoomIn size={11} aria-hidden />
              </span>
            </button>
          ) : (
            <div className="flex h-full w-full flex-col items-center justify-center gap-1 text-slate-400">
              <ImageOff size={20} aria-hidden />
              <span className="text-[10px]">{!item.image_url ? '준비 중' : online ? '이미지 없음' : '오프라인'}</span>
            </div>
          )}
          {sceneUrl && online ? (
            <a
              href={sceneUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="absolute bottom-1 right-1 inline-flex items-center gap-0.5 rounded-md bg-black/70 px-1.5 py-0.5 text-[10px] font-semibold text-white"
              aria-label={`영상 ${formatTimestamp(item.timestamp_sec)} 지점에서 보기`}
            >
              <Play size={9} fill="currentColor" aria-hidden />
              {formatTimestamp(item.timestamp_sec)}
            </a>
          ) : (
            <span className="absolute bottom-1 right-1 rounded-md bg-black/70 px-1.5 py-0.5 text-[10px] font-semibold text-white">
              {formatTimestamp(item.timestamp_sec)}
            </span>
          )}
        </div>

        {/* 상품 정보 */}
        <div className="min-w-0 flex-1">
          <p className={`text-[15px] font-bold leading-snug text-slate-900 ${checked ? 'line-through' : ''}`}>
            {item.name_ko}
          </p>
          <p className="mt-0.5 truncate text-xs text-slate-500">{item.name_en}</p>
          {item.edition_note && <p className="mt-1 text-xs font-medium text-brand-700">{item.edition_note}</p>}
          <ItemNotes reason={item.reason} caution={item.caution} />
          <div className="mt-1.5 flex flex-wrap items-center gap-1">
            <span
              className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-bold ring-1 ring-inset ${retailerStyle(item.retailer)}`}
            >
              {item.retailer}
            </span>
            <span className="inline-flex items-center rounded-full bg-slate-50 px-2 py-0.5 text-[11px] text-slate-600 ring-1 ring-inset ring-slate-200">
              {item.category}
            </span>
          </div>
          {showVideoTitle && (
            <p className="mt-1 flex items-center gap-1 truncate text-[11px] text-slate-400">
              <Clapperboard size={11} aria-hidden />
              {video.creator_name || video.source_title}
            </p>
          )}
        </div>
      </div>

      {/* 액션 */}
      <div className="mt-3 flex items-center gap-2">
        {markedDifferent ? (
          <button
            type="button"
            onClick={() => onFeedback(item.id, null)}
            className="inline-flex items-center gap-1 rounded-xl bg-amber-50 px-3 py-2.5 text-xs font-semibold text-amber-800 ring-1 ring-amber-200"
          >
            <Undo2 size={14} aria-hidden />
            되돌리기
          </button>
        ) : (
          <button
            type="button"
            onClick={() => onFeedback(item.id, 'DIFFERENT')}
            disabled={!online}
            className="inline-flex items-center gap-1 rounded-xl bg-slate-100 px-3 py-2.5 text-xs font-semibold text-slate-600 transition active:scale-95 disabled:opacity-40"
          >
            <ThumbsDown size={14} aria-hidden />
            다른 제품이에요
          </button>
        )}
      </div>
      {markedDifferent && (
        <p className="mt-2 text-xs text-amber-700">알려주셔서 고마워요! 다음 분석부터 반영돼요.</p>
      )}

      {/* 이 제품이 나온 다른 영상 */}
      {related && related.length > 0 && (
        <div className="mt-3 border-t border-slate-100 pt-2.5">
          <p className="mb-1.5 text-[11px] font-semibold text-slate-500">이 제품이 나온 다른 영상</p>
          <div className="-mx-1 flex gap-1.5 overflow-x-auto px-1 pb-1 [scrollbar-width:none]">
            {related.map((r) => (
              <button
                key={r.video_id}
                type="button"
                onClick={() => onOpenRelated(r.source_url)}
                disabled={!online}
                title={r.source_title}
                className="inline-flex max-w-[180px] shrink-0 items-center gap-1 rounded-full bg-brand-50 px-2.5 py-1 text-xs font-medium text-brand-800 ring-1 ring-brand-100 disabled:opacity-50"
              >
                <Play size={10} fill="currentColor" aria-hidden />
                <span className="truncate">{r.creator_name || r.source_title}</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </li>
  );
}

/** 영상에서 말한 추천 이유 / 헷갈리지 말아야 할 점 (AI 요약) */
export function ItemNotes({ reason, caution, large = false }: { reason?: string | null; caution?: string | null; large?: boolean }) {
  if (!reason && !caution) return null;
  const text = large ? 'text-sm' : 'text-xs';
  return (
    <div className="mt-1.5 space-y-1">
      {caution && (
        <p className={`flex items-start gap-1 rounded-lg bg-amber-50 px-2 py-1 ${text} font-medium leading-snug text-amber-900`}>
          <TriangleAlert size={large ? 14 : 12} className="mt-0.5 shrink-0 text-amber-600" aria-hidden />
          <span>
            <span className="sr-only">헷갈리지 마세요: </span>
            {caution}
          </span>
        </p>
      )}
      {reason && (
        <p className={`flex items-start gap-1 ${text} leading-snug text-slate-600`}>
          <MessageSquareQuote size={large ? 14 : 12} className="mt-0.5 shrink-0 text-slate-400" aria-hidden />
          <span>
            <span className="sr-only">추천 이유: </span>
            {reason}
          </span>
        </p>
      )}
    </div>
  );
}
