import type { ShoppingItem, VideoAnalysisResponse } from '@linktem/types';

export type FilterTab = 'all' | 'retailer' | 'video';

export interface ListEntry {
  item: ShoppingItem;
  video: VideoAnalysisResponse;
}

export interface EntryGroup {
  key: string;
  title: string;
  subtitle?: string;
  video?: VideoAnalysisResponse;
  entries: ListEntry[];
}

export function toEntries(videos: VideoAnalysisResponse[], checked: Record<string, boolean>): ListEntry[] {
  return videos.flatMap((video) =>
    video.items.map((item) => ({ video, item: { ...item, is_checked: Boolean(checked[item.id]) } })),
  );
}

/** 체크한 항목은 아래로 (안정 정렬) */
function uncheckedFirst(entries: ListEntry[]): ListEntry[] {
  return [...entries].sort((a, b) => Number(a.item.is_checked) - Number(b.item.is_checked));
}

export function groupEntries(entries: ListEntry[], tab: FilterTab): EntryGroup[] {
  if (tab === 'all') {
    return [{ key: 'all', title: '전체', entries: uncheckedFirst(entries) }];
  }

  const groups = new Map<string, EntryGroup>();
  for (const entry of entries) {
    const key = tab === 'retailer' ? entry.item.retailer : entry.video.video_id;
    let group = groups.get(key);
    if (!group) {
      group =
        tab === 'retailer'
          ? { key, title: entry.item.retailer, entries: [] }
          : {
              key,
              title: entry.video.source_title || '제목 없는 영상',
              subtitle: entry.video.creator_name,
              video: entry.video,
              entries: [],
            };
      groups.set(key, group);
    }
    group.entries.push(entry);
  }

  const result = Array.from(groups.values()).map((g) => ({ ...g, entries: uncheckedFirst(g.entries) }));
  if (tab === 'retailer') {
    // 아이템이 많은 판매처부터, '기타/미상' 은 맨 뒤
    result.sort((a, b) => {
      if (a.key === '기타/미상') return 1;
      if (b.key === '기타/미상') return -1;
      return b.entries.length - a.entries.length;
    });
  }
  return result;
}
