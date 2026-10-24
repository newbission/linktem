"""5회 점진적 앙상블 & 캐시 오케스트레이션.

| 회차 | 동작                                                                                   |
| ---- | -------------------------------------------------------------------------------------- |
| 1    | 작업(analysis_jobs) 생성 후 즉시 응답 → 백그라운드: 다운로드 → Gemini → 캡처 → 저장       |
| 2~4  | 캐시 즉시 응답 + BackgroundTask: 추가 Gemini 회차 → 전 회차 다수결 → 아이템 동기화          |
| 5    | 캐시 응답 + is_locked=true. BackgroundTask: 최종 다수결 확정 (Gemini 호출 없음)              |
| 6+   | 캐시만 응답                                                                             |

- 1회차는 HTTP 요청과 분리된 작업으로 실행하고 진행 단계를 DB 에 기록한다 → 클라이언트는 짧은 조회로
  진행 상황을 확인하므로 긴 요청이 끊겨 결과를 잃지 않고, 앱을 닫았다 열어도 이어서 받는다.
- 회차는 처음 보는 요청자(익명 해시)일 때만 증가한다 → 한 사람이 연타해 조기 동결되는 것 방지.
- 동일 URL 최초 분석이 동시에 들어오면 하나의 작업을 공유한다 (진행 중 작업은 영상당 1개, DB 유니크 인덱스).
- 같은 영상의 백그라운드 작업은 영상별 asyncio.Lock 으로 직렬화한다 (Render 단일 인스턴스 전제, ADR-005).
- 아이템 ID 는 회차가 바뀌어도 유지된다 (클라이언트 체크 상태 보존): 같은 상품으로 매칭되면 UPDATE.
"""

from __future__ import annotations

import asyncio
import logging
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable
from uuid import UUID

import asyncpg
import httpx
from fastapi import BackgroundTasks

from app import repositories as repo
from app.config import Settings
from app.schemas import (
    AnalysisJob,
    AnalyzeResponse,
    RelatedVideo,
    RelatedVideosResponse,
    ShoppingItem,
    UserFeedbackResponse,
    VideoAnalysisResponse,
)
from app.services.downloader import DownloadedVideo, DownloadError, NoVideoError, VideoDownloader, VideoTooLongError
from app.services.ensemble import (
    ConsensusItem,
    build_consensus,
    feedback_penalty,
    names_match,
    normalize_name,
    parse_runs,
)
from app.services.gemini import GeminiAnalyzer, GeminiError
from app.services.frame_selector import FrameQuery, FrameSelector
from app.services.image_processor import FrameCandidate, ImageProcessor, discard, sharpest
from app.services.storage import (
    MediaStorage,
    StorageError,
    UploadedImage,
    build_image_key,
    delete_images,
    superseded_expiry,
    upload_capture,
)
from app.services.url_utils import UnsupportedUrlError, VideoTarget, normalize_video_url

logger = logging.getLogger(__name__)

# 타임스탬프가 이 이상 바뀌면 스틸컷을 다시 캡처
RECAPTURE_THRESHOLD_SEC = 3.0
# '사진이 달라요' 제보로 다시 고를 때의 후보 구간 (처음보다 넓게)
RECAPTURE_OFFSETS = (-3.0, -2.0, -1.0, 0.0, 1.0, 2.0, 3.0)
# 리스트 갱신 조회(GET /api/videos)에서 한 번에 받을 수 있는 영상 수
MAX_LOOKUP_IDS = 30

JOB_INTERRUPTED_MESSAGE = "서버가 다시 시작되어 분석이 중단됐어요. 다시 시도해 주세요."
JOB_UNEXPECTED_MESSAGE = "분석 중 알 수 없는 오류가 발생했어요. 잠시 후 다시 시도해 주세요."

StageCallback = Callable[[str], Awaitable[None]]


async def _no_stage(_: str) -> None:
    return None


class AnalysisError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


@dataclass
class CaptureTarget:
    timestamp_sec: float
    name_ko: str
    name_en: str

    @classmethod
    def of(cls, item: ConsensusItem) -> "CaptureTarget":
        return cls(item.timestamp_sec, item.name_ko, item.name_en)

    @classmethod
    def of_row(cls, row: asyncpg.Record) -> "CaptureTarget":
        return cls(float(row["timestamp_sec"]), row["name_ko"], row["name_en"])


@dataclass
class _Plan:
    consensus: ConsensusItem
    existing: asyncpg.Record | None
    needs_capture: bool


