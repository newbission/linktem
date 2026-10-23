-- 분석 작업(백그라운드) — 002_enable_rls.sql 다음에 1회 실행 (재실행해도 안전)
--
-- POST /api/analyze 는 처음 보는 영상이면 작업만 만들고 즉시 응답한다.
-- 클라이언트는 GET /api/jobs/{id} 로 진행 단계를 조회하므로, 앱을 닫았다 열어도 결과를 이어서 받는다.

create table if not exists analysis_jobs (
  id            uuid primary key default gen_random_uuid(),
  platform      text not null,
  canonical_key text not null,
  source_url    text not null,
  client_hash   text not null,                       -- 1회차 요청자 (videos.requester_hashes 첫 항목)
  status        text not null default 'queued'
                check (status in ('queued', 'running', 'done', 'failed')),
  stage         text not null default 'queued'
                check (stage in ('queued', 'downloading', 'analyzing', 'capturing', 'saving', 'done', 'failed')),
  error         text,                                -- 사용자에게 보여줄 실패 사유
  error_code    int,                                 -- HTTP 의미의 상태 코드 (422: 상품 없음, 502: 외부 서비스 실패 등)
  video_id      uuid references videos(id) on delete set null,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  finished_at   timestamptz
);

-- 같은 영상의 진행 중 작업은 하나만 → 여러 사람이 동시에 요청해도 다운로드/AI 분석은 1회
create unique index if not exists uq_analysis_jobs_active
  on analysis_jobs (canonical_key) where status in ('queued', 'running');
create index if not exists idx_analysis_jobs_finished
  on analysis_jobs (finished_at) where finished_at is not null;

drop trigger if exists trg_analysis_jobs_updated_at on analysis_jobs;
create trigger trg_analysis_jobs_updated_at before update on analysis_jobs
  for each row execute function set_updated_at();

-- Supabase 공개 REST 차단 (002 와 동일한 정책)
alter table analysis_jobs enable row level security;
do $$
declare
  r text;
begin
  foreach r in array array['anon', 'authenticated'] loop
    if exists (select 1 from pg_roles where rolname = r) then
      execute format('revoke all on analysis_jobs from %I', r);
    end if;
  end loop;
end
$$;
