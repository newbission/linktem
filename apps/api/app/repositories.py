"""SQL 접근 계층 — 모든 함수는 asyncpg Connection 을 받아 호출 측이 트랜잭션 경계를 정한다."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Sequence
from uuid import UUID

import asyncpg

REQUESTER_HASH_CAP = 50

_VIDEO_COLUMNS = """
    id, platform, canonical_key, source_url, source_title, creator_name, duration_sec,
    analysis_count, is_locked, analysis_runs, requester_hashes, images_expired, last_requested_at,
    summary, cover_key, cover_url
"""


# ---------------------------------------------------------------------------
# videos
# ---------------------------------------------------------------------------


async def get_video_by_key(conn: asyncpg.Connection, canonical_key: str) -> asyncpg.Record | None:
    return await conn.fetchrow(f"select {_VIDEO_COLUMNS} from videos where canonical_key = $1", canonical_key)


async def get_video(conn: asyncpg.Connection, video_id: UUID | str, *, for_update: bool = False) -> asyncpg.Record | None:
    suffix = " for update" if for_update else ""
    return await conn.fetchrow(f"select {_VIDEO_COLUMNS} from videos where id = $1{suffix}", _uuid(video_id))


async def insert_video(
    conn: asyncpg.Connection,
    *,
    video_id: UUID,
    platform: str,
    canonical_key: str,
    source_url: str,
    source_title: str,
    creator_name: str,
    duration_sec: int | None,
    first_run: list[dict[str, Any]],
    client_hash: str,
    summary: str | None = None,
    cover_key: str = "",
    cover_url: str = "",
) -> asyncpg.Record | None:
    """동일 canonical_key 가 이미 있으면 None (다른 인스턴스가 먼저 저장한 경우)."""
    return await conn.fetchrow(
        f"""
        insert into videos (id, platform, canonical_key, source_url, source_title, creator_name, duration_sec,
                            analysis_count, analysis_runs, requester_hashes, summary, cover_key, cover_url)
        values ($1, $2, $3, $4, $5, $6, $7, 1, $8::jsonb, array[$9]::text[], $10, $11, $12)
        on conflict (canonical_key) do nothing
        returning {_VIDEO_COLUMNS}
        """,
        video_id,
        platform,
        canonical_key,
        source_url,
        source_title,
        creator_name,
        duration_sec,
        [first_run],
        client_hash,
        summary,
        cover_key,
        cover_url,
    )


async def register_request(
    conn: asyncpg.Connection, video_id: UUID, client_hash: str, max_runs: int
) -> tuple[asyncpg.Record, bool, bool]:
    """요청 1건을 기록하고 (갱신된 video, 회차 증가 여부, 이번 요청으로 동결 여부) 를 반환.

    회차는 처음 보는 요청자일 때만 증가한다. 반드시 트랜잭션 안에서 호출할 것.
    """
    video = await get_video(conn, video_id, for_update=True)
    if video is None:
        raise LookupError(str(video_id))

    hashes: list[str] = list(video["requester_hashes"] or [])
    is_new_requester = client_hash not in hashes
    counted = is_new_requester and not video["is_locked"] and video["analysis_count"] < max_runs

    if not counted:
        updated = await conn.fetchrow(
            f"update videos set last_requested_at = now() where id = $1 returning {_VIDEO_COLUMNS}", video_id
        )
        return updated, False, False

    hashes = (hashes + [client_hash])[-REQUESTER_HASH_CAP:]
    new_count = video["analysis_count"] + 1
    lock_now = new_count >= max_runs
    updated = await conn.fetchrow(
        f"""
        update videos
           set analysis_count = $2, requester_hashes = $3::text[], is_locked = is_locked or $4,
               last_requested_at = now()
         where id = $1
        returning {_VIDEO_COLUMNS}
        """,
        video_id,
        new_count,
        hashes,
        lock_now,
    )
    return updated, True, lock_now


async def append_run(conn: asyncpg.Connection, video_id: UUID, run: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    row = await conn.fetchrow(
        "update videos set analysis_runs = analysis_runs || $2::jsonb where id = $1 returning analysis_runs",
        video_id,
        [run],
    )
    return list(row["analysis_runs"]) if row else []


async def update_video_meta(
    conn: asyncpg.Connection,
    video_id: UUID,
    *,
    source_title: str,
    creator_name: str,
    duration_sec: int | None,
    summary: str | None = None,
) -> None:
    """빈 값으로 덮어쓰지 않는다. 요약은 첫 요약을 유지하고 없을 때만 채운다 (회차마다 바뀌면 혼란)."""
    await conn.execute(
        """
        update videos
           set source_title = coalesce(nullif($2, ''), source_title),
               creator_name = coalesce(nullif($3, ''), creator_name),
               duration_sec = coalesce($4, duration_sec),
               summary = coalesce(summary, nullif($5, ''))
         where id = $1
        """,
        video_id,
        source_title,
        creator_name,
        duration_sec,
        summary,
    )


async def set_images_expired(conn: asyncpg.Connection, video_id: UUID, expired: bool) -> None:
    await conn.execute("update videos set images_expired = $2 where id = $1", video_id, expired)


async def stale_video_ids(conn: asyncpg.Connection, ttl_days: int, limit: int = 100) -> list[UUID]:
    rows = await conn.fetch(
        """
        select id from videos
         where images_expired = false and last_requested_at < now() - make_interval(days => $1)
         order by last_requested_at
         limit $2
        """,
        ttl_days,
        limit,
    )
    return [r["id"] for r in rows]


# ---------------------------------------------------------------------------
# video_items + products
# ---------------------------------------------------------------------------


async def list_items(conn: asyncpg.Connection, video_id: UUID, *, include_hidden: bool = False) -> list[asyncpg.Record]:
    return await conn.fetch(
        f"""
        select vi.id, vi.video_id, vi.product_id, vi.timestamp_sec::float8 as timestamp_sec, vi.image_key,
               vi.image_url, vi.thumb_url, vi.reason, vi.caution, vi.edition_note, vi.vote_count, vi.same_count, vi.different_count, vi.is_hidden,
               vi.position, vi.retailer, p.normalized_key, p.name_ko, p.name_en, p.category
          from video_items vi
          join products p on p.id = vi.product_id
         where vi.video_id = $1 {"" if include_hidden else "and vi.is_hidden = false"}
         order by vi.position, vi.timestamp_sec
        """,
        video_id,
    )


async def upsert_product(
    conn: asyncpg.Connection, *, normalized_key: str, name_ko: str, name_en: str, category: str, retailer: str
) -> asyncpg.Record:
    return await conn.fetchrow(
        """
        insert into products (normalized_key, name_ko, name_en, category, retailer)
        values ($1, $2, $3, $4, $5)
        on conflict (normalized_key) do update set updated_at = now()
        returning id, name_ko
        """,
        normalized_key,
        name_ko,
        name_en,
        category,
        retailer,
    )


async def upsert_item(
    conn: asyncpg.Connection,
    *,
    video_id: UUID,
    product_id: UUID,
    retailer: str,
    timestamp_sec: float,
    image_key: str,
    image_url: str,
    thumb_url: str,
    edition_note: str | None,
    reason: str | None,
    caution: str | None,
    vote_count: int,
    position: int,
) -> UUID:
    return await conn.fetchval(
        """
        insert into video_items (video_id, product_id, retailer, timestamp_sec, image_key, image_url, thumb_url,
                                 edition_note, reason, caution, vote_count, position)
        values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
        on conflict (video_id, product_id) do update
           set retailer = excluded.retailer,
               timestamp_sec = excluded.timestamp_sec,
               image_key = case when excluded.image_key <> '' then excluded.image_key else video_items.image_key end,
               image_url = case when excluded.image_key <> '' then excluded.image_url else video_items.image_url end,
               thumb_url = case when excluded.image_key <> '' then excluded.thumb_url else video_items.thumb_url end,
               edition_note = excluded.edition_note,
               reason = excluded.reason,
               caution = excluded.caution,
               vote_count = excluded.vote_count,
               position = excluded.position
        returning id
        """,
        video_id,
        product_id,
        retailer,
        timestamp_sec,
        image_key,
        image_url,
        thumb_url,
        edition_note,
        reason,
        caution,
        vote_count,
        position,
    )


async def update_item(
    conn: asyncpg.Connection,
    item_id: UUID,
    *,
    retailer: str,
    timestamp_sec: float,
    edition_note: str | None,
    reason: str | None,
    caution: str | None,
    vote_count: int,
    position: int,
) -> None:
    await conn.execute(
        """
        update video_items
           set retailer = $2, timestamp_sec = $3, edition_note = $4, reason = $5, caution = $6,
               vote_count = $7, position = $8
         where id = $1
        """,
        item_id,
        retailer,
        timestamp_sec,
        edition_note,
        reason,
        caution,
        vote_count,
        position,
    )


async def set_item_image(
    conn: asyncpg.Connection, item_id: UUID, image_key: str, image_url: str, thumb_url: str
) -> None:
    await conn.execute(
        "update video_items set image_key = $2, image_url = $3, thumb_url = $4 where id = $1",
        item_id,
        image_key,
        image_url,
        thumb_url,
    )


async def clear_video_images(conn: asyncpg.Connection, video_id: UUID) -> list[asyncpg.Record]:
    """영상의 모든 아이템 이미지 참조를 비우고, 비우기 전 (id, image_key) 를 반환."""
    return await conn.fetch(
        """
        with old as (
            select id, image_key from video_items where video_id = $1 and image_key <> '' for update
        )
        update video_items vi set image_key = '', image_url = '', thumb_url = ''
          from old where vi.id = old.id
        returning old.id, old.image_key
        """,
        video_id,
    )


async def delete_items(conn: asyncpg.Connection, item_ids: Sequence[UUID]) -> None:
    if item_ids:
        await conn.execute("delete from video_items where id = any($1::uuid[])", list(item_ids))


# ---------------------------------------------------------------------------
# user_feedback
# ---------------------------------------------------------------------------


async def upsert_feedback(
    conn: asyncpg.Connection,
    item_id: UUID,
    feedback_type: str,
    client_hash: str,
    hide_threshold: int,
    *,
    cancel: bool = False,
    comment: str | None = None,
) -> asyncpg.Record | None:
    """제보 반영(또는 취소) 후 집계/숨김 상태를 반환. 아이템이 없으면 None. 트랜잭션 안에서 호출.

    '제품 판정'(SAME / WRONG_PRODUCT / NOT_IN_VIDEO)은 1인 1표, 나머지 유형은 유형마다 1인 1건.
    """
    exists = await conn.fetchval("select 1 from video_items where id = $1 for update", item_id)
    if not exists:
        return None
    if cancel:
        await conn.execute(
            "delete from user_feedback where video_item_id = $1 and client_hash = $2 and feedback_type = $3",
            item_id,
            client_hash,
            feedback_type,
        )
    else:
        await conn.execute(
            """
            insert into user_feedback (video_item_id, feedback_type, client_hash, comment)
            values ($1, $2, $3, $4)
            on conflict (video_item_id, client_hash, report_group) do update
               set feedback_type = excluded.feedback_type,
                   comment = coalesce(excluded.comment, user_feedback.comment)
            """,
            item_id,
            feedback_type,
            client_hash,
            comment,
        )
    return await refresh_feedback_counts(conn, item_id, hide_threshold)


async def refresh_feedback_counts(conn: asyncpg.Connection, item_id: UUID, hide_threshold: int) -> asyncpg.Record:
    return await conn.fetchrow(
        """
        with agg as (
            select count(*) filter (where feedback_type = 'SAME') as same_count,
                   count(*) filter (where feedback_type in ('WRONG_PRODUCT', 'NOT_IN_VIDEO')) as different_count,
                   coalesce(
                       (select jsonb_object_agg(t.feedback_type, t.n)
                          from (select feedback_type, count(*) as n from user_feedback
                                 where video_item_id = $1 group by feedback_type) t),
                       '{}'::jsonb
                   ) as report_counts
              from user_feedback where video_item_id = $1
        )
        update video_items vi
           set same_count = agg.same_count,
               different_count = agg.different_count,
               report_counts = agg.report_counts,
               is_hidden = (agg.different_count >= $2 and agg.different_count > agg.same_count * 2)
          from agg
         where vi.id = $1
        returning vi.id, vi.video_id, vi.image_key, vi.same_count, vi.different_count, vi.is_hidden, vi.report_counts
        """,
        item_id,
        hide_threshold,
    )


async def clear_reports(conn: asyncpg.Connection, item_id: UUID, feedback_type: str) -> None:
    """처리한(사진을 다시 고른) 제보는 지운다 — 새 사진에 대한 제보를 처음부터 다시 모으기 위해."""
    await conn.execute(
        "delete from user_feedback where video_item_id = $1 and feedback_type = $2", item_id, feedback_type
    )


async def get_item_for_recapture(conn: asyncpg.Connection, item_id: UUID) -> asyncpg.Record | None:
    return await conn.fetchrow(
        """
        select vi.id, vi.video_id, vi.timestamp_sec::float8 as timestamp_sec, vi.image_key, p.name_ko, p.name_en,
               v.source_url
          from video_items vi
          join products p on p.id = vi.product_id
          join videos v on v.id = vi.video_id
         where vi.id = $1
        """,
        item_id,
    )


# ---------------------------------------------------------------------------
# related
# ---------------------------------------------------------------------------


async def related_videos(
    conn: asyncpg.Connection,
    video_id: UUID,
    *,
    client_hash: str = "",
    unlink_threshold: int = 2,
    per_item: int = 5,
) -> list[asyncpg.Record]:
    """같은 제품(products.id)이 나온 다른 영상. 여러 명이 뗀 연결과, 이 요청자가 직접 뗀 연결은 뺀다."""
    return await conn.fetch(
        """
        select item_id, other_item_id, video_id, source_title, creator_name, source_url
          from (
            select vi.id as item_id, o.id as other_item_id, v.id as video_id, v.source_title, v.creator_name,
                   v.source_url,
                   row_number() over (partition by vi.id order by v.last_requested_at desc) as rn
              from video_items vi
              join video_items o on o.product_id = vi.product_id and o.video_id <> vi.video_id
                                and o.is_hidden = false
              join videos v on v.id = o.video_id
             where vi.video_id = $1 and vi.is_hidden = false
               and not exists (
                   select 1 from related_unlinks u
                    where u.item_a = least(vi.id, o.id) and u.item_b = greatest(vi.id, o.id)
                      and (u.client_hash = $3
                           or (select count(*) from related_unlinks c
                                where c.item_a = u.item_a and c.item_b = u.item_b) >= $4)
               )
          ) ranked
         where rn <= $2
         order by item_id, rn
        """,
        video_id,
        per_item,
        client_hash,
        unlink_threshold,
    )


async def unlink_related(
    conn: asyncpg.Connection, item_id: UUID, other_item_id: UUID, client_hash: str
) -> int | None:
    """'이 영상의 제품은 달라요' 기록 후 그 연결의 누적 수. 같은 제품으로 연결된 쌍이 아니면 None."""
    linked = await conn.fetchval(
        """
        select 1 from video_items a join video_items b on a.product_id = b.product_id and a.video_id <> b.video_id
         where a.id = $1 and b.id = $2
        """,
        item_id,
        other_item_id,
    )
    if not linked:
        return None
    first, second = sorted([item_id, other_item_id])
    await conn.execute(
        """
        insert into related_unlinks (item_a, item_b, client_hash) values ($1, $2, $3)
        on conflict (item_a, item_b, client_hash) do nothing
        """,
        first,
        second,
        client_hash,
    )
    return await conn.fetchval(
        "select count(*) from related_unlinks where item_a = $1 and item_b = $2", first, second
    )


# ---------------------------------------------------------------------------
# image_lifecycle_logs
# ---------------------------------------------------------------------------


async def log_image_event(
    conn: asyncpg.Connection,
    *,
    r2_key: str,
    event: str,
    video_id: UUID | None = None,
    item_id: UUID | None = None,
    size_bytes: int | None = None,
    expires_at: datetime | None = None,
    processed: bool = False,
) -> None:
    await conn.execute(
        """
        insert into image_lifecycle_logs (video_id, video_item_id, r2_key, event, size_bytes, expires_at, processed_at)
        values ($1, $2, $3, $4, $5, $6, case when $7 then now() end)
        """,
        video_id,
        item_id,
        r2_key,
        event,
        size_bytes,
        expires_at,
        processed,
    )


async def due_superseded_images(conn: asyncpg.Connection, limit: int = 500) -> list[asyncpg.Record]:
    return await conn.fetch(
        """
        select id, r2_key, video_id, video_item_id from image_lifecycle_logs
         where event = 'SUPERSEDED' and processed_at is null and expires_at <= now()
         order by expires_at
         limit $1
        """,
        limit,
    )


async def mark_logs_processed(conn: asyncpg.Connection, log_ids: Sequence[int]) -> None:
    if log_ids:
        await conn.execute(
            "update image_lifecycle_logs set processed_at = now() where id = any($1::bigint[])", list(log_ids)
        )


# ---------------------------------------------------------------------------
# analysis_jobs (백그라운드 1회차 분석)
# ---------------------------------------------------------------------------

_JOB_COLUMNS = """
    id, platform, canonical_key, source_url, client_hash, status, stage, error, error_code, video_id,
    created_at, updated_at, finished_at
