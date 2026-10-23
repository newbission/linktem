-- Supabase 공개 API(PostgREST) 차단 — 001_init.sql 다음에 1회 실행 (재실행해도 안전)
--
-- Supabase 는 public 스키마 테이블을 anon/authenticated 키로 REST 에 자동 노출한다.
-- Linktem 은 백엔드가 DB 에 직접 접속(postgres 역할 = 테이블 소유자)하므로 REST 가 필요 없다.
-- RLS 를 켜고 정책을 두지 않으면 anon/authenticated 는 모든 행이 거부되고,
-- 소유자(postgres)는 RLS 를 우회하므로 API 동작에는 영향이 없다. (FORCE 는 쓰지 않음)

alter table videos               enable row level security;
alter table products             enable row level security;
alter table video_items          enable row level security;
alter table image_lifecycle_logs enable row level security;
alter table user_feedback        enable row level security;

-- 로컬 Postgres(docker)에는 anon/authenticated 역할이 없으므로 있을 때만 권한 회수
do $$
declare
  r text;
begin
  foreach r in array array['anon', 'authenticated'] loop
    if exists (select 1 from pg_roles where rolname = r) then
      execute format(
        'revoke all on videos, products, video_items, image_lifecycle_logs, user_feedback from %I', r
      );
    end if;
  end loop;
end
$$;
