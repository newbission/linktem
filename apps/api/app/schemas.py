"""@linktem/types (packages/types/src/index.ts) 와 1:1 대응하는 Pydantic 모델.

필드를 바꿀 때는 반드시 TS 원본을 먼저 수정하고, tests/test_contract.py 로 일치 여부를 확인한다.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

FeedbackType = Literal["SAME", "DIFFERENT"]

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


class VideoAnalysisResponse(BaseModel):
    video_id: str
    source_title: str
    creator_name: str
    analysis_count: int
    is_locked: bool
    items: list[ShoppingItem]
    source_url: Optional[str] = None


# ---------------------------------------------------------------------------
# 피드백
# ---------------------------------------------------------------------------


class UserFeedbackRequest(BaseModel):
    item_id: str = Field(..., min_length=1, max_length=64)
    feedback_type: FeedbackType


class UserFeedbackResponse(BaseModel):
    item_id: str
    same_count: int
    different_count: int
    is_hidden: bool


# ---------------------------------------------------------------------------
# 관련 영상
# ---------------------------------------------------------------------------


class RelatedVideo(BaseModel):
    video_id: str
    source_title: str
    creator_name: str
    source_url: str


class RelatedVideosResponse(BaseModel):
    items: dict[str, list[RelatedVideo]]


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
