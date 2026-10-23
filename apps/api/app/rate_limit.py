"""인메모리 슬라이딩 윈도우 레이트 리밋 + 익명 클라이언트 해시.

Render 무료 플랜은 단일 인스턴스이므로 프로세스 메모리로 충분하다 (Redis 불필요 → 0원 유지).
"""

from __future__ import annotations

import hashlib
import time
from collections import defaultdict, deque

from fastapi import Request


def client_ip(request: Request) -> str:
    # Render/Cloudflare 프록시 뒤: X-Forwarded-For 의 첫 번째가 실제 클라이언트
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def client_hash(request: Request, salt: str) -> str:
    """IP + User-Agent 를 솔트와 함께 해시. 원문은 저장하지 않는다."""
    raw = f"{salt}|{client_ip(request)}|{request.headers.get('user-agent', '')}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


class SlidingWindowLimiter:
    def __init__(self, limit: int, window_sec: float = 60.0, max_keys: int = 10_000) -> None:
        self._limit = limit
        self._window = window_sec
        self._max_keys = max_keys
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def hit(self, key: str) -> tuple[bool, int]:
        """요청 1건 기록. (허용 여부, 재시도까지 남은 초) 반환."""
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] > self._window:
            hits.popleft()
        if len(hits) >= self._limit:
            retry_after = int(self._window - (now - hits[0])) + 1
            return False, retry_after
        hits.append(now)
        if len(self._hits) > self._max_keys:
            self._evict(now)
        return True, 0

    def _evict(self, now: float) -> None:
        stale = [k for k, v in self._hits.items() if not v or now - v[-1] > self._window]
        for key in stale:
            del self._hits[key]
