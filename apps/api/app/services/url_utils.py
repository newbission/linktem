"""SNS URL 정규화 & 플랫폼 화이트리스트.

같은 영상이 `youtu.be/ID`, `youtube.com/shorts/ID`, `m.youtube.com/watch?v=ID&si=...` 처럼
여러 형태로 공유되므로, 캐시 키(canonical_key)를 하나로 모아야 Gemini 호출을 아낄 수 있다.
yt-dlp 의 generic extractor 를 통한 SSRF 를 막기 위해 지원 플랫폼 외 URL 은 거부한다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

_YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"}
_INSTAGRAM_HOSTS = {"instagram.com", "www.instagram.com", "m.instagram.com"}
_TIKTOK_HOSTS = {"tiktok.com", "www.tiktok.com", "m.tiktok.com", "vt.tiktok.com", "vm.tiktok.com"}

_YT_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_URL_IN_TEXT = re.compile(r"https?://[^\s<>\"']+")


class UnsupportedUrlError(ValueError):
    """지원하지 않는 플랫폼이거나 영상 ID 를 찾을 수 없는 URL."""


@dataclass(frozen=True)
class VideoTarget:
    platform: str  # youtube | instagram | tiktok
    canonical_key: str  # 캐시 키 (예: youtube:dQw4w9WgXcQ)
    url: str  # yt-dlp / Gemini 에 넘길 정규화 URL


def extract_first_url(text: str) -> str | None:
    """공유 텍스트("이 영상 봐봐! https://...")에서 첫 URL 을 꺼낸다."""
    match = _URL_IN_TEXT.search(text or "")
    if not match:
        return None
    return match.group(0).rstrip(").,!?]}>")


def normalize_video_url(raw: str) -> VideoTarget:
    url = extract_first_url(raw) if not raw.lower().startswith(("http://", "https://")) else raw.strip()
    if not url:
        raise UnsupportedUrlError("URL 형식이 아닙니다.")

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise UnsupportedUrlError("http(s) URL 만 지원합니다.")
    host = (parsed.hostname or "").lower()
    path_parts = [p for p in parsed.path.split("/") if p]

    if host in _YOUTUBE_HOSTS:
        return _normalize_youtube(host, path_parts, parse_qs(parsed.query))
    if host in _INSTAGRAM_HOSTS:
        return _normalize_instagram(path_parts)
    if host in _TIKTOK_HOSTS:
        return _normalize_tiktok(host, path_parts, url)

    raise UnsupportedUrlError("유튜브, 인스타그램, 틱톡 링크만 지원합니다.")


def _normalize_youtube(host: str, parts: list[str], query: dict[str, list[str]]) -> VideoTarget:
    video_id: str | None = None
    if host == "youtu.be":
        video_id = parts[0] if parts else None
    elif parts and parts[0] == "watch":
        video_id = (query.get("v") or [None])[0]
    elif len(parts) >= 2 and parts[0] in ("shorts", "embed", "live", "v"):
        video_id = parts[1]

    if not video_id or not _YT_ID.match(video_id):
        raise UnsupportedUrlError("유튜브 영상 ID 를 찾을 수 없습니다.")
    return VideoTarget(
        platform="youtube",
        canonical_key=f"youtube:{video_id}",
        url=f"https://www.youtube.com/watch?v={video_id}",
    )


def _normalize_instagram(parts: list[str]) -> VideoTarget:
    # /reel/{code}, /reels/{code}, /p/{code}, /tv/{code}, /{username}/reel/{code}
    for i, part in enumerate(parts):
        if part in ("reel", "reels", "p", "tv") and i + 1 < len(parts):
            code = parts[i + 1]
            if re.match(r"^[A-Za-z0-9_-]{5,}$", code):
                kind = "reel" if part in ("reel", "reels") else part
                return VideoTarget(
                    platform="instagram",
                    canonical_key=f"instagram:{code}",
                    url=f"https://www.instagram.com/{kind}/{code}/",
                )
    raise UnsupportedUrlError("인스타그램 게시물/릴스 링크가 아닙니다.")


def _normalize_tiktok(host: str, parts: list[str], url: str) -> VideoTarget:
    # https://www.tiktok.com/@user/video/{id}
    if len(parts) >= 3 and parts[0].startswith("@") and parts[1] in ("video", "photo"):
        video_id = parts[2]
        if video_id.isdigit():
            return VideoTarget(
                platform="tiktok",
                canonical_key=f"tiktok:{video_id}",
                url=f"https://www.tiktok.com/{parts[0]}/video/{video_id}",
            )
    # 단축 링크(vt./vm.tiktok.com/XXXX)는 리다이렉트 후 ID 가 확정되므로 임시 키 사용.
    # analyzer 가 yt-dlp 메타데이터의 실제 ID 로 canonical_key 를 재확정한다.
    if host in ("vt.tiktok.com", "vm.tiktok.com") and parts:
        return VideoTarget(platform="tiktok", canonical_key=f"tiktok-short:{parts[0]}", url=url.split("?")[0])
    raise UnsupportedUrlError("틱톡 영상 링크가 아닙니다.")


def canonical_key_from_info(platform: str, extractor_id: str | None) -> str | None:
    """yt-dlp 메타데이터의 id 로 확정 키를 만든다 (단축 링크 보정용)."""
    if not extractor_id:
        return None
    return f"{platform}:{extractor_id}"


def youtube_timestamp_url(source_url: str, seconds: float) -> str:
    sep = "&" if "?" in source_url else "?"
    return f"{source_url}{sep}t={int(seconds)}s"
