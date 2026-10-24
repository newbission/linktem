'use client';

import {
  Check,
  ChevronDown,
  Clapperboard,
  Flag,
  ImageOff,
  MessageSquareQuote,
  Play,
  TriangleAlert,
  X,
  ZoomIn,
} from 'lucide-react';
import { useState } from 'react';

import type { FeedbackType, RelatedVideo, ShoppingItem, VideoAnalysisResponse } from '@linktem/types';

import { formatTimestamp, retailerStyle, timestampUrl } from '@/lib/format';
import { REPORT_LABELS, REPORT_OPTIONS, type ReportType } from '@/lib/reports';

interface Props {
  item: ShoppingItem;
  video: VideoAnalysisResponse;
  imageSrc?: string;
  related?: RelatedVideo[];
  /** 체크리스트 번호 (먼저 담은 순서, 체크해도 바뀌지 않음) */
  number?: number;
  /** 내가 보낸 제보 유형 */
  reports: FeedbackType[];
  online: boolean;
  showVideoTitle?: boolean;
  onToggle: (itemId: string) => void;
  onReport: (itemId: string, type: ReportType, cancel: boolean) => void;
  onOpenRelated: (url: string) => void;
  /** 스틸컷을 누르면 확대 보기 */
  onOpenImage: (itemId: string) => void;
}

export function ItemCard({
  item,
  video,
  imageSrc,
  related,
  number,
  reports,
  online,
  showVideoTitle,
  onToggle,
  onReport,
  onOpenRelated,
  onOpenImage,
}: Props) {
  const [imageFailed, setImageFailed] = useState(false);
  const [reportOpen, setReportOpen] = useState(false);
  const checked = item.is_checked;
  // 오프라인 저장본 → 썸네일 → (썸네일 도입 전 캡처) 확대용 이미지
  const src = imageSrc ?? (item.thumb_url || item.image_url);
  const canZoom = Boolean(src) && !imageFailed;
  const sceneUrl = timestampUrl(video.source_url, item.timestamp_sec);
  const myReports = reports.filter((t): t is ReportType => t !== 'SAME');

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
            {number !== undefined && (
              <span
                className={`mr-1.5 inline-flex h-5 min-w-5 -translate-y-px items-center justify-center rounded-md px-1 align-middle text-[11px] font-extrabold no-underline ${
                  checked ? 'bg-slate-200 text-slate-500' : 'bg-slate-900 text-white'
                }`}
                aria-label={`${number}번`}
              >
                {number}
              </span>
            )}
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

      {/* 제보 */}
      <div className="mt-3 flex flex-wrap items-center gap-1.5">
        <button
          type="button"
          onClick={() => setReportOpen((v) => !v)}
          disabled={!online}
          aria-expanded={reportOpen}
          className="inline-flex items-center gap-1 rounded-xl bg-slate-100 px-3 py-2 text-xs font-semibold text-slate-600 transition active:scale-95 disabled:opacity-40"
        >
          <Flag size={13} aria-hidden />
          제보하기
          <ChevronDown size={13} className={`transition ${reportOpen ? 'rotate-180' : ''}`} aria-hidden />
        </button>
        {myReports.map((type) => (
          <span
            key={type}
            className="inline-flex items-center gap-1 rounded-full bg-amber-50 py-1 pl-2.5 pr-1 text-[11px] font-semibold text-amber-800 ring-1 ring-amber-200"
          >
            {REPORT_LABELS[type]}
            <button
              type="button"
              onClick={() => onReport(item.id, type, true)}
              disabled={!online}
              className="rounded-full p-0.5 text-amber-500 hover:bg-amber-100 disabled:opacity-40"
              aria-label={`'${REPORT_LABELS[type]}' 제보 취소`}
            >
              <X size={12} />
            </button>
          </span>
        ))}
      </div>
      {reportOpen && (
        <div className="mt-2 rounded-xl bg-slate-50 p-2" role="group" aria-label="제보 유형">
          <p className="px-1 pb-1.5 text-[11px] text-slate-500">해당하는 걸 모두 눌러 주세요. 다시 누르면 취소돼요.</p>
          <div className="grid grid-cols-1 gap-1 min-[380px]:grid-cols-2">
            {REPORT_OPTIONS.map(({ type, label, hint }) => {
              const active = myReports.includes(type);
              return (
                <button
                  key={type}
                  type="button"
                  aria-pressed={active}
                  onClick={() => onReport(item.id, type, active)}
                  title={hint}
                  className={`rounded-lg px-2.5 py-2 text-left text-xs font-semibold ring-1 transition active:scale-[0.98] ${
                    active
                      ? 'bg-amber-100 text-amber-900 ring-amber-300'
                      : 'bg-white text-slate-700 ring-slate-200 hover:bg-slate-100'
                  }`}
                >
                  {label}
                  <span className="mt-0.5 block text-[10px] font-normal leading-snug text-slate-500">{hint}</span>
                </button>
              );
            })}
          </div>
        </div>
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
