"""yt-dlp 기반 저화질(360p 이하) 영상 다운로더.

- Gemini 분석과 스틸컷 캡처에는 고화질이 필요 없으므로 360p 이하 + 최저 오디오로 받아
  Render 무료 인스턴스(대역폭/디스크/메모리)를 아낀다.
- 오디오는 상품명 음성 인식에 중요하므로 반드시 함께 받는다 (Gemini 업로드용 mp4 머지).
- 길이 제한은 메타데이터 조회 단계에서 먼저 검사해 불필요한 다운로드를 막는다.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yt_dlp
from yt_dlp.utils import DownloadError as YtDlpDownloadError

from app.config import Settings

logger = logging.getLogger(__name__)

# 360p 이하 video+audio → 360p 이하 단일 파일 → 최저 화질 video+audio → 최저 화질 단일 파일
FORMAT_SELECTOR = "bv*[height<=360]+ba/b[height<=360]/wv*+wa/w"
# 짧은 영상(쇼츠·릴스)은 확대용 스틸컷을 위해 720p 까지 (용량 부담이 작음). 없으면 위 규칙으로 내려감
FORMAT_SELECTOR_HD = f"bv*[height<=720]+ba/b[height<=720]/{FORMAT_SELECTOR}"
MAX_FILESIZE_BYTES = 200 * 1024 * 1024


class DownloadError(RuntimeError):
    """영상 다운로드 실패 (비공개/삭제/지역 제한/봇 차단 등)."""


class VideoTooLongError(RuntimeError):
    def __init__(self, duration: int, limit: int) -> None:
        super().__init__(f"영상 길이 {duration}초가 제한 {limit}초를 초과합니다.")
        self.duration = duration
        self.limit = limit


class NoVideoError(RuntimeError):
    """영상이 없는 게시글 (사진 전용 게시물 등)."""


@dataclass
class VideoMeta:
    extractor_id: str
    title: str
    uploader: str
    duration: int | None
    webpage_url: str


@dataclass
class DownloadedVideo:
    path: Path
    meta: VideoMeta


class VideoDownloader:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._cookie_file: str | None = None
        if settings.ytdlp_cookies_b64:
            tmp = tempfile.NamedTemporaryFile(prefix="linktem-cookies-", suffix=".txt", delete=False)
            tmp.write(base64.b64decode(settings.ytdlp_cookies_b64))
            tmp.close()
            self._cookie_file = tmp.name

    def _base_opts(self) -> dict[str, Any]:
        opts: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "noplaylist": True,
            "socket_timeout": 30,
            "retries": 3,
            "fragment_retries": 3,
            "concurrent_fragment_downloads": 4,
            "geo_bypass": True,
            "http_headers": {"Accept-Language": "ko-KR,ko;q=0.9,en;q=0.6"},
        }
        if self._settings.ytdlp_proxy:
            opts["proxy"] = self._settings.ytdlp_proxy
        if self._cookie_file:
            opts["cookiefile"] = self._cookie_file
        return opts

    async def download(self, url: str, workdir: Path) -> DownloadedVideo:
        """메타데이터 조회 → 길이 검사 → 다운로드(짧은 영상 720p, 그 외 360p). 동기 yt-dlp 는 스레드에서 실행."""
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._download_sync, url, workdir),
                timeout=self._settings.download_timeout_sec,
            )
        except asyncio.TimeoutError as exc:
            raise DownloadError("영상 다운로드 시간이 초과되었습니다.") from exc

    def _download_sync(self, url: str, workdir: Path) -> DownloadedVideo:
        opts = {
            **self._base_opts(),
            "format": FORMAT_SELECTOR,
            "merge_output_format": "mp4",
            "outtmpl": str(workdir / "video.%(ext)s"),
            "max_filesize": MAX_FILESIZE_BYTES,
            "paths": {"home": str(workdir), "temp": str(workdir)},
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if info is None:
                    raise DownloadError("영상 정보를 가져오지 못했습니다.")
                if info.get("_type") == "playlist":
                    entries = [e for e in (info.get("entries") or []) if e and e.get("vcodec") != "none"]
                    if not entries:
                        raise NoVideoError("영상이 포함되지 않은 게시글입니다.")
                    info = entries[0]

                meta = _meta_from_info(info)
                limit = self._settings.max_video_duration_sec
                if meta.duration and meta.duration > limit:
                    raise VideoTooLongError(meta.duration, limit)
                if not info.get("formats") and not info.get("url"):
                    raise NoVideoError("영상이 포함되지 않은 게시글입니다.")

                if meta.duration and meta.duration <= self._settings.download_hd_max_duration_sec:
                    # 포맷 선택은 process_ie_result 에서 다시 이뤄지므로 선택기만 바꿔 끼운다
                    ydl.format_selector = ydl.build_format_selector(FORMAT_SELECTOR_HD)
                info = ydl.process_ie_result(info, download=True)
        except (VideoTooLongError, NoVideoError, DownloadError):
            raise
        except YtDlpDownloadError as exc:
            logger.warning("yt-dlp download failed: %s", exc)
            raise DownloadError(_friendly_ytdlp_error(str(exc))) from exc

        path = _resolve_output_path(info, workdir)
        if path is None or not path.exists() or path.stat().st_size == 0:
            raise DownloadError("다운로드된 영상 파일을 찾을 수 없습니다.")
        logger.info("downloaded %s (%.1f MB)", meta.extractor_id, path.stat().st_size / 1_048_576)
        return DownloadedVideo(path=path, meta=meta)


def _meta_from_info(info: dict[str, Any]) -> VideoMeta:
    duration = info.get("duration")
    return VideoMeta(
        extractor_id=str(info.get("id") or ""),
        title=str(info.get("title") or info.get("description") or "")[:300],
        uploader=str(info.get("uploader") or info.get("channel") or info.get("uploader_id") or "")[:120],
        duration=int(duration) if duration else None,
        webpage_url=str(info.get("webpage_url") or ""),
    )


def _resolve_output_path(info: dict[str, Any], workdir: Path) -> Path | None:
    for download in info.get("requested_downloads") or []:
        filepath = download.get("filepath")
        if filepath and Path(filepath).exists():
            return Path(filepath)
    candidates = sorted(
        (p for p in workdir.glob("video.*") if p.suffix not in (".part", ".ytdl")),
        key=lambda p: p.stat().st_size,
        reverse=True,
    )
    return candidates[0] if candidates else None


def _friendly_ytdlp_error(message: str) -> str:
    lowered = message.lower()
    if "private" in lowered or "login" in lowered or "sign in" in lowered:
        return "비공개이거나 로그인이 필요한 영상입니다."
    if "not available" in lowered or "removed" in lowered or "404" in lowered:
        return "삭제되었거나 볼 수 없는 영상입니다."
    if "confirm you" in lowered and "bot" in lowered:
        return "영상 플랫폼이 일시적으로 요청을 차단했습니다. 잠시 후 다시 시도해 주세요."
    if "geo" in lowered or "country" in lowered:
        return "지역 제한이 걸린 영상입니다."
    return "영상을 다운로드하지 못했습니다."
