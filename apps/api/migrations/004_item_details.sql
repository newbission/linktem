-- 아이템 상세: 확대용/썸네일 이미지 분리 + 영상 속 메모 — 003_analysis_jobs.sql 다음에 1회 실행 (재실행해도 안전)
--
-- image_key / image_url : 확대용 스틸컷 (짧은 변 720px)
-- thumb_url             : 리스트 카드용 썸네일 (짧은 변 256px). 키는 image_key 에서 파생 ({key}_t.webp)
--                         빈 문자열이면 이 컬럼 도입 전 캡처 → 클라이언트는 image_url 로 대체
-- reason                : 영상에서 말한 추천 이유 / 특징
-- caution               : 비슷한 제품과 헷갈리지 않도록 확인할 점

alter table video_items add column if not exists thumb_url text not null default '';
alter table video_items add column if not exists reason    text;
alter table video_items add column if not exists caution   text;
