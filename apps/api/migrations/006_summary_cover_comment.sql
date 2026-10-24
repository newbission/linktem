-- 영상 요약 / 대표 이미지 / 제보 의견 — 005_report_types.sql 다음에 1회 실행 (재실행해도 안전)
--
-- videos.summary    : 영상 전체 내용 한두 문장 요약 (AI)
-- videos.cover_key  : 대표 이미지 저장소 키 (플랫폼 썸네일을 받아 WebP 로 저장 — 인스타 CDN 링크는 만료되므로 직접 보관)
-- videos.cover_url  : 대표 이미지 공개 URL ('' 이면 클라이언트가 첫 상품 썸네일로 대체)
-- user_feedback.comment : 제보와 함께 보낸 의견 (선택)

alter table videos add column if not exists summary   text;
alter table videos add column if not exists cover_key text not null default '';
alter table videos add column if not exists cover_url text not null default '';

alter table user_feedback add column if not exists comment text;
