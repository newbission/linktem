"""스틸컷 이미지 파이프라인: ffmpeg 후보 프레임 캡처 → 최적 프레임 선택 → 확대용 + 썸네일 WebP 두 장.

- 지정 시점 앞뒤로 후보 프레임 여러 장(기본 ±1초, 0.5초 간격 5장)을 캡처한다.
  Gemini 가 고른 시점은 1초 단위 샘플링이라 1~2초 어긋나 제품이 화면에 없는 경우가 많기 때문.
- 어떤 후보에 제품이 보이는지는 FrameSelector(경량 AI)가 고르고, 실패하면 가장 선명한(엣지 분산이 큰) 프레임을 쓴다.
- 확대용: 짧은 변 720px 이하(확대는 하지 않음), WebP q45. 목표 용량(50KB)을 넘으면 품질을 낮춘다 → 약 30KB.
- 썸네일: 짧은 변 256px, WebP q60 → 약 10KB. 리스트 카드(84px)는 썸네일만 받아 첫 화면이 가볍다.
"""

from __future__ import annotations

import asyncio
import io
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps, ImageStat

from app.config import Settings

logger = logging.getLogger(__name__)

FFMPEG_TIMEOUT_SEC = 30
# AI 선택용 미리보기 (작게 보내 토큰·전송량 절약, 포장 글씨는 식별 가능한 크기)
PREVIEW_MAX_SIDE = 384
PREVIEW_JPEG_QUALITY = 70


class ImageProcessingError(RuntimeError):
    pass


@dataclass
class CapturedImage:
    full: bytes
    thumb: bytes


@dataclass
class FrameCandidate:
    """후보 프레임 — 원본은 디스크(JPEG)에 두고 메모리에는 작은 미리보기만 둔다 (512MB 인스턴스 보호)."""

    timestamp_sec: float
    path: Path
    sharpness: float
    preview: bytes


