"""Linktem API — FastAPI 엔트리포인트."""

from __future__ import annotations

import hmac
import logging
import mimetypes
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncIterator

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.config import Settings, get_settings
from app.db import create_pool
from app.rate_limit import SlidingWindowLimiter, client_hash, client_ip
from app.schemas import (
    AnalyzeResponse,
    CleanupResponse,
    HealthResponse,
    RelatedVideosResponse,
    UserFeedbackRequest,
    UserFeedbackResponse,
    VideoAnalysisRequest,
    VideoLookupResponse,
)
from app.services.analyzer import MAX_LOOKUP_IDS, AnalysisError, Analyzer
from app.services.downloader import VideoDownloader
from app.services.gemini import GeminiAnalyzer
from app.services.image_processor import ImageProcessor
from app.services.storage import LocalStorage, create_storage, cleanup_expired_images

# slim 이미지에는 /etc/mime.types 가 없어 .webp 를 octet-stream 으로 내보내는 문제 방지
mimetypes.add_type("image/webp", ".webp")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("linktem")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    pool = await create_pool(settings)
    storage = app.state.storage
    app.state.settings = settings
    app.state.pool = pool
    app.state.storage = storage
    app.state.analyzer = Analyzer(
        settings=settings,
        pool=pool,
        downloader=VideoDownloader(settings),
        gemini=GeminiAnalyzer(settings),
        images=ImageProcessor(settings),
        storage=storage,
    )
    app.state.analyze_limiter = SlidingWindowLimiter(settings.analyze_rate_limit_per_min)
    app.state.feedback_limiter = SlidingWindowLimiter(30)
    await app.state.analyzer.fail_interrupted_jobs()
    logger.info("Linktem API %s started (env=%s, db=%s)", __version__, settings.app_env, pool is not None)
    try:
        yield
    finally:
        # 실행 중 작업을 먼저 실패로 기록한 뒤 DB 풀을 닫는다
        await app.state.analyzer.cancel_jobs()
        if pool is not None:
            await pool.close()


_settings = get_settings()
app = FastAPI(
    title="Linktem API",
    version=__version__,
    description="SNS 영상/게시글 → 장보기 체크리스트 자동 생성",
    lifespan=lifespan,
    docs_url=None if _settings.app_env == "production" else "/docs",
    redoc_url=None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origins,
    allow_origin_regex=r"https://linktem(-[a-z0-9-]+)?\.vercel\.app",  # Vercel 프리뷰 배포
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
    max_age=86400,
)
app.add_middleware(GZipMiddleware, minimum_size=1024)


class ImmutableStaticFiles(StaticFiles):
    """키에 랜덤 접미사가 있어 내용이 바뀌지 않으므로 1년 캐시."""

    def file_response(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response


# 저장소는 라우트 마운트가 필요해 앱 생성 시점에 만든다 (local 이면 /media 정적 서빙)
app.state.storage = create_storage(_settings)
if isinstance(app.state.storage, LocalStorage):
    app.mount(
        _settings.local_storage_public_path.rstrip("/"),
        ImmutableStaticFiles(directory=app.state.storage.root),
        name="media",
    )


@app.exception_handler(AnalysisError)
async def _analysis_error_handler(_: Request, exc: AnalysisError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


def get_analyzer(request: Request) -> Analyzer:
    return request.app.state.analyzer


def settings_dep() -> Settings:
    return get_settings()


def _enforce_rate_limit(limiter: SlidingWindowLimiter, request: Request) -> None:
    allowed, retry_after = limiter.hit(client_ip(request))
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="요청이 너무 많아요. 잠시 후 다시 시도해 주세요.",
            headers={"Retry-After": str(retry_after)},
        )


# ---------------------------------------------------------------------------
# routes
# ---------------------------------------------------------------------------


@app.get("/health", response_model=HealthResponse, tags=["ops"])
@app.head("/health", include_in_schema=False)
async def health() -> HealthResponse:
    """UptimeRobot 슬립 방지용. DB 등 외부 의존성 없이 즉시 응답."""
    return HealthResponse(version=__version__, time=datetime.now(timezone.utc).isoformat())


@app.post("/api/analyze", response_model=AnalyzeResponse, response_model_exclude_none=True, tags=["analyze"])
async def analyze(
    body: VideoAnalysisRequest,
    request: Request,
    background: BackgroundTasks,
    analyzer: Analyzer = Depends(get_analyzer),
    settings: Settings = Depends(settings_dep),
) -> AnalyzeResponse:
    """이미 분석된 영상은 video 를 즉시, 처음 보는 영상은 job 을 즉시 반환 (분석은 백그라운드)."""
    _enforce_rate_limit(request.app.state.analyze_limiter, request)
    return await analyzer.analyze(body.url, client_hash(request, settings.client_hash_salt), background)


@app.get("/api/jobs/{job_id}", response_model=AnalyzeResponse, response_model_exclude_none=True, tags=["analyze"])
async def get_job(job_id: str, response: Response, analyzer: Analyzer = Depends(get_analyzer)) -> AnalyzeResponse:
    """진행 상황 조회 (2~3초 간격 폴링용, 레이트 리밋 없음). 완료되면 video 포함."""
    response.headers["Cache-Control"] = "no-store"
    return await analyzer.get_job(job_id)


@app.get("/api/videos", response_model=VideoLookupResponse, tags=["analyze"])
async def lookup_videos(
    response: Response,
    ids: str = Query(..., description="쉼표로 구분한 video_id 목록", max_length=40 * MAX_LOOKUP_IDS),
    analyzer: Analyzer = Depends(get_analyzer),
) -> VideoLookupResponse:
    """리스트에 있는 영상의 최신 결과 (백그라운드 앙상블 개선분 반영). 회차를 올리지 않는 조회 전용."""
    response.headers["Cache-Control"] = "no-store"
    videos = await analyzer.lookup_videos([i.strip() for i in ids.split(",") if i.strip()])
    return VideoLookupResponse(videos=videos)


@app.post("/api/feedback", response_model=UserFeedbackResponse, tags=["feedback"])
async def feedback(
    body: UserFeedbackRequest,
    request: Request,
    analyzer: Analyzer = Depends(get_analyzer),
    settings: Settings = Depends(settings_dep),
) -> UserFeedbackResponse:
    _enforce_rate_limit(request.app.state.feedback_limiter, request)
    return await analyzer.submit_feedback(
        body.item_id, body.feedback_type, client_hash(request, settings.client_hash_salt)
    )


@app.get("/api/videos/{video_id}/related", response_model=RelatedVideosResponse, tags=["analyze"])
async def related_videos(video_id: str, analyzer: Analyzer = Depends(get_analyzer)) -> RelatedVideosResponse:
    return await analyzer.related(video_id)


@app.post("/api/admin/cleanup", response_model=CleanupResponse, tags=["ops"])
async def admin_cleanup(
    request: Request,
    x_admin_token: str = Header(default=""),
    settings: Settings = Depends(settings_dep),
) -> CleanupResponse:
    if not settings.admin_token or not hmac.compare_digest(x_admin_token, settings.admin_token):
        raise HTTPException(status_code=401, detail="unauthorized")
    pool = request.app.state.pool
    if pool is None:
        raise HTTPException(status_code=503, detail="데이터베이스가 설정되지 않았습니다.")
    result = await cleanup_expired_images(request.app.state.storage, pool, settings)
    return CleanupResponse(**result)
