import type { FeedbackType } from '@linktem/types';

/** 제보 메뉴에 보여줄 유형 (SAME 은 '되돌리기'/'맞아요' 용도라 메뉴에 없음) */
export type ReportType = Exclude<FeedbackType, 'SAME'>;

export const REPORT_OPTIONS: { type: ReportType; label: string; hint: string }[] = [
  { type: 'WRONG_PRODUCT', label: '다른 제품이에요', hint: '브랜드나 제품명을 잘못 알아봤어요' },
  { type: 'NOT_IN_VIDEO', label: '영상에 없는 제품이에요', hint: '영상에 나오지 않은 제품이 들어갔어요' },
  { type: 'WRONG_IMAGE', label: '사진이 달라요', hint: '사진에 이 제품이 안 보여요 — 여러 분이 알려주시면 다시 골라요' },
  { type: 'WRONG_RETAILER', label: '판매처가 달라요', hint: '다른 매장에서 산 제품이에요' },
  { type: 'WRONG_DETAIL', label: '용량·맛·메모가 달라요', hint: '에디션이나 메모 내용이 틀렸어요' },
  { type: 'DUPLICATE', label: '중복이에요', hint: '같은 제품이 리스트에 두 번 있어요' },
];

export const REPORT_LABELS: Record<ReportType, string> = Object.fromEntries(
  REPORT_OPTIONS.map((o) => [o.type, o.label]),
) as Record<ReportType, string>;

// 서로 배타적인 '제품 판정' — 하나를 고르면 나머지는 빠진다 (서버도 1인 1표)
const IDENTITY: FeedbackType[] = ['SAME', 'WRONG_PRODUCT', 'NOT_IN_VIDEO'];

/** 내 제보 목록에 유형을 넣거나 빼고 결과를 돌려준다 */
export function toggleReport(current: FeedbackType[], type: FeedbackType, cancel: boolean): FeedbackType[] {
  if (cancel) return current.filter((t) => t !== type);
  const base = IDENTITY.includes(type) ? current.filter((t) => !IDENTITY.includes(t)) : current;
  return base.includes(type) ? base : [...base, type];
}

/** 이전 버전 저장본: 아이템당 단일 값('SAME' | 'DIFFERENT') → 유형 목록 */
export function migrateReports(raw: unknown): Record<string, FeedbackType[]> {
  if (!raw || typeof raw !== 'object') return {};
  const result: Record<string, FeedbackType[]> = {};
  for (const [itemId, value] of Object.entries(raw as Record<string, unknown>)) {
    const list = Array.isArray(value) ? value : [value];
    const types = list
      .map((v) => (v === 'DIFFERENT' ? 'WRONG_PRODUCT' : v))
      .filter((v): v is FeedbackType => typeof v === 'string' && v !== 'SAME');
    if (types.length) result[itemId] = Array.from(new Set(types));
  }
  return result;
}