class ImageProcessor:
    def __init__(self, settings: Settings, max_concurrency: int = 3) -> None:
        self._settings = settings
        self._ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
        self._semaphore = asyncio.Semaphore(max_concurrency)

    async def capture_candidates(
        self,
        video_path: Path,
        timestamp_sec: float,
        workdir: Path,
        duration: float | None = None,
        offsets: tuple[float, ...] | list[float] | None = None,
    ) -> list[FrameCandidate]:
        """timestamp_sec 앞뒤 후보 프레임 (시간 순). 영상 경계에서 겹치는 시점은 한 번만 캡처."""
        offsets = offsets if offsets is not None else self._settings.image_candidate_offsets
        stamps = sorted({round(_clamp_ts(timestamp_sec + off, duration), 2) for off in offsets})
        candidates: list[FrameCandidate] = []
        async with self._semaphore:
            for ts in stamps:
                out = workdir / f"cand-{timestamp_sec:.2f}-{ts:.2f}.jpg"
                if await self._extract_frame(video_path, ts, out):
                    candidates.append(await asyncio.to_thread(_describe_frame, ts, out))
            if not candidates:
                # 타임스탬프가 영상 끝을 넘긴 경우 등: 0초 근처로 한 번 더 시도
                out = workdir / f"cand-{timestamp_sec:.2f}-fallback.jpg"
                if await self._extract_frame(video_path, 0.0, out):
                    candidates.append(await asyncio.to_thread(_describe_frame, 0.0, out))
        if not candidates:
            raise ImageProcessingError(f"{timestamp_sec}초 프레임을 캡처하지 못했습니다.")
        return candidates

    async def encode_candidate(self, candidate: FrameCandidate) -> CapturedImage:
        return await asyncio.to_thread(self._encode_file, candidate.path)

    async def capture_webp(
        self,
        video_path: Path,
        timestamp_sec: float,
        workdir: Path,
        duration: float | None = None,
    ) -> CapturedImage:
        """AI 선택 없이: 후보 중 가장 선명한 프레임을 확대용·썸네일 WebP 로 반환."""
        candidates = await self.capture_candidates(video_path, timestamp_sec, workdir, duration)
        try:
            return await self.encode_candidate(sharpest(candidates))
        finally:
            discard(candidates)

    def _encode_file(self, path: Path) -> CapturedImage:
        with Image.open(path) as img:
            frame = ImageOps.exif_transpose(img).convert("RGB")
        return CapturedImage(full=self.encode_webp(frame), thumb=self.encode_thumb(frame))

    async def _extract_frame(self, video_path: Path, ts: float, out: Path) -> bool:
        cmd = [
            self._ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            f"{ts:.3f}",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            "-an",
            "-y",
            str(out),
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE
        )
        try:
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=FFMPEG_TIMEOUT_SEC)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            logger.warning("ffmpeg timeout at %.2fs", ts)
            return False
        if proc.returncode != 0 or not out.exists() or out.stat().st_size == 0:
            logger.debug("ffmpeg failed at %.2fs: %s", ts, stderr.decode(errors="ignore")[:300])
            return False
        return True

    # ------------------------------------------------------------------
    # Pillow (CPU 작업 — 스레드에서 실행)
    # ------------------------------------------------------------------

    def encode_cover(self, data: bytes) -> bytes:
        """플랫폼 대표 이미지(JPEG 등) → 썸네일 크기 WebP."""
        with Image.open(io.BytesIO(data)) as img:
            frame = ImageOps.exif_transpose(img).convert("RGB")
        return self.encode_thumb(frame)

    def encode_thumb(self, img: Image.Image) -> bytes:
        thumb = resize_short_side(img.convert("RGB"), self._settings.image_thumb_short_side)
        return _webp_bytes(thumb, self._settings.image_thumb_quality)

    def encode_webp(self, img: Image.Image) -> bytes:
        img = resize_short_side(img.convert("RGB"), self._settings.image_max_short_side)
        quality = self._settings.image_webp_quality
        data = _webp_bytes(img, quality)
        while len(data) > self._settings.image_target_max_bytes and quality > self._settings.image_min_quality:
            quality = max(self._settings.image_min_quality, quality - 10)
            data = _webp_bytes(img, quality)
        # 품질 하한에서도 크면 해상도를 한 단계 낮춤
        if len(data) > self._settings.image_target_max_bytes:
            img = resize_short_side(img, int(min(img.size) * 0.8))
            data = _webp_bytes(img, quality)
        return data


def sharpest(candidates: list[FrameCandidate]) -> FrameCandidate:
    return max(candidates, key=lambda c: c.sharpness)


def discard(candidates: list[FrameCandidate]) -> None:
    for candidate in candidates:
        candidate.path.unlink(missing_ok=True)


def _describe_frame(ts: float, path: Path) -> FrameCandidate:
    with Image.open(path) as img:
        frame = ImageOps.exif_transpose(img).convert("RGB")
    preview = frame.copy()
    preview.thumbnail((PREVIEW_MAX_SIDE, PREVIEW_MAX_SIDE))
    buf = io.BytesIO()
    preview.save(buf, format="JPEG", quality=PREVIEW_JPEG_QUALITY)
    return FrameCandidate(timestamp_sec=ts, path=path, sharpness=sharpness_score(frame), preview=buf.getvalue())


def resize_short_side(img: Image.Image, max_short_side: int) -> Image.Image:
    width, height = img.size
    short = min(width, height)
    if short <= max_short_side:
        return img
    scale = max_short_side / short
    return img.resize((max(1, round(width * scale)), max(1, round(height * scale))), Image.Resampling.LANCZOS)


def sharpness_score(img: Image.Image) -> float:
    """엣지 강도의 분산 — 클수록 선명. 계산량을 줄이려고 축소본으로 측정."""
    small = img.convert("L")
    small.thumbnail((320, 320))
    edges = small.filter(ImageFilter.FIND_EDGES)
    return float(ImageStat.Stat(edges).var[0])


def _webp_bytes(img: Image.Image, quality: int) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=quality, method=6)
    return buf.getvalue()


def _clamp_ts(ts: float, duration: float | None) -> float:
    ts = max(0.0, ts)
    if duration:
        ts = min(ts, max(0.0, duration - 0.2))
    return ts
