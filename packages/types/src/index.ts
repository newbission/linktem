/**
 * @linktem/types — Linktem 프론트엔드(apps/web) ↔ 백엔드(apps/api) 공통 데이터 계약.
 *
 * 이 파일이 계약의 원본(Source of Truth)이다.
 * Python 미러: apps/api/app/schemas.py  (apps/api/tests/test_contract.py 가 일치 여부를 검증)
 * 필드명은 양쪽 모두 snake_case 를 사용한다.
 */

// ---------------------------------------------------------------------------
// 분석 요청 / 응답
// ---------------------------------------------------------------------------

/** POST /api/analyze 요청 본문 */
export interface VideoAnalysisRequest {
  /** 유튜브 / 인스타그램 / 틱톡 영상 또는 게시글 URL */
  url: string;
}

/** 장보기 체크리스트의 아이템 한 개 (= video_items 행) */
export interface ShoppingItem {
  /** video_items.id (UUID) */
  id: string;
  /** 한글 상품명 */
  name_ko: string;
  /** 영문 상품명 (영상 간 동일 상품 매칭 키로도 사용) */
  name_en: string;
  /** 카테고리 (예: "가공식품", "생활용품") — SHOPPING_CATEGORIES 참고 */
  category: string;
  /** 영상 내 상품이 가장 잘 보이는 시점 (초) */
  timestamp_sec: number;
  /** 해당 시점 스틸컷 WebP 공개 URL — 확대 보기용 (짧은 변 720px). 이미지 만료/복원 중이면 빈 문자열 */
  image_url: string;
  /** 리스트 카드용 썸네일 (짧은 변 256px). 없거나 빈 문자열이면 image_url 사용 */
  thumb_url?: string;
  /** 판매처 (예: "이마트", "코스트코", "다이소") */
  retailer: string;
  /** 체크 여부 — 서버는 항상 false 로 내려주고, 클라이언트가 로컬 상태로 관리 */
  is_checked: boolean;
  /** 한정판 / 용량 / 맛 등 에디션 메모 */
  edition_note?: string;
  /** 영상에서 말한 추천 이유·특징 (AI 요약) */
  reason?: string;
  /** 비슷한 제품과 헷갈리지 않도록 확인할 점 (AI 요약) */
  caution?: string;
}

/** POST /api/analyze 응답 본문 */
export interface VideoAnalysisResponse {
  /** videos.id (UUID) */
  video_id: string;
  /** 영상 제목 */
  source_title: string;
  /** 업로더 / 채널명 */
  creator_name: string;
  /** 앙상블 누적 회차 (1~5) */
  analysis_count: number;
  /** 5회차 도달로 데이터가 동결되었는지 여부 (이후 AI 재분석 없음) */
  is_locked: boolean;
  /** 체크리스트 아이템 */
  items: ShoppingItem[];
  /**
   * 정규화된 원본 영상 URL — "영상에서 보기"(타임스탬프 점프) 및 관련 영상 재분석에 사용.
   * (명세 대비 추가된 optional 필드, ADR-007)
   */
  source_url?: string;
  /** 영상 전체 내용 한두 문장 요약 (AI) */
  summary?: string;
  /** 영상 대표 이미지 (없으면 첫 상품 썸네일로 대체) */
  thumb_url?: string;
}

// ---------------------------------------------------------------------------
// 백그라운드 분석 작업
// ---------------------------------------------------------------------------

/** queued: 순서 대기 / running: 진행 중 / done: 완료 / failed: 실패 */
export type AnalysisJobStatus = 'queued' | 'running' | 'done' | 'failed';

/** 진행 단계 — 화면의 단계 표시용 */
export type AnalysisJobStage = 'queued' | 'downloading' | 'analyzing' | 'capturing' | 'saving' | 'done' | 'failed';

/** 처음 보는 영상의 1회차 분석 작업 (서버 메모리가 아닌 DB 에 기록되어 앱을 닫았다 열어도 조회 가능) */
export interface AnalysisJob {
  /** analysis_jobs.id (UUID) */
  job_id: string;
  /** 정규화된 원본 영상 URL */
  source_url: string;
  status: AnalysisJobStatus;
  stage: AnalysisJobStage;
  /** 실패 시 사용자에게 보여줄 사유 */
  error?: string;
  /** 실패 상태 코드 (422: 상품을 찾지 못함, 413: 영상이 너무 김, 502: 외부 서비스 실패 등) */
  error_code?: number;
  /** 완료 시 결과 영상 ID */
  video_id?: string;
  /** ISO 8601 */
  created_at: string;
  /** ISO 8601 */
  updated_at: string;
}

/**
 * POST /api/analyze, GET /api/jobs/{job_id} 응답.
 * - 이미 분석된 영상: video 만 (즉시 표시)
 * - 처음 보는 영상: job 만 (GET /api/jobs/{job_id} 로 진행 상황 조회)
 * - 작업 완료 후 조회: job + video
 */