class Analyzer:
    def __init__(
        self,
        *,
        settings: Settings,
        pool: asyncpg.Pool | None,
        downloader: VideoDownloader,
        gemini: GeminiAnalyzer,
        images: ImageProcessor,
        storage: MediaStorage,
        frame_selector: FrameSelector | None = None,
    ) -> None:
        self._settings = settings
        self._pool = pool
        self._downloader = downloader
        self._gemini = gemini
        self._images = images
        self._storage = storage
        self._frames = frame_selector
        self._video_locks: dict[str, asyncio.Lock] = {}
        # 실행 중인 1회차 작업 (GC 로 사라지지 않도록 참조 보관, 종료 시 정리)
        self._job_tasks: set[asyncio.Task[None]] = set()
        # Render 무료 인스턴스(512MB) 보호: 다운로드+AI+ffmpeg 무거운 작업 동시 실행 수 제한
        self._heavy = asyncio.Semaphore(2)

    # ==================================================================
    # POST /api/analyze
    # ==================================================================

    async def analyze(self, raw_url: str, client_hash: str, background: BackgroundTasks) -> AnalyzeResponse:
        pool = self._require_pool()
        try:
            target = normalize_video_url(raw_url)
            if target.canonical_key.startswith("tiktok-short:"):
                target = await self._resolve_short_link(target)
        except UnsupportedUrlError as exc:
            raise AnalysisError(400, str(exc)) from exc

        async with pool.acquire() as conn:
            video = await repo.get_video_by_key(conn, target.canonical_key)
        if video is None:
            return AnalyzeResponse(job=await self._start_job(target, client_hash))
        return AnalyzeResponse(video=await self._serve_cached(video["id"], client_hash, background))

    async def _serve_cached(self, video_id: UUID, client_hash: str, background: BackgroundTasks) -> VideoAnalysisResponse:
        pool = self._require_pool()
        async with pool.acquire() as conn, conn.transaction():
            video, counted, lock_now = await repo.register_request(
                conn, video_id, client_hash, self._settings.ensemble_max_runs
            )

        if lock_now:
            logger.info("video %s locked at run %d", video_id, video["analysis_count"])
            background.add_task(self.finalize, video_id)
        elif counted:
            logger.info("video %s run %d scheduled", video_id, video["analysis_count"])
            background.add_task(self.run_background_ensemble, video_id)
        if video["images_expired"]:
            background.add_task(self.restore_images, video_id)
        return await self.build_response(video_id)

    # ==================================================================
    # 1회차 분석 작업 (POST /api/analyze → GET /api/jobs/{id})
    # ==================================================================

    async def _start_job(self, target: VideoTarget, client_hash: str) -> AnalysisJob:
        if not self._gemini.enabled:
            raise AnalysisError(503, "AI 분석 기능이 설정되지 않았습니다.")
        pool = self._require_pool()
        async with pool.acquire() as conn:
            job = await repo.create_job(
                conn,
                platform=target.platform,
                canonical_key=target.canonical_key,
                source_url=target.url,
                client_hash=client_hash,
            )
            if job is None:
                # 같은 영상을 다른 사람이 이미 분석 중 → 그 작업을 함께 기다린다
                job = await repo.get_active_job_by_key(conn, target.canonical_key)
                if job is not None:
                    return _job_model(job)
                # 조회 사이에 작업이 끝난 드문 경우: 새 작업을 만든다 (실행 시 캐시를 먼저 확인)
                job = await repo.create_job(
                    conn,
                    platform=target.platform,
                    canonical_key=target.canonical_key,
                    source_url=target.url,
                    client_hash=client_hash,
                )
                if job is None:
                    raise AnalysisError(409, "같은 영상의 분석이 이미 진행 중이에요. 잠시 후 다시 확인해 주세요.")

        task = asyncio.create_task(self._run_job(job["id"], target, client_hash), name=f"analysis-job-{job['id']}")
        self._job_tasks.add(task)
        task.add_done_callback(self._job_tasks.discard)
        logger.info("job %s queued for %s", job["id"], target.canonical_key)
        return _job_model(job)

    async def get_job(self, job_id: str) -> AnalyzeResponse:
        pool = self._require_pool()
        parsed = _parse_uuid(job_id)
        async with pool.acquire() as conn:
            job = await repo.get_job(conn, parsed)
        if job is None:
            raise AnalysisError(404, "분석 작업을 찾을 수 없어요. 링크를 다시 넣어 주세요.")
        video = await self.build_response(job["video_id"]) if job["status"] == "done" and job["video_id"] else None
        return AnalyzeResponse(job=_job_model(job), video=video)

    async def drain_jobs(self) -> None:
        """진행 중인 1회차 작업이 모두 끝날 때까지 대기 (테스트 / 정상 종료용)."""
        while self._job_tasks:
            await asyncio.gather(*list(self._job_tasks), return_exceptions=True)

    async def cancel_jobs(self) -> None:
        """서버 종료 시: 실행 중인 작업을 취소하고 실패로 기록되기를 기다린다."""
        for task in list(self._job_tasks):
            task.cancel()
        await asyncio.gather(*list(self._job_tasks), return_exceptions=True)

    async def fail_interrupted_jobs(self) -> int:
        """서버 시작 시: 이전 프로세스에서 끝나지 못한 작업 정리 (작업은 프로세스 메모리에서 실행되므로 이어갈 수 없음)."""
        if self._pool is None:
            return 0
        try:
            async with self._pool.acquire() as conn:
                count = await repo.fail_unfinished_jobs(conn, JOB_INTERRUPTED_MESSAGE, 503)
        except asyncpg.UndefinedTableError:
            # 서버는 띄우되(캐시 조회는 가능) 새 영상 분석은 마이그레이션 전까지 실패한다
            logger.error("analysis_jobs 테이블이 없습니다 — migrations/003_analysis_jobs.sql 을 실행하세요.")
            return 0
        if count:
            logger.warning("marked %d interrupted analysis job(s) as failed", count)
        return count

    async def _run_job(self, job_id: UUID, target: VideoTarget, client_hash: str) -> None:
        pool = self._require_pool()
        loop = asyncio.get_running_loop()
        started = loop.time()

        async def on_stage(stage: str) -> None:
            # 단계 전환 시각을 남겨 어디서 오래 걸리는지 로그로 바로 확인
            logger.info("job %s → %s (+%.1fs)", job_id, stage, loop.time() - started)
            try:
                async with pool.acquire() as conn:
                    await repo.set_job_stage(conn, job_id, stage)
            except Exception:  # noqa: BLE001 — 단계 표시는 부가 정보, 분석은 계속
                logger.warning("job %s stage update failed (%s)", job_id, stage, exc_info=True)

        async def fail(detail: str, code: int) -> None:
            async with pool.acquire() as conn:
                await repo.fail_job(conn, job_id, detail, code)

        try:
            async with pool.acquire() as conn:
                existing = await repo.get_video_by_key(conn, target.canonical_key)
            video_id = existing["id"] if existing else await self._first_analysis(target, client_hash, on_stage)
            async with pool.acquire() as conn:
                await repo.finish_job(conn, job_id, video_id)
            logger.info("job %s done in %.1fs (video %s)", job_id, loop.time() - started, video_id)
        except AnalysisError as exc:
            logger.info("job %s failed (%d): %s", job_id, exc.status_code, exc.detail)
            await fail(exc.detail, exc.status_code)
        except asyncio.CancelledError:
            # 종료 중 취소: 다음 시작 시 fail_interrupted_jobs 가 정리하지만, 가능하면 지금 기록
            try:
                await asyncio.shield(fail(JOB_INTERRUPTED_MESSAGE, 503))
            except Exception:  # noqa: BLE001
                pass
            raise
        except Exception:  # noqa: BLE001 — 작업 실패는 상태로만 전달
            logger.exception("job %s crashed", job_id)
            await fail(JOB_UNEXPECTED_MESSAGE, 500)

    async def _first_analysis(
        self, target: VideoTarget, client_hash: str, on_stage: StageCallback = _no_stage
    ) -> UUID:
        """1회차: 다운로드 → Gemini → 캡처 → 저장. 저장된(또는 동시에 먼저 저장된) 영상 ID 반환."""
        pool = self._require_pool()
        video_id = uuid.uuid4()
        async with self._heavy:
            with tempfile.TemporaryDirectory(prefix="linktem-") as tmp:
                workdir = Path(tmp)
                downloaded, raw_items = await self._download_and_extract(target, workdir, 1, on_stage)
                if not raw_items:
                    raise AnalysisError(422, "영상에서 장보기 상품을 찾지 못했어요.")

                await on_stage("capturing")
                consensus = build_consensus(parse_runs([raw_items]))
                uploads = await self._capture_and_upload(
                    video_id, downloaded, [CaptureTarget.of(c) for c in consensus], workdir
                )

        await on_stage("saving")
        uploaded_keys = [u.key for u in uploads if u]
        try:
            async with pool.acquire() as conn, conn.transaction():
                video = await repo.insert_video(
                    conn,
                    video_id=video_id,
                    platform=target.platform,
                    canonical_key=target.canonical_key,
                    source_url=target.url,
                    source_title=downloaded.meta.title,
                    creator_name=downloaded.meta.uploader,
                    duration_sec=downloaded.meta.duration,
                    first_run=raw_items,
                    client_hash=client_hash,
                )
                if video is not None:
                    for item, upload in zip(consensus, uploads):
                        await self._insert_consensus_item(conn, video_id, item, upload)
        except Exception:
            await delete_images(self._storage, uploaded_keys)
            raise

        if video is None:
            # 다른 인스턴스/요청이 먼저 저장함 → 업로드한 이미지는 버리고 기존 영상으로
            await delete_images(self._storage, uploaded_keys)
            async with pool.acquire() as conn:
                existing = await repo.get_video_by_key(conn, target.canonical_key)
            assert existing is not None
            return existing["id"]
        return video_id

    # ==================================================================
    # 리스트 갱신 조회 (GET /api/videos) — 회차를 올리지 않음
    # ==================================================================

    async def lookup_videos(self, video_ids: list[str]) -> list[VideoAnalysisResponse]:
        pool = self._require_pool()
        ids: list[UUID] = []
        for raw in dict.fromkeys(video_ids):
            try:
                ids.append(UUID(raw))
            except ValueError:
                continue
        if len(ids) > MAX_LOOKUP_IDS:
            raise AnalysisError(400, f"한 번에 최대 {MAX_LOOKUP_IDS}개 영상까지 조회할 수 있어요.")
        async with pool.acquire() as conn:
            rows = await conn.fetch("select id from videos where id = any($1::uuid[])", ids)
        existing = {r["id"] for r in rows}
        return [await self.build_response(vid) for vid in ids if vid in existing]

    # ==================================================================
    # 백그라운드 회차 (2~4) / 동결 (5) / 이미지 복원
    # ==================================================================

    async def run_background_ensemble(self, video_id: UUID) -> None:
        pool = self._require_pool()
        async with self._lock_for(video_id):
            try:
                async with pool.acquire() as conn:
                    video = await repo.get_video(conn, video_id)
                if video is None or not self._gemini.enabled:
                    return
                runs: list[Any] = list(video["analysis_runs"] or [])
                # Gemini 는 최대 (max_runs - 1) 회. 5회차는 동결 전용
                if len(runs) >= self._settings.ensemble_max_runs - 1:
                    return
                target = VideoTarget(video["platform"], video["canonical_key"], video["source_url"])
                run_index = len(runs) + 1

                async with self._heavy:
                    with tempfile.TemporaryDirectory(prefix="linktem-") as tmp:
                        workdir = Path(tmp)
                        downloaded, raw_items = await self._download_and_extract(target, workdir, run_index)
                        async with pool.acquire() as conn:
                            all_runs = await repo.append_run(conn, video_id, raw_items)
                            await repo.update_video_meta(
                                conn,
                                video_id,
                                source_title=downloaded.meta.title,
                                creator_name=downloaded.meta.uploader,
                                duration_sec=downloaded.meta.duration,
                            )
                        await self._apply_consensus(video_id, all_runs, downloaded, workdir)
                logger.info("video %s ensemble run %d applied (%d items)", video_id, run_index, len(raw_items))
            except Exception:  # noqa: BLE001 — 백그라운드 실패는 캐시 서빙에 영향 없음
                logger.exception("background ensemble failed for %s", video_id)

    async def finalize(self, video_id: UUID) -> None:
        """5회차 동결: 진행 중인 4회차가 있으면 Lock 으로 끝나길 기다린 뒤, 피드백 포함 최종 다수결 확정."""
        pool = self._require_pool()
        async with self._lock_for(video_id):
            try:
                async with pool.acquire() as conn:
                    video = await repo.get_video(conn, video_id)
                if video is None:
                    return
                await self._apply_consensus(video_id, list(video["analysis_runs"] or []), None, None)
                logger.info("video %s finalized with %d runs", video_id, len(video["analysis_runs"] or []))
            except Exception:  # noqa: BLE001
                logger.exception("finalize failed for %s", video_id)

    async def restore_images(self, video_id: UUID) -> None:
        """TTL 로 정리된 스틸컷을 저장된 타임스탬프로 다시 캡처 (Gemini 호출 없음 → 동결 영상도 가능)."""
        pool = self._require_pool()
        async with self._lock_for(video_id):
            try:
                async with pool.acquire() as conn:
                    video = await repo.get_video(conn, video_id)
                    if video is None or not video["images_expired"]:
                        return
                    items = await repo.list_items(conn, video_id, include_hidden=True)
                async with self._heavy:
                    with tempfile.TemporaryDirectory(prefix="linktem-") as tmp:
                        workdir = Path(tmp)
                        downloaded = await self._downloader.download(video["source_url"], workdir)
                        uploads = await self._capture_and_upload(
                            video_id, downloaded, [CaptureTarget.of_row(i) for i in items], workdir
                        )
                async with pool.acquire() as conn, conn.transaction():
                    for item, upload in zip(items, uploads):
                        if upload is None:
                            continue
                        await repo.set_item_image(conn, item["id"], upload.key, upload.url, upload.thumb_url)
                        await repo.log_image_event(
                            conn,
                            r2_key=upload.key,
                            event="RESTORED",
                            video_id=video_id,
                            item_id=item["id"],
                            size_bytes=upload.size_bytes,
                        )
                    await repo.set_images_expired(conn, video_id, False)
                logger.info("video %s images restored", video_id)
            except Exception:  # noqa: BLE001
                logger.exception("image restore failed for %s", video_id)

    # ==================================================================
    # 다수결 결과 → video_items 동기화
    # ==================================================================

    async def _apply_consensus(
        self,
        video_id: UUID,
        all_runs: list[Any],
        downloaded: DownloadedVideo | None,
        workdir: Path | None,
    ) -> None:
        pool = self._require_pool()
        async with pool.acquire() as conn:
            existing = list(await repo.list_items(conn, video_id, include_hidden=True))

        penalties: dict[str, int] = {}
        for row in existing:
            penalty = feedback_penalty(row["same_count"], row["different_count"])
            if penalty > 0:
                penalties[normalize_name(row["name_en"])] = penalty

        consensus = build_consensus(parse_runs(all_runs), penalties)
        if not consensus:
            logger.warning("video %s consensus empty — keeping current items", video_id)
            return

        plans = self._plan_sync(consensus, existing, can_capture=downloaded is not None)
        matched_ids = {p.existing["id"] for p in plans if p.existing is not None}
        removed = [row for row in existing if row["id"] not in matched_ids]

        capture_plans = [p for p in plans if p.needs_capture]
        uploads: list[UploadedImage | None] = []
        if capture_plans and downloaded is not None and workdir is not None:
            uploads = await self._capture_and_upload(
                video_id, downloaded, [CaptureTarget.of(p.consensus) for p in capture_plans], workdir
            )
        upload_by_plan = {id(p): u for p, u in zip(capture_plans, uploads)}

        expires_at = superseded_expiry(self._settings)
        try:
            async with pool.acquire() as conn, conn.transaction():
                for plan in plans:
                    c = plan.consensus
                    upload = upload_by_plan.get(id(plan))
                    if plan.existing is None:
                        await self._insert_consensus_item(conn, video_id, c, upload)
                        continue
                    row = plan.existing
                    await repo.update_item(
                        conn,
                        row["id"],
                        retailer=c.retailer,
                        timestamp_sec=c.timestamp_sec,
                        edition_note=c.edition_note,
                        reason=c.reason,
                        caution=c.caution,
                        vote_count=c.votes,
                        position=c.position,
                    )
                    if upload is not None:
                        await repo.set_item_image(conn, row["id"], upload.key, upload.url, upload.thumb_url)
                        await repo.log_image_event(
                            conn,
                            r2_key=upload.key,
                            event="UPLOADED",
                            video_id=video_id,
                            item_id=row["id"],
                            size_bytes=upload.size_bytes,
                        )
                        if row["image_key"]:
                            await repo.log_image_event(
                                conn,
                                r2_key=row["image_key"],
                                event="SUPERSEDED",
                                video_id=video_id,
                                item_id=row["id"],
                                expires_at=expires_at,
                            )

                for row in removed:
                    if row["image_key"]:
                        await repo.log_image_event(
                            conn,
                            r2_key=row["image_key"],
                            event="SUPERSEDED",
                            video_id=video_id,
                            item_id=row["id"],
                            expires_at=expires_at,
                        )
                await repo.delete_items(conn, [row["id"] for row in removed])
        except Exception:
            await delete_images(self._storage, [u.key for u in uploads if u])
            raise

    def _plan_sync(
        self, consensus: list[ConsensusItem], existing: list[asyncpg.Record], *, can_capture: bool
    ) -> list[_Plan]:
        available = {row["id"]: row for row in existing}
        plans: list[_Plan] = []
        for c in consensus:
            match = next((r for r in available.values() if r["normalized_key"] == c.product_key), None)
            if match is None:
                match = next(
                    (r for r in available.values() if names_match(r["name_en"], r["name_ko"], c.name_en, c.name_ko)),
                    None,
                )
            if match is not None:
                del available[match["id"]]
                moved = abs(float(match["timestamp_sec"]) - c.timestamp_sec) > RECAPTURE_THRESHOLD_SEC
                plans.append(_Plan(c, match, needs_capture=can_capture and (moved or not match["image_key"])))
            elif can_capture:
                # 새 상품은 스틸컷을 만들 수 있을 때만 추가 (동결 단계에서는 추가하지 않음)
                plans.append(_Plan(c, None, needs_capture=True))
        return plans

    async def _insert_consensus_item(
        self, conn: asyncpg.Connection, video_id: UUID, item: ConsensusItem, upload: UploadedImage | None
    ) -> None:
        product = await repo.upsert_product(
            conn,
            normalized_key=item.product_key,
            name_ko=item.name_ko,
            name_en=item.name_en,
            category=item.category,
            retailer=item.retailer,
        )
        item_id = await repo.upsert_item(
            conn,
            video_id=video_id,
            product_id=product["id"],
            retailer=item.retailer,
            timestamp_sec=item.timestamp_sec,
            image_key=upload.key if upload else "",
            image_url=upload.url if upload else "",
            thumb_url=upload.thumb_url if upload else "",
            edition_note=item.edition_note,
            reason=item.reason,
            caution=item.caution,
            vote_count=item.votes,
            position=item.position,
        )
        if upload is not None:
            await repo.log_image_event(
                conn,
                r2_key=upload.key,
                event="UPLOADED",
                video_id=video_id,
                item_id=item_id,
                size_bytes=upload.size_bytes,
            )

    # ==================================================================
    # 다운로드 / AI / 이미지
    # ==================================================================

    async def _download_and_extract(
        self, target: VideoTarget, workdir: Path, run_index: int, on_stage: StageCallback = _no_stage
    ) -> tuple[DownloadedVideo, list[dict[str, Any]]]:
        try:
            await on_stage("downloading")
            if target.platform == "youtube" and self._settings.gemini_use_youtube_url:
                gemini_task = asyncio.create_task(self._gemini.analyze_youtube_url(target.url, run_index))
                # 다운로드가 먼저 실패해 결과를 기다리지 않게 되어도 "exception never retrieved" 경고가 없도록
                gemini_task.add_done_callback(lambda t: t.cancelled() or t.exception())
                try:
                    downloaded = await self._downloader.download(target.url, workdir)
                except BaseException:
                    gemini_task.cancel()
                    raise
                await on_stage("analyzing")
                try:
                    raw_items = await gemini_task
                except GeminiError as exc:
                    logger.warning("gemini youtube-url path failed (%s) — falling back to file upload", exc)
                    raw_items = await self._gemini.analyze_file(downloaded.path, run_index, downloaded.meta.duration)
            else:
                downloaded = await self._downloader.download(target.url, workdir)
                await on_stage("analyzing")
                raw_items = await self._gemini.analyze_file(downloaded.path, run_index, downloaded.meta.duration)
        except VideoTooLongError as exc:
            raise AnalysisError(413, f"{exc.limit // 60}분 이하의 영상만 분석할 수 있어요.") from exc
        except NoVideoError as exc:
            raise AnalysisError(400, str(exc)) from exc
        except DownloadError as exc:
            raise AnalysisError(502, str(exc)) from exc
        except GeminiError as exc:
            logger.error("gemini failed: %s", exc)
            raise AnalysisError(502, "AI 분석에 실패했어요. 잠시 후 다시 시도해 주세요.") from exc

        duration = downloaded.meta.duration
        if duration:
            for item in raw_items:
                item["timestamp_sec"] = min(float(item["timestamp_sec"]), max(0.0, duration - 0.5))
        return downloaded, raw_items

    async def _capture_and_upload(
        self,
        video_id: UUID,
        downloaded: DownloadedVideo,
        targets: list[CaptureTarget],
        workdir: Path,
        offsets: tuple[float, ...] | list[float] | None = None,
    ) -> list[UploadedImage | None]:
        """상품별 후보 프레임 캡처 → (경량 AI 1회) 제품이 보이는 프레임 선택 → 확대용·썸네일 업로드."""
        if not targets:
            return []
        if not self._storage.enabled:
            logger.warning("스틸컷 저장소 미설정 — 업로드 생략")
            return [None] * len(targets)
        duration = float(downloaded.meta.duration) if downloaded.meta.duration else None

        async def _candidates(target: CaptureTarget) -> list[FrameCandidate]:
            try:
                return await self._images.capture_candidates(
                    downloaded.path, target.timestamp_sec, workdir, duration, offsets
                )
            except RuntimeError as exc:
                logger.warning("capture failed at %.2fs: %s", target.timestamp_sec, exc)
                return []

        per_target = list(await asyncio.gather(*(_candidates(t) for t in targets)))
        try:
            picks: list[int | None] | None = None
            if self._frames is not None and self._frames.enabled:
                queried = [i for i, c in enumerate(per_target) if c]
                choices = await self._frames.choose(
                    [
                        FrameQuery(targets[i].name_ko, targets[i].name_en, [c.preview for c in per_target[i]])
                        for i in queried
                    ]
                )
                if choices is not None:
                    picks = [None] * len(targets)
                    for i, choice in zip(queried, choices):
                        picks[i] = choice
                    missing = sum(1 for i in queried if picks[i] is None)
                    logger.info("frame selection: %d/%d picked by AI", len(queried) - missing, len(queried))

            async def _upload(index: int) -> UploadedImage | None:
                candidates = per_target[index]
                if not candidates:
                    return None
                choice = picks[index] if picks is not None else None
                # AI 가 고른 프레임, 없으면(보이는 후보 없음·선택 실패) 가장 선명한 프레임
                chosen = candidates[choice] if choice is not None else sharpest(candidates)
                try:
                    captured = await self._images.encode_candidate(chosen)
                    return await upload_capture(self._storage, build_image_key(video_id), captured.full, captured.thumb)
                except (StorageError, RuntimeError, OSError) as exc:
                    logger.warning("encode/upload failed at %.2fs: %s", chosen.timestamp_sec, exc)
                    return None

            return list(await asyncio.gather(*(_upload(i) for i in range(len(targets)))))
        finally:
            for candidates in per_target:
                discard(candidates)

    async def _resolve_short_link(self, target: VideoTarget) -> VideoTarget:
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
                resp = await client.get(target.url, headers={"User-Agent": "Mozilla/5.0"})
            return normalize_video_url(str(resp.url))
        except (httpx.HTTPError, UnsupportedUrlError) as exc:
            raise UnsupportedUrlError("틱톡 단축 링크를 확인하지 못했습니다.") from exc

    # ==================================================================
    # 조회 API
    # ==================================================================

    async def build_response(self, video_id: UUID) -> VideoAnalysisResponse:
        pool = self._require_pool()
        async with pool.acquire() as conn:
            video = await repo.get_video(conn, video_id)
            if video is None:
                raise AnalysisError(404, "영상을 찾을 수 없습니다.")
            rows = await repo.list_items(conn, video_id)
        return VideoAnalysisResponse(
            video_id=str(video["id"]),
            source_title=video["source_title"],
            creator_name=video["creator_name"],
            analysis_count=video["analysis_count"],
            is_locked=video["is_locked"],
            source_url=video["source_url"],
            items=[
                ShoppingItem(
                    id=str(r["id"]),
                    name_ko=r["name_ko"],
                    name_en=r["name_en"],
                    category=r["category"],
                    timestamp_sec=float(r["timestamp_sec"]),
                    image_url=r["image_url"],
                    # 썸네일 도입 전 캡처는 확대용 이미지로 대체
                    thumb_url=r["thumb_url"] or r["image_url"],
                    reason=r["reason"],
                    caution=r["caution"],
                    retailer=r["retailer"],
                    is_checked=False,
                    edition_note=r["edition_note"],
                )
                for r in rows
            ],
        )

    async def submit_feedback(
        self,
        item_id: str,
        feedback_type: str,
        client_hash: str,
        background: BackgroundTasks | None = None,
        *,
        cancel: bool = False,
    ) -> UserFeedbackResponse:
        pool = self._require_pool()
        item_uuid = _parse_uuid(item_id)
        image_reset = False
        async with pool.acquire() as conn, conn.transaction():
            row = await repo.upsert_feedback(
                conn, item_uuid, feedback_type, client_hash, self._settings.feedback_hide_threshold, cancel=cancel
            )
            if row is None:
                raise AnalysisError(404, "아이템을 찾을 수 없습니다.")
            image_reports = int((row["report_counts"] or {}).get("WRONG_IMAGE", 0))
            if (
                not cancel
                and feedback_type == "WRONG_IMAGE"
                and row["image_key"]
                and image_reports >= self._settings.image_report_threshold
            ):
                # 사진을 내리고(유예 후 삭제) 처리한 제보는 비운 뒤, 더 넓은 구간에서 다시 고른다
                await repo.set_item_image(conn, item_uuid, "", "", "")
                await repo.log_image_event(
                    conn,
                    r2_key=row["image_key"],
                    event="SUPERSEDED",
                    video_id=row["video_id"],
                    item_id=item_uuid,
                    expires_at=superseded_expiry(self._settings),
                )
                await repo.clear_reports(conn, item_uuid, "WRONG_IMAGE")
                row = await repo.refresh_feedback_counts(conn, item_uuid, self._settings.feedback_hide_threshold)
                image_reset = True

        if image_reset:
            logger.info("item %s image reported %d times — recapturing", item_uuid, image_reports)
            if background is not None:
                background.add_task(self.recapture_item, item_uuid)
            else:
                await self.recapture_item(item_uuid)
        return UserFeedbackResponse(
            item_id=str(row["id"]),
            same_count=row["same_count"],
            different_count=row["different_count"],
            is_hidden=row["is_hidden"],
            report_counts={k: int(v) for k, v in (row["report_counts"] or {}).items()},
            image_reset=image_reset,
        )

    async def repick_images(self, video_id: str) -> int:
        """영상의 모든 스틸컷을 후보 프레임 + AI 선택으로 다시 고른다 (관리자용). 바뀐 이미지 수 반환."""
        pool = self._require_pool()
        vid = _parse_uuid(video_id)
        async with self._lock_for(vid):
            async with pool.acquire() as conn:
                video = await repo.get_video(conn, vid)
                if video is None:
                    raise AnalysisError(404, "영상을 찾을 수 없습니다.")
                items = await repo.list_items(conn, vid, include_hidden=True)
            if not items:
                return 0
            async with self._heavy:
                with tempfile.TemporaryDirectory(prefix="linktem-") as tmp:
                    workdir = Path(tmp)
                    downloaded = await self._downloader.download(video["source_url"], workdir)
                    uploads = await self._capture_and_upload(
                        vid, downloaded, [CaptureTarget.of_row(i) for i in items], workdir
                    )
            changed = 0
            try:
                async with pool.acquire() as conn, conn.transaction():
                    for item, upload in zip(items, uploads):
                        if upload is None:
                            continue
                        if item["image_key"]:
                            await repo.log_image_event(
                                conn,
                                r2_key=item["image_key"],
                                event="SUPERSEDED",
                                video_id=vid,
                                item_id=item["id"],
                                expires_at=superseded_expiry(self._settings),
                            )
                        await repo.set_item_image(conn, item["id"], upload.key, upload.url, upload.thumb_url)
                        await repo.log_image_event(
                            conn,
                            r2_key=upload.key,
                            event="UPLOADED",
                            video_id=vid,
                            item_id=item["id"],
                            size_bytes=upload.size_bytes,
                        )
                        changed += 1
            except Exception:
                await delete_images(self._storage, [u.key for u in uploads if u])
                raise
            logger.info("video %s images re-picked (%d/%d)", vid, changed, len(items))
            return changed

    async def recapture_item(self, item_id: UUID) -> None:
        """'사진이 달라요' 제보 처리: 기존보다 넓은 구간(±3초)의 후보에서 제품이 보이는 프레임을 다시 고른다."""
        pool = self._require_pool()
        async with pool.acquire() as conn:
            item = await repo.get_item_for_recapture(conn, item_id)
        if item is None:
            return
        video_id = item["video_id"]
        async with self._lock_for(video_id):
            try:
                async with self._heavy:
                    with tempfile.TemporaryDirectory(prefix="linktem-") as tmp:
                        workdir = Path(tmp)
                        downloaded = await self._downloader.download(item["source_url"], workdir)
                        uploads = await self._capture_and_upload(
                            video_id, downloaded, [CaptureTarget.of_row(item)], workdir, RECAPTURE_OFFSETS
                        )
                upload = uploads[0] if uploads else None
                if upload is None:
                    return
                async with pool.acquire() as conn, conn.transaction():
                    still_exists = await conn.fetchval(
                        "select 1 from video_items where id = $1 and image_key = '' for update", item_id
                    )
                    if not still_exists:
                        # 그 사이 아이템이 지워졌거나 다른 경로로 사진이 채워짐 → 새 사진은 버림
                        await delete_images(self._storage, [upload.key])
                        return
                    await repo.set_item_image(conn, item_id, upload.key, upload.url, upload.thumb_url)
                    await repo.log_image_event(
                        conn,
                        r2_key=upload.key,
                        event="UPLOADED",
                        video_id=video_id,
                        item_id=item_id,
                        size_bytes=upload.size_bytes,
                    )
                logger.info("item %s recaptured", item_id)
            except Exception:  # noqa: BLE001 — 실패하면 '사진 준비 중'으로 남고 다음 앙상블 회차에서 다시 캡처
                logger.exception("recapture failed for item %s", item_id)

    async def related(self, video_id: str) -> RelatedVideosResponse:
        pool = self._require_pool()
        async with pool.acquire() as conn:
            rows = await repo.related_videos(conn, _parse_uuid(video_id))
        items: dict[str, list[RelatedVideo]] = {}
        for r in rows:
            items.setdefault(str(r["item_id"]), []).append(
                RelatedVideo(
                    video_id=str(r["video_id"]),
                    source_title=r["source_title"],
                    creator_name=r["creator_name"],
                    source_url=r["source_url"],
                )
            )
        return RelatedVideosResponse(items=items)

    # ==================================================================
    # helpers
    # ==================================================================

    def _require_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise AnalysisError(503, "데이터베이스가 설정되지 않았습니다.")
        return self._pool

    def _lock_for(self, video_id: UUID) -> asyncio.Lock:
        key = str(video_id)
        lock = self._video_locks.get(key)
        if lock is None:
            lock = self._video_locks[key] = asyncio.Lock()
        return lock


def _job_model(row: asyncpg.Record) -> AnalysisJob:
    return AnalysisJob(
        job_id=str(row["id"]),
        source_url=row["source_url"],
        status=row["status"],
        stage=row["stage"],
        error=row["error"],
        error_code=row["error_code"],
        video_id=str(row["video_id"]) if row["video_id"] else None,
        created_at=row["created_at"].isoformat(),
        updated_at=row["updated_at"].isoformat(),
    )


def _parse_uuid(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise AnalysisError(404, "잘못된 ID 입니다.") from exc
