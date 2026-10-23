"""5회 점진적 앙상블 & 캐시 오케스트레이션.

| 회차 | 동작                                                                          |
| ---- | ----------------------------------------------------------------------------- |
| 1    | 다운로드 → Gemini → 캡처 → R2 → DB 저장 → 즉시 응답                            |
| 2~4  | 캐시 즉시 응답 + BackgroundTask: 추가 Gemini 회차 → 전 회차 다수결 → 아이템 동기화 |
| 5    | 캐시 응답 + is_locked=true. BackgroundTask: 최종 다수결 확정 (Gemini 호출 없음)     |
| 6+   | 캐시만 응답                                                                    |

- 회차는 처음 보는 요청자(익명 해시)일 때만 증가한다 → 한 사람이 연타해 조기 동결되는 것 방지.
- 동일 URL 최초 분석이 동시에 들어오면 하나의 작업을 공유한다 (in-flight dedupe).
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
from typing import Any
from uuid import UUID

import asyncpg
import httpx
from fastapi import BackgroundTasks

from app import repositories as repo
from app.config import Settings
from app.schemas import (
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
from app.services.image_processor import ImageProcessor
from app.services.storage import MediaStorage, StorageError, UploadedImage, build_image_key, superseded_expiry
from app.services.url_utils import UnsupportedUrlError, VideoTarget, normalize_video_url

logger = logging.getLogger(__name__)

# 타임스탬프가 이 이상 바뀌면 스틸컷을 다시 캡처
RECAPTURE_THRESHOLD_SEC = 3.0


class AnalysisError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


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
    ) -> None:
        self._settings = settings
        self._pool = pool
        self._downloader = downloader
        self._gemini = gemini
        self._images = images
        self._storage = storage
        self._video_locks: dict[str, asyncio.Lock] = {}
        self._inflight: dict[str, asyncio.Task[VideoAnalysisResponse]] = {}
        # Render 무료 인스턴스(512MB) 보호: 다운로드+AI+ffmpeg 무거운 작업 동시 실행 수 제한
        self._heavy = asyncio.Semaphore(2)

    # ==================================================================
    # POST /api/analyze
    # ==================================================================

    async def analyze(self, raw_url: str, client_hash: str, background: BackgroundTasks) -> VideoAnalysisResponse:
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
            return await self._first_analysis_dedup(target, client_hash)
        return await self._serve_cached(video["id"], client_hash, background)

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

    async def _first_analysis_dedup(self, target: VideoTarget, client_hash: str) -> VideoAnalysisResponse:
        key = target.canonical_key
        task = self._inflight.get(key)
        if task is None:
            task = asyncio.create_task(self._first_analysis(target, client_hash))
            self._inflight[key] = task
            task.add_done_callback(lambda _t: self._inflight.pop(key, None))
        # shield: 첫 요청자가 연결을 끊어도 작업은 계속되어 다른 대기자/캐시에 결과가 남음
        return await asyncio.shield(task)

    async def _first_analysis(self, target: VideoTarget, client_hash: str) -> VideoAnalysisResponse:
        pool = self._require_pool()
        if not self._gemini.enabled:
            raise AnalysisError(503, "AI 분석 기능이 설정되지 않았습니다.")

        video_id = uuid.uuid4()
        async with self._heavy:
            with tempfile.TemporaryDirectory(prefix="linktem-") as tmp:
                workdir = Path(tmp)
                downloaded, raw_items = await self._download_and_extract(target, workdir, run_index=1)
                if not raw_items:
                    raise AnalysisError(422, "영상에서 장보기 상품을 찾지 못했어요.")

                consensus = build_consensus(parse_runs([raw_items]))
                uploads = await self._capture_and_upload(
                    video_id, downloaded, [c.timestamp_sec for c in consensus], workdir
                )

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
            await self._storage.delete_keys(uploaded_keys)
            raise

        if video is None:
            # 다른 인스턴스/요청이 먼저 저장함 → 업로드한 이미지는 버리고 캐시 경로로
            await self._storage.delete_keys(uploaded_keys)
            async with pool.acquire() as conn:
                existing = await repo.get_video_by_key(conn, target.canonical_key)
            assert existing is not None
            return await self.build_response(existing["id"])

        return await self.build_response(video_id)

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
                            video_id, downloaded, [float(i["timestamp_sec"]) for i in items], workdir
                        )
                async with pool.acquire() as conn, conn.transaction():
                    for item, upload in zip(items, uploads):
                        if upload is None:
                            continue
                        await repo.set_item_image(conn, item["id"], upload.key, upload.url)
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
                video_id, downloaded, [p.consensus.timestamp_sec for p in capture_plans], workdir
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
                        vote_count=c.votes,
                        position=c.position,
                    )
                    if upload is not None:
                        await repo.set_item_image(conn, row["id"], upload.key, upload.url)
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
            await self._storage.delete_keys([u.key for u in uploads if u])
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
            edition_note=item.edition_note,
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
        self, target: VideoTarget, workdir: Path, run_index: int
    ) -> tuple[DownloadedVideo, list[dict[str, Any]]]:
        try:
            if target.platform == "youtube" and self._settings.gemini_use_youtube_url:
                gemini_task = asyncio.create_task(self._gemini.analyze_youtube_url(target.url, run_index))
                # 다운로드가 먼저 실패해 결과를 기다리지 않게 되어도 "exception never retrieved" 경고가 없도록
                gemini_task.add_done_callback(lambda t: t.cancelled() or t.exception())
                try:
                    downloaded = await self._downloader.download(target.url, workdir)
                except BaseException:
                    gemini_task.cancel()
                    raise
                try:
                    raw_items = await gemini_task
                except GeminiError as exc:
                    logger.warning("gemini youtube-url path failed (%s) — falling back to file upload", exc)
                    raw_items = await self._gemini.analyze_file(downloaded.path, run_index, downloaded.meta.duration)
            else:
                downloaded = await self._downloader.download(target.url, workdir)
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
        self, video_id: UUID, downloaded: DownloadedVideo, timestamps: list[float], workdir: Path
    ) -> list[UploadedImage | None]:
        duration = float(downloaded.meta.duration) if downloaded.meta.duration else None

        async def _one(ts: float) -> UploadedImage | None:
            try:
                data = await self._images.capture_webp(downloaded.path, ts, workdir, duration)
                if not self._storage.enabled:
                    logger.warning("스틸컷 저장소 미설정 — 업로드 생략")
                    return None
                return await self._storage.upload_webp(build_image_key(video_id), data)
            except (StorageError, RuntimeError) as exc:
                logger.warning("capture/upload failed at %.2fs: %s", ts, exc)
                return None

        return list(await asyncio.gather(*(_one(ts) for ts in timestamps)))

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
                    retailer=r["retailer"],
                    is_checked=False,
                    edition_note=r["edition_note"],
                )
                for r in rows
            ],
        )

    async def submit_feedback(self, item_id: str, feedback_type: str, client_hash: str) -> UserFeedbackResponse:
        pool = self._require_pool()
        item_uuid = _parse_uuid(item_id)
        async with pool.acquire() as conn, conn.transaction():
            row = await repo.upsert_feedback(
                conn, item_uuid, feedback_type, client_hash, self._settings.feedback_hide_threshold
            )
        if row is None:
            raise AnalysisError(404, "아이템을 찾을 수 없습니다.")
        return UserFeedbackResponse(
            item_id=str(row["id"]),
            same_count=row["same_count"],
            different_count=row["different_count"],
            is_hidden=row["is_hidden"],
        )

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


def _parse_uuid(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise AnalysisError(404, "잘못된 ID 입니다.") from exc
