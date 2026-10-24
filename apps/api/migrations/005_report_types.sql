-- 제보 유형 확장 — 004_item_details.sql 다음에 1회 실행 (재실행해도 안전)
--
-- SAME            이 제품이 맞아요 ('다른 제품'·'영상에 없음' 제보를 반박/철회하는 표)
-- WRONG_PRODUCT   다른 제품이에요 (이름·브랜드를 잘못 알아봄)      → 숨김 임계치·앙상블 감점
-- NOT_IN_VIDEO    영상에 없는 제품이에요 (AI 가 지어냄)            → 숨김 임계치·앙상블 감점
-- WRONG_IMAGE     사진이 달라요 (스틸컷에 이 제품이 안 보임)        → 임계치 도달 시 사진을 다시 고름
-- WRONG_RETAILER  판매처가 달라요                                  → 기록 (검수용)
-- WRONG_DETAIL    용량·맛·메모가 달라요                            → 기록 (검수용)
-- DUPLICATE       같은 제품이 중복돼요                              → 기록 (검수용)
--
-- 한 사람이 한 아이템에 여러 유형을 제보할 수 있다. 단 SAME / WRONG_PRODUCT / NOT_IN_VIDEO 는
-- 서로 배타적인 '제품 판정' 이므로 report_group = 'identity' 로 묶어 1인 1표를 유지한다.

-- 기존 체크 제약/유니크 제약 제거 (자동 생성된 이름이라 조회해서 삭제)
do $$
declare
  c record;
begin
  for c in
    select conname from pg_constraint
     where conrelid = 'user_feedback'::regclass and contype in ('c', 'u')
       and conname <> 'user_feedback_feedback_type_check_v2'
  loop
    execute format('alter table user_feedback drop constraint %I', c.conname);
  end loop;
end
$$;

update user_feedback set feedback_type = 'WRONG_PRODUCT' where feedback_type = 'DIFFERENT';

alter table user_feedback drop constraint if exists user_feedback_feedback_type_check_v2;
alter table user_feedback add constraint user_feedback_feedback_type_check_v2 check (
  feedback_type in ('SAME', 'WRONG_PRODUCT', 'NOT_IN_VIDEO', 'WRONG_IMAGE', 'WRONG_RETAILER', 'WRONG_DETAIL', 'DUPLICATE')
);

alter table user_feedback add column if not exists report_group text
  generated always as (
    case when feedback_type in ('SAME', 'WRONG_PRODUCT', 'NOT_IN_VIDEO') then 'identity' else feedback_type end
  ) stored;

create unique index if not exists uq_user_feedback_group on user_feedback (video_item_id, client_hash, report_group);

-- 아이템별 유형 집계 (검수·응답용). same_count / different_count 는 기존대로 유지
alter table video_items add column if not exists report_counts jsonb not null default '{}'::jsonb;
