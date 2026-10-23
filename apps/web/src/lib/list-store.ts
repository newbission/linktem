import type { AnalysisJob, FeedbackType, VideoAnalysisResponse } from '@linktem/types';

/** 브라우저에 보관하는 장보기 리스트 (텍스트 데이터만 — 이미지는 IndexedDB) */
export interface StoredList {
  version: 1;
  /** 최근에 추가한 영상이 앞 */
  videos: VideoAnalysisResponse[];
  /** ShoppingItem.id → 체크 여부 */
  checked: Record<string, boolean>;
  /** ShoppingItem.id → 보낸 피드백 */
  feedback: Record<string, FeedbackType>;
  /** 분석 중이거나 실패한 작업 (완료되면 videos 로 옮기고 여기서 뺀다). 최근 작업이 앞 */
  jobs: AnalysisJob[];
  /** video_id → 리스트에 추가한 시각 (ms) — '분석한 영상' 목록 표시용 */
  addedAt: Record<string, number>;
  updatedAt: number;
}

const STORAGE_KEY = 'linktem:list:v1';

export const EMPTY_LIST: StoredList = {
  version: 1,
  videos: [],
  checked: {},
  feedback: {},
  jobs: [],
  addedAt: {},
  updatedAt: 0,
};

/** 이전 버전 저장본(jobs/addedAt 없음)이나 오프라인 스냅샷도 현재 형태로 맞춘다 */
export function normalizeList(raw: Partial<StoredList>): StoredList {
  return {
    ...EMPTY_LIST,
    ...raw,
    jobs: Array.isArray(raw.jobs) ? raw.jobs : [],
    addedAt: raw.addedAt && typeof raw.addedAt === 'object' ? raw.addedAt : {},
  };
}

export function loadList(): StoredList | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as StoredList;
    if (parsed.version !== 1 || !Array.isArray(parsed.videos)) return null;
    return normalizeList(parsed);
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
