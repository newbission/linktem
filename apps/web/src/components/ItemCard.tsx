'use client';

import {
  Check,
  ChevronDown,
  Clapperboard,
  Flag,
  ImageOff,
  LoaderCircle,
  MessageSquareQuote,
  Play,
  Send,
  TriangleAlert,
  X,
  ZoomIn,
} from 'lucide-react';
import { useState, type ReactNode } from 'react';

import type { FeedbackType, RelatedVideo, ShoppingItem, VideoAnalysisResponse } from '@linktem/types';

import { formatTimestamp, retailerStyle, timestampUrl } from '@/lib/format';
import { MAX_REPORT_COMMENT, REPORT_LABELS, REPORT_OPTIONS, type ReportType, type SendReports } from '@/lib/reports';

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
  onSendReports: SendReports;
  onOpenRelated: (url: string) => void;
  /** '이 영상의 제품은 달라요' — 잘못 연결된 다른 영상 떼기 */
  onUnlinkRelated?: (itemId: string, related: RelatedVideo) => void;
  /** 스틸컷을 누르면 확대 보기 */
  onOpenImage: (itemId: string) => void;
  /** 간단히 보기에서 펼친 상세: 행에 이미 있는 체크박스·번호·이름은 빼고 테두리 없이 렌더링 */
  embedded?: boolean;
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
  onSendReports,
  onOpenRelated,
  onUnlinkRelated,
  onOpenImage,
  embedded = false,
}: Props) {
  const [imageFailed, setImageFailed] = useState(false);
  const [reportOpen, setReportOpen] = useState(false);
  // 메뉴에서 고른 '보낼 제보' (보내기 전까지는 서버에 가지 않음)
  const [draft, setDraft] = useState<ReportType[]>([]);
  const [comment, setComment] = useState('');
  const [sending, setSending] = useState(false);
  const checked = item.is_checked;
  // 오프라인 저장본 → 썸네일 → (썸네일 도입 전 캡처) 확대용 이미지
  const src = imageSrc ?? (item.thumb_url || item.image_url);
  const canZoom = Boolean(src) && !imageFailed;
  const sceneUrl = timestampUrl(video.source_url, item.timestamp_sec);
  const myReports = reports.filter((t): t is ReportType => t !== 'SAME');
  const toAdd = draft.filter((t) => !myReports.includes(t));
  const toRemove = myReports.filter((t) => !draft.includes(t));
  const dirty = toAdd.length > 0 || toRemove.length > 0 || (comment.trim() !== '' && draft.length > 0);

  const openReport = () => {
    setDraft(myReports);
    setComment('');
    setReportOpen(true);
  };

  const toggleDraft = (type: ReportType) =>
    setDraft((prev) => {
      if (prev.includes(type)) return prev.filter((t) => t !== type);
      // '다른 제품' 과 '영상에 없음' 은 함께 고를 수 없음 (서버도 1인 1표)
      const exclusive: ReportType[] = ['WRONG_PRODUCT', 'NOT_IN_VIDEO'];
      const base = exclusive.includes(type) ? prev.filter((t) => !exclusive.includes(t)) : prev;
      return [...base, type];
    });

  const send = async () => {
    if (!dirty || sending) return;
    setSending(true);
    // 의견만 바꾼 경우에도 고른 유형에 의견이 붙도록 다시 보낸다
    const add = toAdd.length > 0 ? toAdd : comment.trim() ? draft : [];
    const ok = await onSendReports(item.id, add, toRemove, comment.trim() || undefined);
    setSending(false);
    if (ok) setReportOpen(false);
  };

  return (
    <Root
      embedded={embedded}
      className={
        embedded
          ? `rounded-xl bg-slate-50/70 p-2.5 ${checked ? 'opacity-60' : ''}`
          : `rounded-2xl bg-white p-3 shadow-sm ring-1 transition ${checked ? 'ring-slate-100 opacity-60' : 'ring-slate-200/80'}`
      }
    >
      <div className="flex gap-3">
        {/* 체크박스 (간단히 보기 상세에서는 행에 있으므로 생략) */}
        {!embedded && (
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
        )}

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
          {!embedded && (
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
          )}
          <p className={`truncate text-xs text-slate-500 ${embedded ? '' : 'mt-0.5'}`}>{item.name_en}</p>
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

      {/* 제보: 메뉴에서 고르고 → (의견) → 보내기 */}
      <div className="mt-3 flex flex-wrap items-center gap-1.5">
        <button
          type="button"
          onClick={() => (reportOpen ? setReportOpen(false) : openReport())}
          disabled={!online}
          aria-expanded={reportOpen}
          className="inline-flex items-center gap-1 rounded-xl bg-slate-100 px-3 py-2 text-xs font-semibold text-slate-600 transition active:scale-95 disabled:opacity-40"
        >
          <Flag size={13} aria-hidden />
          {myReports.length > 0 ? '제보 수정' : '제보하기'}
          <ChevronDown size={13} className={`transition ${reportOpen ? 'rotate-180' : ''}`} aria-hidden />
        </button>
        {!reportOpen &&
          myReports.map((type) => (
            <span
              key={type}
              className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2.5 py-1 text-[11px] font-semibold text-amber-800 ring-1 ring-amber-200"
              title="보낸 제보"
            >
              <Check size={11} aria-hidden />
              {REPORT_LABELS[type]}
            </span>
          ))}
      </div>
      {reportOpen && (
        <div className="mt-2 rounded-xl bg-slate-50 p-2" role="group" aria-label="제보 유형">
          <p className="px-1 pb-1.5 text-[11px] text-slate-500">
            해당하는 걸 모두 고른 뒤 <b>보내기</b>를 눌러 주세요. 보낸 제보를 빼면 취소돼요.
          </p>
          <div className="grid grid-cols-1 gap-1 min-[380px]:grid-cols-2">
            {REPORT_OPTIONS.map(({ type, label, hint }) => {
              const active = draft.includes(type);
              const sent = myReports.includes(type);
              return (
                <button
                  key={type}
                  type="button"
                  aria-pressed={active}
                  onClick={() => toggleDraft(type)}
                  className={`rounded-lg px-2.5 py-2 text-left text-xs font-semibold ring-1 transition active:scale-[0.98] ${
                    active
                      ? 'bg-amber-100 text-amber-900 ring-amber-300'
                      : 'bg-white text-slate-700 ring-slate-200 hover:bg-slate-100'
                  }`}
                >
                  <span className="flex items-center justify-between gap-1">
                    {label}
                    {sent && <span className="text-[10px] font-medium text-amber-700">보냄</span>}
                  </span>
                  <span className="mt-0.5 block text-[10px] font-normal leading-snug text-slate-500">{hint}</span>
                </button>
              );
            })}
          </div>
          <label className="mt-2 block">
            <span className="sr-only">제보 의견</span>
            <textarea
              value={comment}
              onChange={(e) => setComment(e.target.value.slice(0, MAX_REPORT_COMMENT))}
              rows={2}
              placeholder="자세히 알려주시면 더 빨리 고쳐요 (선택) — 예: 1kg 이 아니라 500g 이에요"
              className="w-full resize-none rounded-lg border border-slate-200 bg-white px-2.5 py-2 text-xs text-slate-800 placeholder:text-slate-400 focus:border-brand-500 focus:outline-none"
            />
          </label>
          <div className="mt-1.5 flex items-center justify-end gap-1.5">
            <button
              type="button"
              onClick={() => setReportOpen(false)}
              className="rounded-lg px-3 py-2 text-xs font-semibold text-slate-500 hover:bg-slate-100"
            >
              닫기
            </button>
            <button
              type="button"
              onClick={send}
              disabled={!dirty || sending || !online}
              className="inline-flex items-center gap-1 rounded-lg bg-slate-900 px-3.5 py-2 text-xs font-bold text-white transition active:scale-95 disabled:bg-slate-300"
            >
              {sending ? <LoaderCircle size={13} className="animate-spin" aria-hidden /> : <Send size={13} aria-hidden />}
              {toRemove.length > 0 && toAdd.length === 0 && !comment.trim() ? '취소 보내기' : '보내기'}
            </button>
          </div>
        </div>
      )}

      {/* 이 제품이 나온 다른 영상 */}
      {related && related.length > 0 && (
        <div className="mt-3 border-t border-slate-100 pt-2.5">
          <p className="mb-1.5 text-[11px] font-semibold text-slate-500">이 제품이 나온 다른 영상</p>
          <div className="-mx-1 flex gap-1.5 overflow-x-auto px-1 pb-1 [scrollbar-width:none]">
            {related.map((r) => {
              const label = r.creator_name || r.source_title;
              return (
                <span
                  key={r.other_item_id}
                  className="inline-flex max-w-[200px] shrink-0 items-center rounded-full bg-brand-50 text-xs font-medium text-brand-800 ring-1 ring-brand-100"
                >
                  <button
                    type="button"
                    onClick={() => onOpenRelated(r.source_url)}
                    disabled={!online}
                    title={r.source_title}
                    className={`inline-flex min-w-0 items-center gap-1 py-1 pl-2.5 disabled:opacity-50 ${onUnlinkRelated ? 'pr-1' : 'pr-2.5'}`}
                  >
                    <Play size={10} fill="currentColor" aria-hidden />
                    <span className="truncate">{label}</span>
                  </button>
                  {onUnlinkRelated && (
                    <button
                      type="button"
                      onClick={() => {
                        if (window.confirm(`'${label}' 영상의 제품이 이 제품과 다른가요?\n연결을 떼면 내 리스트에서 바로 사라져요.`)) {
                          onUnlinkRelated(item.id, r);
                        }
                      }}
                      disabled={!online}
                      className="mr-0.5 rounded-full p-1 text-brand-700/60 hover:bg-brand-100 hover:text-red-500 disabled:opacity-50"
                      aria-label={`'${label}' 영상과의 연결 떼기 (다른 제품이에요)`}
                      title="다른 제품이에요 — 연결 떼기"
                    >
                      <X size={11} aria-hidden />
                    </button>
                  )}
                </span>
              );
            })}
          </div>
        </div>
      )}
    </Root>
  );
}

function Root({ embedded, className, children }: { embedded: boolean; className: string; children: ReactNode }) {
  // 간단히 보기에서 펼친 카드는 이미 <li> 안에 있으므로 div 로
  return embedded ? <div className={className}>{children}</div> : <li className={className}>{children}</li>;
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
