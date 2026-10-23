import type { FeedbackType, VideoAnalysisResponse } from '@linktem/types';

/** 브라우저에 보관하는 장보기 리스트 (텍스트 데이터만 — 이미지는 IndexedDB) */
export interface StoredList {
  version: 1;
  /** 최근에 추가한 영상이 앞 */
  videos: VideoAnalysisResponse[];
  /** ShoppingItem.id → 체크 여부 */
  checked: Record<string, boolean>;
  /** ShoppingItem.id → 보낸 피드백 */
  feedback: Record<string, FeedbackType>;
  updatedAt: number;
}

const STORAGE_KEY = 'linktem:list:v1';

export const EMPTY_LIST: StoredList = { version: 1, videos: [], checked: {}, feedback: {}, updatedAt: 0 };

export function loadList(): StoredList | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as StoredList;
    if (parsed.version !== 1 || !Array.isArray(parsed.videos)) return null;
    return { ...EMPTY_LIST, ...parsed };
  } catch {
    return null;
  }
}

export function saveList(list: StoredList): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
  } catch {
    /* 사파리 사생활 보호 모드 / 용량 초과 — IndexedDB 오프라인 저장으로 보완 */
  }
}
