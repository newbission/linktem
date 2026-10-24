"""스틸컷 이미지 파이프라인: ffmpeg 프레임 캡처 → 가장 선명한 프레임 → 확대용 + 썸네일 WebP 두 장.

- 지정 시점 ±0.4초 3프레임을 캡처해 가장 선명한(엣지 분산이 큰) 프레임을 고른다.
  손떨림/모션블러가 심한 쇼츠 영상에서 품질 차이가 크다.
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

CAPTURE_OFFSETS = (0.0, -0.4, 0.4)
FFMPEG_TIMEOUT_SEC = 30


class ImageProcessingError(RuntimeError):
    pass


@dataclass
class CapturedImage:
    full: bytes
    thumb: bytes


class ImageProcessor:
    def __init__(self, settings: Settings, max_concurrency: int = 3) -> None:
        self._settings = settings
        self._ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
        self._semaphore = asyncio.Semaphore(max_concurrency)

    async def capture_webp(
        self,
        video_path: Path,
        timestamp_sec: float,
        workdir: Path,
        duration: float | None = None,
    ) -> CapturedImage:
        """timestamp_sec 근처의 가장 선명한 프레임을 확대용·썸네일 WebP 로 반환."""
        async with self._semaphore:
            frames: list[Path] = []
            for idx, offset in enumerate(CAPTURE_OFFSETS):
                ts = _clamp_ts(timestamp_sec + offset, duration)
                out = workdir / f"frame-{timestamp_sec:.2f}-{idx}.png"
                if await self._extract_frame(video_path, ts, out):
                    frames.append(out)
            if not frames:
                # 타임스탬프가 영상 끝을 넘긴 경우 등: 0초 근처로 한 번 더 시도
                out = workdir / f"frame-{timestamp_sec:.2f}-fallback.png"
                if await self._extract_frame(video_path, 0.0, out):
                    frames.append(out)
            if not frames:
                raise ImageProcessingError(f"{timestamp_sec}초 프레임을 캡처하지 못했습니다.")
            try:
                return await asyncio.to_thread(self._select_and_encode, frames)
            finally:
                for frame in frames:
                    frame.unlink(missing_ok=True)

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

    def _select_and_encode(self, frames: list[Path]) -> CapturedImage:
        best_img: Image.Image | None = None
        best_score = -1.0
        for frame in frames:
            with Image.open(frame) as img:
                img = ImageOps.exif_transpose(img).convert("RGB")
                score = sharpness_score(img)
                if score > best_score:
                    best_img, best_score = img.copy(), score
        assert best_img is not None
        return CapturedImage(full=self.encode_webp(best_img), thumb=self.encode_thumb(best_img))

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
