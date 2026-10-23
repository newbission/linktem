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
  /** 해당 시점 스틸컷 WebP 공개 URL (Cloudflare R2). 이미지 만료/복원 중이면 빈 문자열 */
  image_url: string;
  /** 판매처 (예: "이마트", "코스트코", "다이소") */
  retailer: string;
  /** 체크 여부 — 서버는 항상 false 로 내려주고, 클라이언트가 로컬 상태로 관리 */
  is_checked: boolean;
  /** 한정판 / 용량 / 맛 등 에디션 메모 */
  edition_note?: string;
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
}

// ---------------------------------------------------------------------------
// 피드백
// ---------------------------------------------------------------------------

export type FeedbackType = 'SAME' | 'DIFFERENT';

/** POST /api/feedback 요청 본문 */
export interface UserFeedbackRequest {
  /** ShoppingItem.id */
  item_id: string;
  /** SAME: 영상 속 제품이 맞아요 / DIFFERENT: 다른 제품이에요 */
  feedback_type: FeedbackType;
}

/** POST /api/feedback 응답 본문 */
export interface UserFeedbackResponse {
  item_id: string;
  same_count: number;
  different_count: number;
  /** 피드백 임계치 초과로 리스트에서 숨겨졌는지 여부 */
  is_hidden: boolean;
}

// ---------------------------------------------------------------------------
// 관련 영상 ("이 제품이 나온 다른 영상")
// ---------------------------------------------------------------------------

export interface RelatedVideo {
  video_id: string;
  source_title: string;
  creator_name: string;
  source_url: string;
}

/** GET /api/videos/{video_id}/related 응답 — key: ShoppingItem.id */
export interface RelatedVideosResponse {
  items: Record<string, RelatedVideo[]>;
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

export const FEEDBACK_TYPES: readonly FeedbackType[] = ['SAME', 'DIFFERENT'] as const;