export interface AnalyzeResponse {
  job?: AnalysisJob;
  video?: VideoAnalysisResponse;
}

/** GET /api/videos?ids=... 응답 — 리스트에 있는 영상의 최신 결과 (회차를 올리지 않는 조회 전용) */
export interface VideoLookupResponse {
  /** 존재하는 영상만 포함 (삭제된 ID 는 빠짐) */
  videos: VideoAnalysisResponse[];
}

// ---------------------------------------------------------------------------
// 피드백
// ---------------------------------------------------------------------------

/**
 * 제보 유형
 * - SAME: 이 제품이 맞아요 (WRONG_PRODUCT·NOT_IN_VIDEO 와 배타적인 '제품 판정' 표)
 * - WRONG_PRODUCT: 다른 제품이에요 / NOT_IN_VIDEO: 영상에 없는 제품이에요 → 여러 명이면 리스트에서 숨김
 * - WRONG_IMAGE: 사진이 달라요 → 여러 명이면 사진을 다시 고름
 * - WRONG_RETAILER: 판매처가 달라요 / WRONG_DETAIL: 용량·맛·메모가 달라요 / DUPLICATE: 중복이에요 → 검수용 기록
 */
export type FeedbackType =
  | 'SAME'
  | 'WRONG_PRODUCT'
  | 'NOT_IN_VIDEO'
  | 'WRONG_IMAGE'
  | 'WRONG_RETAILER'
  | 'WRONG_DETAIL'
  | 'DUPLICATE';

/** POST /api/feedback 요청 본문 */
export interface UserFeedbackRequest {
  /** ShoppingItem.id */
  item_id: string;
  feedback_type: FeedbackType;
  /** true 면 이 유형의 내 제보를 취소 */
  cancel?: boolean;
  /** 제보와 함께 보내는 의견 (선택, 300자 이내) */
  comment?: string;
}

/** POST /api/feedback 응답 본문 */
export interface UserFeedbackResponse {
  item_id: string;
  /** '이 제품이 맞아요' 수 */
  same_count: number;
  /** '다른 제품이에요' + '영상에 없는 제품이에요' 수 */
  different_count: number;
  /** 피드백 임계치 초과로 리스트에서 숨겨졌는지 여부 */
  is_hidden: boolean;
  /** 유형별 제보 수 (key: FeedbackType) */
  report_counts: Record<string, number>;
  /** '사진이 달라요' 제보가 모여 사진을 내리고 다시 고르는 중인지 */
  image_reset: boolean;
}

// ---------------------------------------------------------------------------
// 관련 영상 ("이 제품이 나온 다른 영상")
// ---------------------------------------------------------------------------

export interface RelatedVideo {
  /** 상대 영상 속 같은 제품 아이템 (연결 떼기에 사용) */
  other_item_id: string;
  video_id: string;
  source_title: string;
  creator_name: string;
  source_url: string;
}

/** GET /api/videos/{video_id}/related 응답 — key: ShoppingItem.id */
export interface RelatedVideosResponse {
  items: Record<string, RelatedVideo[]>;
}

/** POST /api/related/unlink — "이 영상의 제품은 달라요" (잘못 연결된 같은 제품 떼기) */
export interface RelatedUnlinkRequest {
  /** 내 리스트의 아이템 */
  item_id: string;
  /** RelatedVideo.other_item_id */
  other_item_id: string;
}

export interface RelatedUnlinkResponse {
  item_id: string;
  other_item_id: string;
  /** 여러 명이 떼어 모든 사용자에게서 숨겨졌는지 (요청자에게는 항상 즉시 숨김) */
  unlinked: boolean;
}

// ---------------------------------------------------------------------------
// 공통
// ---------------------------------------------------------------------------

/** GET /health 응답 */
export interface HealthResponse {
  status: 'ok';
  version: string;
  /** ISO 8601 */
  time: string;
}

/** FastAPI 에러 응답 형식 */
export interface ApiErrorResponse {
  detail: string;
}

/** Gemini 추출 시 사용하는 카테고리 목록 (백엔드 enum 과 동일 순서) */
export const SHOPPING_CATEGORIES = [
  '신선식품',
  '가공식품',
  '음료/주류',
  '생활용품',
  '주방용품',
  '뷰티',
  '가전/디지털',
  '패션',
  '기타',
] as const;

export type ShoppingCategory = (typeof SHOPPING_CATEGORIES)[number];

export const FEEDBACK_TYPES: readonly FeedbackType[] = [
  'SAME',
  'WRONG_PRODUCT',
  'NOT_IN_VIDEO',
  'WRONG_IMAGE',
  'WRONG_RETAILER',
  'WRONG_DETAIL',
  'DUPLICATE',
] as const;
