"""후보 프레임 중 '그 상품이 실제로 보이는' 프레임 고르기 — 경량 Gemini 모델 1회 호출로 영상의 모든 상품을 처리.

- 분석 모델(Flash)과 다른 모델(Flash-Lite)을 써서 무료 한도를 따로 쓴다 (한도는 모델별로 집계).
- 실패(한도 초과·오류·시간 초과)하면 None 을 돌려주고, 호출 측은 가장 선명한 프레임으로 대체한다.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any

from google import genai
from google.genai import types

from app.config import Settings

logger = logging.getLogger(__name__)

SYSTEM_INSTRUCTION = """당신은 쇼핑 영상의 스틸컷을 고르는 편집자입니다.
상품마다 영상에서 연달아 캡처한 후보 프레임 여러 장이 주어집니다.
각 상품에 대해 그 상품(포장, 라벨, 본체)이 가장 크고 선명하게, 다른 물건에 가려지지 않고 보이는 후보 번호를 고르세요.
- 상품명과 다른 제품, 사람 얼굴만 나온 장면, 매장 전경은 고르지 않습니다.
- 어느 후보에도 그 상품이 보이지 않으면 best 를 -1 로 합니다."""

RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "choices": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "product": {"type": "INTEGER", "description": "상품 번호 (1부터)"},
                    "best": {"type": "INTEGER", "description": "가장 잘 보이는 후보 번호 (0부터), 없으면 -1"},
                },
                "required": ["product", "best"],
            },
        }
    },
    "required": ["choices"],
}


@dataclass
class FrameQuery:
    name_ko: str
    name_en: str
    # 후보 미리보기 JPEG (시간 순)
    previews: list[bytes]


class FrameSelector:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = (
            genai.Client(api_key=settings.gemini_api_key)
            if settings.gemini_api_key and settings.frame_selection_model
            else None
        )

    @property
    def enabled(self) -> bool:
        return self._client is not None

    async def choose(self, queries: list[FrameQuery]) -> list[int | None] | None:
        """상품별 선택 후보 인덱스 (보이는 후보가 없으면 None). 호출 자체가 실패하면 None."""
        if self._client is None or not queries:
            return None
        if all(len(q.previews) <= 1 for q in queries):
            return [0 if q.previews else None for q in queries]

        parts: list[types.Part] = []
        for number, query in enumerate(queries, start=1):
            parts.append(types.Part.from_text(text=f"[상품 {number}] {query.name_ko} / {query.name_en}"))
            for idx, preview in enumerate(query.previews):
                parts.append(types.Part.from_text(text=f"상품 {number} 후보 {idx}"))
                parts.append(types.Part.from_bytes(data=preview, mime_type="image/jpeg"))
        parts.append(types.Part.from_text(text="모든 상품에 대해 choices 를 반환하세요."))

        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=0.0,
            response_mime_type="application/json",
            response_schema=RESPONSE_SCHEMA,
            max_output_tokens=2048,
            media_resolution=types.MediaResolution.MEDIA_RESOLUTION_LOW,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        try:
            response = await asyncio.wait_for(
                self._client.aio.models.generate_content(
                    model=self._settings.frame_selection_model,
                    contents=[types.Content(role="user", parts=parts)],
                    config=config,
                ),
                timeout=self._settings.frame_selection_timeout_sec,
            )
            return parse_choices(response.text or "", [len(q.previews) for q in queries])
        except Exception as exc:  # noqa: BLE001 — 프레임 선택은 품질 개선용, 실패하면 선명도 기준으로 대체
            logger.warning("frame selection failed (%s) — falling back to sharpness", exc)
            return None


def parse_choices(text: str, candidate_counts: list[int]) -> list[int | None]:
    """모델 응답 → 상품별 인덱스. 범위를 벗어나거나 빠진 상품은 None (선명도 기준으로 대체)."""
    data = json.loads(text)
    result: list[int | None] = [None] * len(candidate_counts)
    for choice in data.get("choices") or []:
        try:
            product = int(choice["product"]) - 1
            best = int(choice["best"])
        except (KeyError, TypeError, ValueError):
            continue
        if 0 <= product < len(candidate_counts) and 0 <= best < candidate_counts[product]:
            result[product] = best
    return result
