import type { RelatedVideo } from '@linktem/types';

// 뗀 연결 기록이 끝없이 쌓이지 않도록 (오래된 것부터 버림)
export const MAX_UNLINKED = 500;

/** 아이템 쌍 키 — 어느 쪽에서 떼도 같은 연결 (서버 related_unlinks 와 같은 규칙) */
export function relatedPairKey(itemId: string, otherItemId: string): string {
  return itemId < otherItemId ? `${itemId}|${otherItemId}` : `${otherItemId}|${itemId}`;
}

/** 내가 뗀 연결을 뺀 '이 제품이 나온 다른 영상' */
export function visibleRelated(
  related: Record<string, RelatedVideo[]>,
  unlinked: string[],
): Record<string, RelatedVideo[]> {
  if (unlinked.length === 0) return related;
  const hidden = new Set(unlinked);
  const result: Record<string, RelatedVideo[]> = {};
  for (const [itemId, list] of Object.entries(related)) {
    const kept = list.filter((r) => !hidden.has(relatedPairKey(itemId, r.other_item_id)));
    if (kept.length) result[itemId] = kept;
  }
  return result;
}