"""


async def create_job(
    conn: asyncpg.Connection, *, platform: str, canonical_key: str, source_url: str, client_hash: str
) -> asyncpg.Record | None:
    """같은 영상의 진행 중 작업이 이미 있으면 None (uq_analysis_jobs_active)."""
    return await conn.fetchrow(
        f"""
        insert into analysis_jobs (platform, canonical_key, source_url, client_hash)
        values ($1, $2, $3, $4)
        on conflict (canonical_key) where status in ('queued', 'running') do nothing
        returning {_JOB_COLUMNS}
        """,
        platform,
        canonical_key,
        source_url,
        client_hash,
    )


async def get_job(conn: asyncpg.Connection, job_id: UUID | str) -> asyncpg.Record | None:
    return await conn.fetchrow(f"select {_JOB_COLUMNS} from analysis_jobs where id = $1", _uuid(job_id))


async def get_active_job_by_key(conn: asyncpg.Connection, canonical_key: str) -> asyncpg.Record | None:
    return await conn.fetchrow(
        f"select {_JOB_COLUMNS} from analysis_jobs where canonical_key = $1 and status in ('queued', 'running')",
        canonical_key,
    )


async def set_job_stage(conn: asyncpg.Connection, job_id: UUID, stage: str) -> None:
    await conn.execute(
        "update analysis_jobs set status = 'running', stage = $2 where id = $1 and status in ('queued', 'running')",
        job_id,
        stage,
    )


async def finish_job(conn: asyncpg.Connection, job_id: UUID, video_id: UUID) -> None:
    await conn.execute(
        """
        update analysis_jobs
           set status = 'done', stage = 'done', video_id = $2, error = null, error_code = null, finished_at = now()
         where id = $1
        """,
        job_id,
        video_id,
    )


async def fail_job(conn: asyncpg.Connection, job_id: UUID, error: str, error_code: int) -> None:
    await conn.execute(
        """
        update analysis_jobs
           set status = 'failed', stage = 'failed', error = $2, error_code = $3, finished_at = now()
         where id = $1 and status in ('queued', 'running')
        """,
        job_id,
        error,
        error_code,
    )


async def fail_unfinished_jobs(conn: asyncpg.Connection, error: str, error_code: int) -> int:
    """서버 시작 시: 이전 프로세스에서 끝나지 못한 작업을 실패로 정리 (작업은 프로세스 메모리에서 실행됨)."""
    result = await conn.execute(
        """
        update analysis_jobs
           set status = 'failed', stage = 'failed', error = $1, error_code = $2, finished_at = now()
         where status in ('queued', 'running')
        """,
        error,
        error_code,
    )
    return int(result.split()[-1])


async def delete_finished_jobs(conn: asyncpg.Connection, older_than_days: int) -> int:
    result = await conn.execute(
        "delete from analysis_jobs where finished_at < now() - make_interval(days => $1)", older_than_days
    )
    return int(result.split()[-1])


def _uuid(value: UUID | str) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))
