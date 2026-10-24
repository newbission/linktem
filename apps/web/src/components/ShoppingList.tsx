'use client';

import { ChevronDown, Lock, Sparkles, Trash2 } from 'lucide-react';

import type { FeedbackType, RelatedVideo } from '@linktem/types';

import { groupEntries, type FilterTab, type ListEntry } from '@/lib/grouping';
import type { SendReports } from '@/lib/reports';
import { groupKey } from '@/lib/ui-prefs';

import { ItemCard } from './ItemCard';
import { ItemRow } from './ItemRow';

interface Props {
  entries: ListEntry[];
  tab: FilterTab;
  imageMap: Record<string, string>;
  related: Record<string, RelatedVideo[]>;
  feedback: Record<string, FeedbackType[]>;
  numbers: Record<string, number>;
  online: boolean;
  /** 간단히 보기 (한 줄 행) */
  compact: boolean;
  /** 접어 둔 묶음 키 */
  collapsed: string[];
  onToggleCollapsed: (key: string) => void;
  onToggle: (itemId: string) => void;
  onSendReports: SendReports;
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
  compact,
  collapsed,
  onToggleCollapsed,
  onToggle,
  onSendReports,
  onOpenRelated,
  onOpenImage,
  onRemoveVideo,
}: Props) {
  const groups = groupEntries(entries, tab);

  return (
    <div className={compact ? 'space-y-4' : 'space-y-6'}>
      {groups.map((group) => {
        const done = group.entries.filter((e) => e.item.is_checked).length;
        const key = tab === 'all' ? null : groupKey(tab, group.key);
        const isCollapsed = key !== null && collapsed.includes(key);
        const listId = `group-list-${tab}-${group.key}`;
        return (
          <section
            key={group.key}
            id={group.video ? videoGroupId(group.video.video_id) : undefined}
            aria-label={group.title}
            className="scroll-mt-20"
          >
            {key !== null && (
              <header className="mb-2 flex items-center justify-between gap-2 px-1">
                <button
                  type="button"
                  onClick={() => onToggleCollapsed(key)}
                  aria-expanded={!isCollapsed}
                  aria-controls={listId}
                  className="flex min-w-0 flex-1 items-start gap-1.5 rounded-lg py-0.5 text-left"
                >
                  <ChevronDown
                    size={18}
                    className={`mt-0.5 shrink-0 text-slate-400 transition ${isCollapsed ? '-rotate-90' : ''}`}
                    aria-hidden
                  />
                  <span className="min-w-0">
                    <span className="block truncate text-base font-extrabold text-slate-900">{group.title}</span>
                    {group.video && (
                      <span className="mt-0.5 flex items-center gap-1.5 text-xs text-slate-500">
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
                      </span>
                    )}
                  </span>
                </button>
                <div className="flex shrink-0 items-center gap-1">
                  <span className={`text-xs font-semibold ${done === group.entries.length ? 'text-brand-700' : 'text-slate-500'}`}>
                    {done}/{group.entries.length}
                  </span>
                  {group.video && (
                    <button
                      type="button"
                      onClick={() => {
                        if (window.confirm(`'${group.title}' 영상과 상품을 리스트에서 뺄까요?`)) {
                          onRemoveVideo(group.video!.video_id);
                        }
                      }}
                      className="rounded-full p-1.5 text-slate-400 hover:bg-slate-100 hover:text-red-500"
                      aria-label={`${group.title} 영상을 리스트에서 삭제`}
                    >
                      <Trash2 size={15} />
                    </button>
                  )}
                </div>
              </header>
            )}
            {!isCollapsed && (
              <ul id={listId} className={compact ? 'divide-y divide-slate-100 rounded-2xl bg-white shadow-sm ring-1 ring-slate-200/80' : 'space-y-2.5'}>
                {group.entries.map(({ item, video }) => {
                  const shared = {
                    item,
                    video,
                    number: numbers[item.id],
                    reports: feedback[item.id] ?? EMPTY_REPORTS,
                    online,
                    showVideoTitle: tab !== 'video',
                    onToggle,
                  };
                  return compact ? (
                    <ItemRow
                      key={item.id}
                      {...shared}
                      showRetailer={tab !== 'retailer'}
                      renderDetail={(onCollapse) => (
                        <ItemCard
                          {...shared}
                          imageSrc={imageMap[item.image_url]}
                          related={related[item.id]}
                          onSendReports={onSendReports}
                          onOpenRelated={onOpenRelated}
                          onOpenImage={onOpenImage}
                          onCollapse={onCollapse}
                          embedded
                        />
                      )}
                    />
                  ) : (
                    <ItemCard
                      key={item.id}
                      {...shared}
                      imageSrc={imageMap[item.image_url]}
                      related={related[item.id]}
                      onSendReports={onSendReports}
                      onOpenRelated={onOpenRelated}
                      onOpenImage={onOpenImage}
                    />
                  );
                })}
              </ul>
            )}
          </section>
        );
      })}
    </div>
  );
}
