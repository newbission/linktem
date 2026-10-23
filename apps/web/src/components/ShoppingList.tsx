'use client';

import { Lock, Sparkles, Trash2 } from 'lucide-react';

import type { FeedbackType, RelatedVideo } from '@linktem/types';

import { groupEntries, type FilterTab, type ListEntry } from '@/lib/grouping';

import { ItemCard } from './ItemCard';

interface Props {
  entries: ListEntry[];
  tab: FilterTab;
  imageMap: Record<string, string>;
  related: Record<string, RelatedVideo[]>;
  feedback: Record<string, FeedbackType>;
  online: boolean;
  onToggle: (itemId: string) => void;
  onFeedback: (itemId: string, type: FeedbackType | null) => void;
  onOpenRelated: (url: string) => void;
  onRemoveVideo: (videoId: string) => void;
}

export function ShoppingList({
  entries,
  tab,
  imageMap,
  related,
  feedback,
  online,
  onToggle,
  onFeedback,
  onOpenRelated,
  onRemoveVideo,
}: Props) {
  const groups = groupEntries(entries, tab);

  return (
    <div className="space-y-6">
      {groups.map((group) => {
        const done = group.entries.filter((e) => e.item.is_checked).length;
        return (
          <section key={group.key} aria-label={group.title}>
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
                  feedback={feedback[item.id]}
                  online={online}
                  showVideoTitle={tab !== 'video'}
                  onToggle={onToggle}
                  onFeedback={onFeedback}
                  onOpenRelated={onOpenRelated}
                />
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
