"""@linktem/types (packages/types/src/index.ts) 와 1:1 대응하는 Pydantic 모델.

필드를 바꿀 때는 반드시 TS 원본을 먼저 수정하고, tests/test_contract.py 로 일치 여부를 확인한다.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

FeedbackType = Literal[
    "SAME", "WRONG_PRODUCT", "NOT_IN_VIDEO", "WRONG_IMAGE", "WRONG_RETAILER", "WRONG_DETAIL", "DUPLICATE"
]
# '다른 제품' 판정 계열 — 숨김 임계치와 앙상블 감점에 쓰인다
IDENTITY_NEGATIVE_TYPES: tuple[str, ...] = ("WRONG_PRODUCT", "NOT_IN_VIDEO")

SHOPPING_CATEGORIES: tuple[str, ...] = (
    "신선식품",
    "가공식품",
    "음료/주류",
    "생활용품",
    "주방용품",
    "뷰티",
    "가전/디지털",
    "패션",
    "기타",
)


# ---------------------------------------------------------------------------
# 분석 요청 / 응답
# ---------------------------------------------------------------------------


class VideoAnalysisRequest(BaseModel):
    url: str = Field(..., min_length=8, max_length=2048)

    @field_validator("url")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


class ShoppingItem(BaseModel):
    id: str
    name_ko: str
    name_en: str
    category: str
    timestamp_sec: float
    image_url: str
    retailer: str
    is_checked: bool = False
    edition_note: Optional[str] = None
    thumb_url: Optional[str] = None
    reason: Optional[str] = None
    caution: Optional[str] = None


class VideoAnalysisResponse(BaseModel):
    video_id: str
    source_title: str
    creator_name: str
    analysis_count: int
    is_locked: bool
    items: list[ShoppingItem]
    source_url: Optional[str] = None
    summary: Optional[str] = None
    thumb_url: Optional[str] = None


# ---------------------------------------------------------------------------
# 백그라운드 분석 작업
# ---------------------------------------------------------------------------

AnalysisJobStatus = Literal["queued", "running", "done", "failed"]
AnalysisJobStage = Literal["queued", "downloading", "analyzing", "capturing", "saving", "done", "failed"]


class AnalysisJob(BaseModel):
    job_id: str
    source_url: str
    status: AnalysisJobStatus
    stage: AnalysisJobStage
    error: Optional[str] = None
    error_code: Optional[int] = None
    video_id: Optional[str] = None
    created_at: str
    updated_at: str


class AnalyzeResponse(BaseModel):
    job: Optional[AnalysisJob] = None
    video: Optional[VideoAnalysisResponse] = None


class VideoLookupResponse(BaseModel):
    videos: list[VideoAnalysisResponse]


# ---------------------------------------------------------------------------
# 피드백
# ---------------------------------------------------------------------------


class UserFeedbackRequest(BaseModel):
    item_id: str = Field(..., min_length=1, max_length=64)
    feedback_type: FeedbackType
    cancel: Optional[bool] = None
    comment: Optional[str] = Field(default=None, max_length=300)


class UserFeedbackResponse(BaseModel):
    item_id: str
    same_count: int
    different_count: int
    is_hidden: bool
    report_counts: dict[str, int]
    image_reset: bool


# ---------------------------------------------------------------------------
# 관련 영상
# ---------------------------------------------------------------------------


class RelatedVideo(BaseModel):
    other_item_id: str
    video_id: str
    source_title: str
    creator_name: str
    source_url: str


class RelatedVideosResponse(BaseModel):
    items: dict[str, list[RelatedVideo]]


class RelatedUnlinkRequest(BaseModel):
    item_id: str = Field(..., min_length=1, max_length=64)
    other_item_id: str = Field(..., min_length=1, max_length=64)


class RelatedUnlinkResponse(BaseModel):
    item_id: str
    other_item_id: str
    unlinked: bool


# ---------------------------------------------------------------------------
# 공통
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    version: str
    time: str


class CleanupResponse(BaseModel):
    superseded_deleted: int
    expired_videos: int
    expired_images: int
    jobs_deleted: int = 0
