-- '이 제품이 나온 다른 영상' 잘못된 연결 떼기 — 006_summary_cover_comment.sql 다음에 1회 실행 (재실행해도 안전)
--
-- 같은 제품 판정은 영문 상품명 정규화 키가 같으면 연결된다 (products.normalized_key).
-- 이름이 흔하거나 AI 가 잘못 읽으면 다른 제품끼리 연결될 수 있어, 사용자가 '이 영상의 제품은 달라요'로 연결을 뗄 수 있다.
-- 아이템 쌍은 (작은 id, 큰 id) 로 저장해 어느 쪽에서 떼도 같은 연결로 집계한다.
-- 일정 수(RELATED_UNLINK_THRESHOLD) 이상 모이면 모든 사용자에게서 그 연결을 숨긴다.

create table if not exists related_unlinks (
  id           bigserial primary key,
  item_a       uuid not null references video_items (id) on delete cascade,
  item_b       uuid not null references video_items (id) on delete cascade,
  client_hash  text not null,
  created_at   timestamptz not null default now(),
  check (item_a < item_b),
  unique (item_a, item_b, client_hash)
);

create index if not exists idx_related_unlinks_pair on related_unlinks (item_a, item_b);

alter table related_unlinks enable row level security;
do $$
declare
  r text;
begin
  foreach r in array array['anon', 'authenticated'] loop
    if exists (select 1 from pg_roles where rolname = r) then
      execute format('revoke all on related_unlinks from %I', r);
    end if;
  end loop;
end
$$;
