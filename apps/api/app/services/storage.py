"""스틸컷 저장소 — Cloudflare R2(운영) / 로컬 디스크(개발·셀프호스팅) + 만료 이미지 정리.

STORAGE_BACKEND=auto(기본): R2 자격 증명이 있으면 R2, 없으면 LOCAL_STORAGE_DIR 에 저장.
로컬 저장 시 이미지는 API 의 /media 경로로 서빙되고, 응답에는 상대 URL(/media/...)이 담긴다.
→ 웹의 같은 출처 프록시를 거치므로 localhost·Tailscale IP 등 어떤 주소로 접속해도 이미지가 보인다.

오브젝트 키에 랜덤 접미사를 붙여 불변(immutable) URL 로 취급한다.
→ CDN/브라우저에 1년 캐시를 걸 수 있고, 교체된 이미지는 유예기간 뒤 안전하게 삭제할 수 있다.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol, Sequence
from uuid import UUID

import asyncpg
import boto3
from botocore.config import Config as BotoConfig

from app import repositories as repo
from app.config import Settings

logger = logging.getLogger(__name__)

DELETE_BATCH = 1000  # S3 DeleteObjects 최대 키 수


class StorageError(RuntimeError):
    pass


@dataclass
class UploadedImage:
    key: str
    url: str
    size_bytes: int


class MediaStorage(Protocol):
    @property
    def enabled(self) -> bool: ...

    async def upload_webp(self, key: str, data: bytes) -> UploadedImage: ...

    async def delete_keys(self, keys: Sequence[str]) -> int: ...


def build_image_key(video_id: UUID | str) -> str:
    return f"captures/{video_id}/{uuid.uuid4().hex}.webp"


def create_storage(settings: Settings) -> "R2Storage | LocalStorage":
    backend = settings.storage_backend
    if backend == "auto":
        backend = "r2" if settings.r2_configured else "local"
    if backend == "r2":
        storage: R2Storage | LocalStorage = R2Storage(settings)
        if not storage.enabled:
            logger.warning("STORAGE_BACKEND=r2 이지만 R2 자격 증명이 비어 있어 스틸컷을 저장하지 않습니다.")
    else:
        storage = LocalStorage(settings)
    logger.info("media storage: %s", type(storage).__name__)
    return storage


class R2Storage:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._bucket = settings.r2_bucket
        self._public_base = settings.r2_public_base_url.rstrip("/")
        self._client = None
        if settings.r2_account_id and settings.r2_access_key_id and settings.r2_secret_access_key:
            self._client = boto3.client(
                "s3",
                endpoint_url=settings.r2_endpoint_url,
                aws_access_key_id=settings.r2_access_key_id,
                aws_secret_access_key=settings.r2_secret_access_key,
                region_name="auto",
                config=BotoConfig(
                    signature_version="s3v4",
                    retries={"max_attempts": 3, "mode": "standard"},
                    connect_timeout=10,
                    read_timeout=30,
                ),
            )

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def public_url(self, key: str) -> str:
        return f"{self._public_base}/{key}" if key else ""

    async def upload_webp(self, key: str, data: bytes) -> UploadedImage:
        if self._client is None:
            raise StorageError("R2 자격 증명이 설정되지 않았습니다.")
        client = self._client

        def _put() -> None:
            client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=data,
                ContentType="image/webp",
                CacheControl="public, max-age=31536000, immutable",
            )

        try:
            await asyncio.to_thread(_put)
        except Exception as exc:  # noqa: BLE001
            raise StorageError(f"R2 업로드 실패: {key}") from exc
        return UploadedImage(key=key, url=self.public_url(key), size_bytes=len(data))

    async def delete_keys(self, keys: Sequence[str]) -> int:
        """키 목록을 일괄 삭제하고 삭제 성공 수를 반환. 존재하지 않는 키도 성공으로 간주(S3 의미론)."""
        keys = [k for k in dict.fromkeys(keys) if k]
        if not keys or self._client is None:
            return 0
        client = self._client

        def _delete(batch: list[str]) -> int:
            resp = client.delete_objects(
                Bucket=self._bucket,
                Delete={"Objects": [{"Key": k} for k in batch], "Quiet": True},
            )
            errors = resp.get("Errors") or []
            for err in errors:
                logger.warning("R2 delete error %s: %s", err.get("Key"), err.get("Message"))
            return len(batch) - len(errors)

        deleted = 0
        for i in range(0, len(keys), DELETE_BATCH):
            try:
                deleted += await asyncio.to_thread(_delete, keys[i : i + DELETE_BATCH])
            except Exception:  # noqa: BLE001
                logger.exception("R2 delete batch failed")
        return deleted


class LocalStorage:
    """로컬 디스크 저장소. 파일은 LOCAL_STORAGE_DIR/<key>, URL 은 LOCAL_STORAGE_PUBLIC_PATH/<key>."""

    def __init__(self, settings: Settings) -> None:
        self.root = Path(settings.local_storage_dir).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._public_base = settings.local_storage_public_path.rstrip("/")

    @property
    def enabled(self) -> bool:
        return True

    def public_url(self, key: str) -> str:
        return f"{self._public_base}/{key}" if key else ""

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        # 키는 내부에서 생성하지만, 저장소 루트 밖을 가리키는 경로는 방어적으로 차단
        if not path.is_relative_to(self.root):
            raise StorageError(f"잘못된 저장소 키: {key}")
        return path

    async def upload_webp(self, key: str, data: bytes) -> UploadedImage:
        path = self._path(key)

        def _write() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_bytes(data)
            tmp.replace(path)  # 원자적 교체 — 쓰는 도중의 파일이 서빙되지 않도록

        try:
            await asyncio.to_thread(_write)
        except OSError as exc:
            raise StorageError(f"로컬 저장 실패: {key}") from exc
        return UploadedImage(key=key, url=self.public_url(key), size_bytes=len(data))

    async def delete_keys(self, keys: Sequence[str]) -> int:
        def _delete() -> int:
            deleted = 0
            for key in dict.fromkeys(k for k in keys if k):
                try:
                    path = self._path(key)
                    path.unlink(missing_ok=True)
                    deleted += 1
                    # 비어 있는 captures/<video_id> 폴더 정리
                    if path.parent != self.root and not any(path.parent.iterdir()):
                        path.parent.rmdir()
                except (OSError, StorageError):
                    logger.warning("local delete failed: %s", key)
            return deleted

        return await asyncio.to_thread(_delete)


# ---------------------------------------------------------------------------
# 만료 이미지 정리 (POST /api/admin/cleanup 에서 호출)
# ---------------------------------------------------------------------------


def superseded_expiry(settings: Settings) -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=settings.image_superseded_grace_days)


async def cleanup_expired_images(storage: MediaStorage, pool: asyncpg.Pool, settings: Settings) -> dict[str, int]:
    """(a) 유예기간이 지난 SUPERSEDED 이미지 삭제 (b) 장기 미조회 영상의 이미지 삭제 → images_expired."""
    superseded_deleted = 0
    async with pool.acquire() as conn:
        due = await repo.due_superseded_images(conn)
    if due:
        superseded_deleted = await storage.delete_keys([r["r2_key"] for r in due])
        async with pool.acquire() as conn, conn.transaction():
            await repo.mark_logs_processed(conn, [r["id"] for r in due])
            for r in due:
                await repo.log_image_event(
                    conn,
                    r2_key=r["r2_key"],
                    event="DELETED",
                    video_id=r["video_id"],
                    item_id=r["video_item_id"],
                    processed=True,
                )

    expired_videos = 0
    expired_images = 0
    async with pool.acquire() as conn:
        stale_ids = await repo.stale_video_ids(conn, settings.image_ttl_days)
    for video_id in stale_ids:
        async with pool.acquire() as conn, conn.transaction():
            cleared = await repo.clear_video_images(conn, video_id)
            await repo.set_images_expired(conn, video_id, True)
            for r in cleared:
                await repo.log_image_event(
                    conn, r2_key=r["image_key"], event="EXPIRED", video_id=video_id, item_id=r["id"], processed=True
                )
        # DB 참조를 먼저 끊은 뒤 삭제 → 삭제 실패 시에도 깨진 URL 이 응답에 노출되지 않음
        expired_images += await storage.delete_keys([r["image_key"] for r in cleared])
        expired_videos += 1

    logger.info(
        "cleanup: superseded=%d expired_videos=%d expired_images=%d",
        superseded_deleted,
        expired_videos,
        expired_images,
    )
    return {
        "superseded_deleted": superseded_deleted,
        "expired_videos": expired_videos,
        "expired_images": expired_images,
    }
