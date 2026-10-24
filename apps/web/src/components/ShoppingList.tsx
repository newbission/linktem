'use client';

import { Lock, Sparkles, Trash2 } from 'lucide-react';

import type { FeedbackType, RelatedVideo } from '@linktem/types';

import { groupEntries, type FilterTab, type ListEntry } from '@/lib/grouping';
import type { ReportType } from '@/lib/reports';

import { ItemCard } from './ItemCard';

interface Props {
  entries: ListEntry[];
  tab: FilterTab;
  imageMap: Record<string, string>;
  related: Record<string, RelatedVideo[]>;
  feedback: Record<string, FeedbackType[]>;
  numbers: Record<string, number>;
  online: boolean;
  onToggle: (itemId: string) => void;
  onReport: (itemId: string, type: ReportType, cancel: boolean) => void;
  onOpenRelated: (url: string) => void;
  onOpenImage: (itemId: string) => void;
  onRemoveVideo: (videoId: string) => void;
}

const EMPTY_REPORTS: FeedbackType[] = [];

/** '내 분석 영상'에서 영상을 누르면 영상별 보기의 해당 묶음으로 스크롤 */
export function videoGroupId(videoId: string): string {
  return `video-group-${videoId}`;
}

export function ShoppingList({
  entries,
  tab,
  imageMap,
  related,
  feedback,
  numbers,
  online,
  onToggle,
  onReport,
  onOpenRelated,
  onOpenImage,
  onRemoveVideo,
}: Props) {
  const groups = groupEntries(entries, tab);

  return (
    <div className="space-y-6">
      {groups.map((group) => {
        const done = group.entries.filter((e) => e.item.is_checked).length;
        return (
          <section
            key={group.key}
            id={group.video ? videoGroupId(group.video.video_id) : undefined}
            aria-label={group.title}
            className="scroll-mt-20"
          >
            {tab !== 'all' && (
              <header className="mb-2 flex items-end justify-between gap-2 px-1">
                <div className="min-w-0">
                  <h2 className="truncate text-base font-extrabold text-slate-900">{group.title}</h2>
                  {group.video && (
                    <p className="mt-0.5 flex items-center gap-1.5 text-xs text-slate-500">
                      {group.subtitle && <span className="truncate">{group.subtitle}</span>}
                      {group.video.is_locked ? (
                        <span className="inline-flex shrink-0 items-center gap-0.5 rounded-full bg-brand-50 px-1.5 py-0.5 text-[10px] font-bold text-brand-700">
                          <Lock size={9} aria-hidden /> AI 검증 완료
                        </span>
                      ) : (
                        <span
                          className="inline-flex shrink-0 items-center gap-0.5 rounded-full bg-violet-50 px-1.5 py-0.5 text-[10px] font-bold text-violet-700"
                          title="여러 사람이 분석할수록 AI가 결과를 교차 검증해 정확해져요"
                        >
                          <Sparkles size={9} aria-hidden /> AI 검증 {group.video.analysis_count}/5
                        </span>
                      )}
                    </p>
                  )}
                </div>
                <div className="flex shrink-0 items-center gap-1">
                  <span className="text-xs font-semibold text-slate-500">
                    {done}/{group.entries.length}
                  </span>
                  {group.video && (
                    <button
                      type="button"
                      onClick={() => onRemoveVideo(group.video!.video_id)}
                      className="rounded-full p-1.5 text-slate-400 hover:bg-slate-100 hover:text-red-500"
                      aria-label={`${group.title} 영상을 리스트에서 삭제`}
                    >
                      <Trash2 size={15} />
                    </button>
                  )}
                </div>
              </header>
            )}
            <ul className="space-y-2.5">
              {group.entries.map(({ item, video }) => (
                <ItemCard
                  key={item.id}
                  item={item}
                  video={video}
                  imageSrc={imageMap[item.image_url]}
                  related={related[item.id]}
                  number={numbers[item.id]}
                  reports={feedback[item.id] ?? EMPTY_REPORTS}
                  online={online}
                  showVideoTitle={tab !== 'video'}
                  onToggle={onToggle}
                  onReport={onReport}
                  onOpenRelated={onOpenRelated}
                  onOpenImage={onOpenImage}
                />
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
