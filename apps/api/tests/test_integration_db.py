"""실제 PostgreSQL 대상 5회 앙상블 통합 테스트.

외부 서비스(yt-dlp, Gemini, R2)는 가짜로 대체하고 ffmpeg 캡처와 SQL 은 실제로 실행한다.
실행: TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/linktem_test pytest tests/test_integration_db.py
(DB 에 migrations/*.sql 이 적용되어 있어야 하며, 테스트가 테이블을 비우므로 앱 DB 와 분리할 것)
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

import pytest
from fastapi import BackgroundTasks

from app.config import Settings
from app.db import create_pool
from app.schemas import VideoAnalysisResponse
from app.services.analyzer import JOB_INTERRUPTED_MESSAGE, AnalysisError, Analyzer
from app.services.downloader import DownloadedVideo, VideoMeta
from app.services.image_processor import ImageProcessor
from app.services.storage import UploadedImage, cleanup_expired_images

DB_URL = os.environ.get("TEST_DATABASE_URL")
# 테스트는 테이블을 truncate 하므로 앱이 쓰는 DB 를 가리키면 데이터가 지워진다 → DB 이름에 "test" 필수
_DB_NAME = urlparse(DB_URL).path.lstrip("/") if DB_URL else ""
pytestmark = [
    pytest.mark.skipif(not DB_URL, reason="TEST_DATABASE_URL not set"),
    pytest.mark.skipif(bool(DB_URL) and "test" not in _DB_NAME, reason="TEST_DATABASE_URL 의 DB 이름에 'test' 가 없음 (앱 DB 보호)"),
    pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed"),
]

URL = "https://youtu.be/dQw4w9WgXcQ"


def raw(name_ko: str, name_en: str, ts: float, conf: float = 0.9) -> dict[str, Any]:
    return {"name_ko": name_ko, "name_en": name_en, "category": "가공식품", "timestamp_sec": ts,
            "retailer": "이마트", "edition_note": None, "confidence": conf}


GYOZA = ("비비고 왕교자", "Bibigo Wang Gyoza")
RAMEN = ("신라면", "Shin Ramyun")
GHOST = ("유령 상품", "Ghost Product")
HETBAHN = ("햇반", "Hetbahn")

# 회차별 Gemini 결과: 1회차 유령 상품 오탐 → 2~4회차 다수결로 제거, 햇반은 3표로 추가
SCRIPTED_RUNS = [
    [raw(*GYOZA, 1.0), raw(*RAMEN, 2.0), raw(*GHOST, 3.0, conf=0.3)],
    [raw(*GYOZA, 1.2), raw(*RAMEN, 2.1), raw(*HETBAHN, 3.5)],
    [raw(*GYOZA, 1.1), raw(*RAMEN, 2.0), raw(*HETBAHN, 3.4)],
    [raw(*GYOZA, 1.0), raw(*RAMEN, 2.2), raw(*HETBAHN, 3.6)],
]


class FakeDownloader:
    def __init__(self, video: Path) -> None:
        self.video = video
        self.calls = 0

    async def download(self, url: str, workdir: Path) -> DownloadedVideo:
        self.calls += 1
        target = workdir / "video.mp4"
        shutil.copy(self.video, target)
        return DownloadedVideo(target, VideoMeta("dQw4w9WgXcQ", "이마트 장보기 하울", "살림채널", 4, url))


class FakeGemini:
    enabled = True

    def __init__(self) -> None:
        self.calls: list[int] = []

    async def analyze_youtube_url(self, url: str, run_index: int, duration: int | None = None) -> list[dict]:
        self.calls.append(run_index)
        return [dict(i) for i in SCRIPTED_RUNS[run_index - 1]]

    async def analyze_file(self, path: Path, run_index: int, duration: int | None = None) -> list[dict]:
        return await self.analyze_youtube_url("", run_index, duration)


class FakeStorage:
    enabled = True

    def __init__(self) -> None:
        self.objects: dict[str, int] = {}
        self.deleted: list[str] = []
        self._n = 0

    async def upload_webp(self, key: str, data: bytes) -> UploadedImage:
        self.objects[key] = len(data)
        return UploadedImage(key=key, url=f"https://img.test/{key}", size_bytes=len(data))

    async def delete_keys(self, keys: list[str]) -> int:
        keys = [k for k in keys if k]
        self.deleted.extend(keys)
        for k in keys:
            self.objects.pop(k, None)
        return len(keys)


@pytest.fixture(scope="module")
def sample_video(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("video") / "sample.mp4"
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
         "-i", "testsrc2=size=640x360:rate=25:duration=4", "-pix_fmt", "yuv420p", "-y", str(path)],
        check=True,
    )
    return path


@pytest.fixture()
async def env(sample_video: Path):
    settings = Settings(database_url=DB_URL, image_superseded_grace_days=0, image_ttl_days=30)
    pool = await create_pool(settings)
    assert pool is not None
    async with pool.acquire() as conn:
        await conn.execute(
            "truncate analysis_jobs, user_feedback, image_lifecycle_logs, video_items, products, videos"
            " restart identity cascade"
        )
    gemini, storage, downloader = FakeGemini(), FakeStorage(), FakeDownloader(sample_video)
    analyzer = Analyzer(
        settings=settings, pool=pool, downloader=downloader, gemini=gemini,  # type: ignore[arg-type]
        images=ImageProcessor(settings), storage=storage,  # type: ignore[arg-type]
    )
    yield analyzer, pool, gemini, storage, downloader, settings
    await pool.close()


async def resolve(analyzer: Analyzer, url: str, client: str, bg: BackgroundTasks | None = None) -> VideoAnalysisResponse:
    """POST /api/analyze → (처음 보는 영상이면) 작업 완료까지 대기 → GET /api/jobs/{id} 의 video."""
    bg = bg if bg is not None else BackgroundTasks()
    resp = await analyzer.analyze(url, client, bg)
    if resp.video is not None:
        assert resp.job is None
        await bg()  # 응답 이후 실행될 BackgroundTask 를 즉시 실행
        return resp.video
    assert resp.job is not None and resp.job.status == "queued"
    await analyzer.drain_jobs()
    done = await analyzer.get_job(resp.job.job_id)
    assert done.job is not None and done.job.status == "done", done.job and done.job.error
    assert done.video is not None and done.job.video_id == done.video.video_id
    return done.video


async def request(analyzer: Analyzer, client: str):
    bg = BackgroundTasks()
    return await resolve(analyzer, URL, client, bg), bg


async def test_progressive_ensemble_to_lock(env) -> None:
    analyzer, pool, gemini, storage, downloader, settings = env

    # --- 1회차: 즉시 분석 ---
    first, _ = await request(analyzer, "client-1")
    assert first.analysis_count == 1 and not first.is_locked
    assert {i.name_en for i in first.items} == {GYOZA[1], RAMEN[1], GHOST[1]}
    assert all(i.image_url.startswith("https://img.test/captures/") for i in first.items)
    ids_by_name = {i.name_en: i.id for i in first.items}

    # 같은 사람이 다시 요청 → 회차 증가 없음, Gemini 호출 없음
    again, bg = await request(analyzer, "client-1")
    assert again.analysis_count == 1 and len(bg.tasks) == 0

    # --- 2회차: 캐시 즉시 반환 + 백그라운드 분석 (2회 → 기준 1표, 합집합) ---
    second, bg = await request(analyzer, "client-2")
    assert second.analysis_count == 2
    assert {i.name_en for i in second.items} == {GYOZA[1], RAMEN[1], GHOST[1]}, "응답은 기존 캐시"
    assert len(bg.tasks) == 1

    # --- 3회차: 3회 → 기준 2표. 유령 상품(1표) 제거, 햇반(2표) 추가 ---
    third, _ = await request(analyzer, "client-3")
    assert third.analysis_count == 3
    video_uuid = UUID(first.video_id)
    after3 = await analyzer.build_response(video_uuid)
    names3 = {i.name_en for i in after3.items}
    assert names3 == {GYOZA[1], RAMEN[1], HETBAHN[1]}
    # 기존 아이템 ID 유지 (클라이언트 체크 상태 보존)
    kept = {i.name_en: i.id for i in after3.items}
    assert kept[GYOZA[1]] == ids_by_name[GYOZA[1]]
    assert kept[RAMEN[1]] == ids_by_name[RAMEN[1]]

    # --- 4회차 ---
    fourth, _ = await request(analyzer, "client-4")
    assert fourth.analysis_count == 4 and not fourth.is_locked

    # --- 5회차: 동결 ---
    fifth, bg = await request(analyzer, "client-5")
    assert fifth.analysis_count == 5 and fifth.is_locked
    assert gemini.calls == [1, 2, 3, 4], "Gemini 는 최대 4회만 호출"

    # --- 이후: 캐시만 ---
    sixth, bg = await request(analyzer, "client-6")
    assert sixth.analysis_count == 5 and sixth.is_locked and len(bg.tasks) == 0
    assert gemini.calls == [1, 2, 3, 4]

    async with pool.acquire() as conn:
        runs = await conn.fetchval("select jsonb_array_length(analysis_runs) from videos where id = $1", video_uuid)
        ghost_logs = await conn.fetchval("select count(*) from image_lifecycle_logs where event = 'SUPERSEDED'")
    assert runs == 4
    assert ghost_logs >= 1, "제거된 유령 상품 이미지는 SUPERSEDED 로 기록"

    # --- cleanup: 유예 0일 → SUPERSEDED 즉시 삭제 ---
    result = await cleanup_expired_images(storage, pool, settings)  # type: ignore[arg-type]
    assert result["superseded_deleted"] >= 1
    assert result["expired_videos"] == 0


async def test_feedback_hides_item_and_related_videos(env) -> None:
    analyzer, pool, gemini, storage, downloader, settings = env
    first, _ = await request(analyzer, "client-1")
    ramen = next(i for i in first.items if i.name_en == RAMEN[1])

    for n in range(3):
        fb = await analyzer.submit_feedback(ramen.id, "DIFFERENT", f"voter-{n}")
    assert fb.different_count == 3 and fb.is_hidden
    # 같은 사람 재투표는 갱신
    fb = await analyzer.submit_feedback(ramen.id, "SAME", "voter-0")
    assert (fb.same_count, fb.different_count) == (1, 2)

    with pytest.raises(AnalysisError) as err:
        await analyzer.submit_feedback("00000000-0000-0000-0000-000000000000", "SAME", "x")
    assert err.value.status_code == 404

    # 다른 영상에도 같은 상품(신라면)이 나오면 관련 영상으로 연결
    other_url = "https://www.youtube.com/shorts/aaaaaaaaaaa"
    bg = BackgroundTasks()
    other = await resolve(analyzer, other_url, "client-9", bg)
    related = await analyzer.related(other.video_id)
    gyoza_other = next(i for i in other.items if i.name_en == GYOZA[1])
    assert related.items[gyoza_other.id][0].video_id == first.video_id


async def test_expired_images_are_restored(env) -> None:
    analyzer, pool, gemini, storage, downloader, settings = env
    first, _ = await request(analyzer, "client-1")
    async with pool.acquire() as conn:
        await conn.execute("update videos set last_requested_at = now() - interval '60 days'")
    result = await cleanup_expired_images(storage, pool, settings)  # type: ignore[arg-type]
    assert result["expired_videos"] == 1 and result["expired_images"] == len(first.items)

    expired = await analyzer.build_response(UUID(first.video_id))
    assert all(i.image_url == "" for i in expired.items)

    calls_before = len(gemini.calls)
    resp, bg = await request(analyzer, "client-2")  # restore_images 백그라운드 실행
    restored = await analyzer.build_response(UUID(first.video_id))
    assert all(i.image_url.startswith("https://img.test/") for i in restored.items)
    async with pool.acquire() as conn:
        assert await conn.fetchval("select images_expired from videos") is False
    # 복원은 Gemini 를 쓰지 않음 (2회차 앙상블 1회만 추가)
    assert len(gemini.calls) == calls_before + 1


async def test_related_videos_match_across_retailers(env) -> None:
    """같은 상품이 다른 판매처(이마트 vs 코스트코)로 나와도 '이 제품이 나온 다른 영상'으로 연결 (ADR-010)."""
    analyzer, pool, gemini, storage, downloader, settings = env
    first, _ = await request(analyzer, "client-1")  # 이마트 비비고 왕교자

    async def costco_run(url: str, run_index: int, duration: int | None = None) -> list[dict]:
        item = raw(*GYOZA, 2.0)
        item["retailer"] = "Costco"
        return [item]

    gemini.analyze_youtube_url = costco_run  # type: ignore[method-assign]
    other = await resolve(analyzer, "https://www.youtube.com/shorts/bbbbbbbbbbb", "client-2")
    assert other.items[0].retailer == "코스트코"
    first_gyoza = next(i for i in first.items if i.name_en == GYOZA[1])
    assert first_gyoza.retailer == "이마트", "아이템 판매처는 영상별로 유지"

    related = await analyzer.related(other.video_id)
    assert [r.video_id for r in related.items[other.items[0].id]] == [first.video_id]


async def test_cached_video_served_without_ai(env) -> None:
    """이미 분석된 영상은 AI 키가 없어도(Gemini 비활성) 캐시를 즉시 반환한다."""
    analyzer, pool, gemini, storage, downloader, settings = env
    first, _ = await request(analyzer, "client-1")
    gemini.enabled = False
    downloads_before = downloader.calls

    # 2회차 백그라운드 작업은 Gemini 비활성이라 아무것도 하지 않아야 함
    cached = await resolve(analyzer, "https://www.youtube.com/shorts/dQw4w9WgXcQ", "client-2")
    assert cached.video_id == first.video_id
    assert {i.id for i in cached.items} == {i.id for i in first.items}
    assert downloader.calls == downloads_before, "캐시 응답에는 다운로드도 없어야 함"

    with pytest.raises(AnalysisError) as err:
        await analyzer.analyze("https://youtu.be/bbbbbbbbbbb", "client-3", BackgroundTasks())
    assert err.value.status_code == 503, "처음 보는 영상만 AI 미설정 에러"


async def test_first_analysis_runs_as_shared_background_job(env) -> None:
    """처음 보는 영상: 요청은 작업만 받고 즉시 반환, 동시에 들어온 다른 요청자는 같은 작업을 공유."""
    analyzer, pool, gemini, storage, downloader, settings = env
    started = asyncio.Event()
    release = asyncio.Event()
    original = gemini.analyze_youtube_url

    async def slow_run(url: str, run_index: int, duration: int | None = None) -> list[dict]:
        started.set()
        await release.wait()
        return await original(url, run_index, duration)

    gemini.analyze_youtube_url = slow_run  # type: ignore[method-assign]
    first = await analyzer.analyze(URL, "client-1", BackgroundTasks())
    second = await analyzer.analyze("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "client-2", BackgroundTasks())
    assert first.video is None and first.job is not None
    assert second.job is not None and second.job.job_id == first.job.job_id, "같은 영상은 작업 1개 공유"

    await asyncio.wait_for(started.wait(), timeout=5)
    progress = await analyzer.get_job(first.job.job_id)
    assert progress.job is not None and progress.job.status == "running"
    assert progress.job.stage in {"downloading", "analyzing"} and progress.video is None

    release.set()
    await analyzer.drain_jobs()
    done = await analyzer.get_job(first.job.job_id)
    assert done.job is not None and done.job.status == "done" and done.job.stage == "done"
    assert done.video is not None and done.video.analysis_count == 1
    assert gemini.calls == [1], "동시 요청이어도 AI 분석은 1회"

    # 완료 후 같은 링크는 작업 없이 바로 결과
    cached = await analyzer.analyze(URL, "client-1", BackgroundTasks())
    assert cached.job is None and cached.video is not None and cached.video.video_id == done.video.video_id


async def test_failed_job_reports_reason(env) -> None:
    analyzer, pool, gemini, storage, downloader, settings = env

    async def nothing(url: str, run_index: int, duration: int | None = None) -> list[dict]:
        return []

    gemini.analyze_youtube_url = nothing  # type: ignore[method-assign]
    resp = await analyzer.analyze(URL, "client-1", BackgroundTasks())
    assert resp.job is not None
    await analyzer.drain_jobs()
    failed = await analyzer.get_job(resp.job.job_id)
    assert failed.job is not None and failed.job.status == "failed" and failed.job.stage == "failed"
    assert failed.job.error_code == 422 and failed.job.error and "상품" in failed.job.error
    assert failed.video is None

    # 실패한 작업은 진행 중 목록에서 빠지므로 같은 링크로 다시 시도하면 새 작업
    retry = await analyzer.analyze(URL, "client-1", BackgroundTasks())
    assert retry.job is not None and retry.job.job_id != resp.job.job_id
    await analyzer.drain_jobs()

    with pytest.raises(AnalysisError) as err:
        await analyzer.get_job("00000000-0000-0000-0000-000000000000")
    assert err.value.status_code == 404


async def test_interrupted_jobs_are_failed_on_startup(env) -> None:
    analyzer, pool, gemini, storage, downloader, settings = env
    async with pool.acquire() as conn:
        job_id = await conn.fetchval(
            """
            insert into analysis_jobs (platform, canonical_key, source_url, client_hash, status, stage)
            values ('youtube', 'youtube:zzzzzzzzzzz', 'https://www.youtube.com/watch?v=zzzzzzzzzzz', 'c', 'running', 'analyzing')
            returning id
            """
        )
    assert await analyzer.fail_interrupted_jobs() == 1
    job = await analyzer.get_job(str(job_id))
    assert job.job is not None and job.job.status == "failed" and job.job.error == JOB_INTERRUPTED_MESSAGE


async def test_lookup_videos_does_not_count_requests(env) -> None:
    analyzer, pool, gemini, storage, downloader, settings = env
    first, _ = await request(analyzer, "client-1")
    videos = await analyzer.lookup_videos([first.video_id, "not-a-uuid", "00000000-0000-0000-0000-000000000000"])
    assert [v.video_id for v in videos] == [first.video_id]
    assert videos[0].analysis_count == 1, "조회는 회차를 올리지 않음"
    assert gemini.calls == [1]

    with pytest.raises(AnalysisError) as err:
        await analyzer.lookup_videos([str(UUID(int=n)) for n in range(1, 40)])
    assert err.value.status_code == 400
