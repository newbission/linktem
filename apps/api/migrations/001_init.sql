-- Linktem 초기 스키마 — Supabase SQL Editor 에서 1회 실행
-- 테이블: videos, products, video_items, image_lifecycle_logs, user_feedback

create extension if not exists "pgcrypto";

-- ---------------------------------------------------------------------------
-- updated_at 자동 갱신 트리거
-- ---------------------------------------------------------------------------
create or replace function set_updated_at() returns trigger
language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- ---------------------------------------------------------------------------
-- videos
-- ---------------------------------------------------------------------------
create table if not exists videos (
  id                uuid primary key default gen_random_uuid(),
  platform          text not null check (platform in ('youtube', 'instagram', 'tiktok')),
  canonical_key     text not null unique,
  source_url        text not null,
  source_title      text not null default '',
  creator_name      text not null default '',
  duration_sec      integer,
  analysis_count    integer not null default 0 check (analysis_count >= 0),
  is_locked         boolean not null default false,
  analysis_runs     jsonb not null default '[]'::jsonb,
  requester_hashes  text[] not null default '{}',
  images_expired    boolean not null default false,
  last_requested_at timestamptz not null default now(),
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now()
);

create index if not exists idx_videos_last_requested_at on videos (last_requested_at)
  where images_expired = false;

drop trigger if exists trg_videos_updated_at on videos;
create trigger trg_videos_updated_at before update on videos
  for each row execute function set_updated_at();

-- ---------------------------------------------------------------------------
-- products
-- ---------------------------------------------------------------------------
create table if not exists products (
  id              uuid primary key default gen_random_uuid(),
  normalized_key  text not null unique,
  name_ko         text not null,
  name_en         text not null,
  category        text not null default '기타',
  retailer        text not null default '기타/미상',  -- 최초 발견 판매처 (대표값)
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);

drop trigger if exists trg_products_updated_at on products;
create trigger trg_products_updated_at before update on products
  for each row execute function set_updated_at();

-- ---------------------------------------------------------------------------
-- video_items
-- ---------------------------------------------------------------------------
create table if not exists video_items (
  id               uuid primary key default gen_random_uuid(),
  video_id         uuid not null references videos (id) on delete cascade,
  product_id       uuid not null references products (id) on delete restrict,
  retailer         text not null default '기타/미상',
  timestamp_sec    numeric(8, 2) not null default 0,
  image_key        text not null default '',
  image_url        text not null default '',
  edition_note     text,
  vote_count       integer not null default 1,
  same_count       integer not null default 0,
  different_count  integer not null default 0,
  is_hidden        boolean not null default false,
  position         integer not null default 0,
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now(),
  unique (video_id, product_id)
);

create index if not exists idx_video_items_video on video_items (video_id, position);
create index if not exists idx_video_items_product on video_items (product_id);

drop trigger if exists trg_video_items_updated_at on video_items;
create trigger trg_video_items_updated_at before update on video_items
  for each row execute function set_updated_at();

-- ---------------------------------------------------------------------------
-- image_lifecycle_logs
-- ---------------------------------------------------------------------------
create table if not exists image_lifecycle_logs (
  id             bigserial primary key,
  video_id       uuid,
  video_item_id  uuid,
  r2_key         text not null,
  event          text not null check (event in ('UPLOADED', 'SUPERSEDED', 'DELETED', 'EXPIRED', 'RESTORED')),
  size_bytes     integer,
  expires_at     timestamptz,
  processed_at   timestamptz,
  created_at     timestamptz not null default now()
);

create index if not exists idx_image_logs_pending on image_lifecycle_logs (expires_at)
  where event = 'SUPERSEDED' and processed_at is null;

-- ---------------------------------------------------------------------------
-- user_feedback
-- ---------------------------------------------------------------------------
create table if not exists user_feedback (
  id             bigserial primary key,
  video_item_id  uuid not null references video_items (id) on delete cascade,
  feedback_type  text not null check (feedback_type in ('SAME', 'DIFFERENT')),
  client_hash    text not null,
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now(),
  unique (video_item_id, client_hash)
);

drop trigger if exists trg_user_feedback_updated_at on user_feedback;
create trigger trg_user_feedback_updated_at before update on user_feedback
  for each row execute function set_updated_at();

-- ---------------------------------------------------------------------------
-- RLS: 백엔드는 service 커넥션(postgres 롤)으로 직접 접속하므로 anon/authenticated 접근은 전부 차단
-- ---------------------------------------------------------------------------
alter table videos               enable row level security;
alter table products             enable row level security;
alter table video_items          enable row level security;
alter table image_lifecycle_logs enable row level security;
alter table user_feedback        enable row level security;
