"""Gemini 3.8 Flash 영상 분석 — JSON Schema 구조화 출력으로 상품 목록 추출.

입력 경로 두 가지:
- 유튜브: Gemini 가 공개 유튜브 URL 을 직접 읽음 (업로드 생략, 다운로드와 병렬 실행 가능)
- 그 외(인스타그램/틱톡) 또는 유튜브 URL 실패 시: 다운로드한 mp4 를 Files API 로 업로드
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import BaseModel, Field, ValidationError

from app.config import Settings
from app.schemas import SHOPPING_CATEGORIES

logger = logging.getLogger(__name__)

MAX_ITEMS = 30
# 메모는 카드에 한두 줄로 보여주므로 길게 받지 않는다
MAX_NOTE_CHARS = 120
MAX_SUMMARY_CHARS = 160

RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "summary": {
            "type": "STRING",
            "nullable": True,
            "description": (
                "영상 전체 내용을 한두 문장(80자 이내)으로 요약. 어디서 무엇을 샀고 어떤 영상인지. "
                "예: '트레이더 조에서 산 간식·소스 20가지 하울, 재구매템 위주로 소개'"
            ),
        },
        "items": {
            "type": "ARRAY",
            "description": "영상에 등장하거나 언급된 구매 가능한 상품 목록 (등장 순서대로)",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "name_ko": {
                        "type": "STRING",
                        "description": "포장/라벨에 적힌 브랜드 + 제품명 (한국어). 예: '비비고 왕교자'",
                    },
                    "name_en": {
                        "type": "STRING",
                        "description": "영문 제품명 (브랜드 포함, 로마자 표기 가능). 예: 'Bibigo Wang Gyoza'",
                    },
                    "category": {"type": "STRING", "enum": list(SHOPPING_CATEGORIES)},
                    "timestamp_sec": {
                        "type": "NUMBER",
                        "description": "제품 포장 정면이 가장 선명하게 보이는 시점 (영상 시작 기준 초)",
                    },
                    "retailer": {
                        "type": "STRING",
                        "description": "구매처 (예: 이마트, 코스트코, 쿠팡, 다이소, 올리브영). 단서가 없으면 '기타/미상'",
                    },
                    "edition_note": {
                        "type": "STRING",
                        "nullable": True,
                        "description": "용량/맛/한정판/색상 등 같은 제품 내 구분 정보. 없으면 null",
                    },
                    "reason": {
                        "type": "STRING",
                        "nullable": True,
                        "description": (
                            "영상에서 말한 추천 이유·특징·사용 후기를 한 문장(60자 이내)으로 요약. "
                            "예: '물만 부으면 되고 국물이 진해서 캠핑용으로 최고'. 언급이 없으면 null (지어내지 말 것)"
                        ),
                    },
                    "caution": {
                        "type": "STRING",
                        "nullable": True,
                        "description": (
                            "비슷한 제품과 헷갈리지 않도록 살 때 확인할 점 한 문장(60자 이내). "
                            "화자가 강조한 내용이나 포장으로 구별되는 점. "
                            "예: '빨간 뚜껑 오리지널 (매운맛 아님)', '1kg 대용량만 이 가격'. 없으면 null"
                        ),
                    },
                    "confidence": {
                        "type": "NUMBER",
                        "description": "제품 식별 확신도 0.0~1.0",
                    },
                },
                "required": ["name_ko", "name_en", "category", "timestamp_sec", "retailer", "confidence"],
                "propertyOrdering": [
                    "name_ko",
                    "name_en",
                    "category",
                    "timestamp_sec",
                    "retailer",
                    "edition_note",
                    "reason",
                    "caution",
                    "confidence",
                ],
            },
        }
    },
    "required": ["items"],
    "propertyOrdering": ["summary", "items"],
}

SYSTEM_INSTRUCTION = """당신은 한국 SNS 쇼핑 영상(장보기 하울, 살림템, 추천템)을 분석해 장보기 체크리스트를 만드는 전문가입니다.
영상의 화면(포장, 라벨, 가격표, 매장 간판, 장바구니)과 음성/자막을 모두 사용해 시청자가 실제로 살 수 있는 상품을 찾으세요.

규칙:
1. 구매 가능한 개별 상품만 포함합니다. 사람, 매장 인테리어, 이미 조리된 음식, 배경 소품은 제외합니다.
2. 같은 상품이 여러 번 나오면 한 번만 포함하고, 포장 정면이 가장 선명한 시점을 timestamp_sec 으로 고릅니다.
3. 브랜드와 제품명은 포장에 적힌 그대로 적습니다. 확실하지 않으면 보이는 만큼만 적고 confidence 를 낮춥니다.
4. retailer 는 매장 간판, 장바구니/봉투 로고, 가격표 양식, 화자의 말("코스트코에서 산")로 판단합니다. 근거가 없으면 '기타/미상' 입니다.
5. 최대 30개까지, 영상 등장 순서대로 나열합니다.
6. reason 은 화자가 실제로 말하거나 자막에 나온 추천 이유만 요약합니다. 근거가 없으면 null 입니다.
7. caution 은 "이 제품이어야 하는 이유", "다른 제품과 헷갈리면 안 되는 점"(맛·용량·색상·버전·매장 전용 등)을 적습니다.
   화자가 강조했거나 포장으로 분명히 구별될 때만 적고, 일반적인 주의사항은 적지 않습니다.
8. 상품이 하나도 없으면 빈 배열을 반환합니다."""


class GeminiItem(BaseModel):
    name_ko: str = ""
    name_en: str = ""
    category: str = "기타"
    timestamp_sec: float = 0.0
    retailer: str = "기타/미상"
    edition_note: str | None = None
    reason: str | None = None
    caution: str | None = None
    confidence: float = 0.5


class GeminiExtraction(BaseModel):
    summary: str | None = None
    items: list[GeminiItem] = Field(default_factory=list)


@dataclass
class ExtractionResult:
    """한 회차 분석 결과 — items 는 analysis_runs 에 그대로 저장되는 dict 목록."""

    items: list[dict[str, Any]]
    summary: str | None = None


class GeminiError(RuntimeError):
    """Gemini 호출/파싱 실패."""


class GeminiAnalyzer:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = genai.Client(api_key=settings.gemini_api_key) if settings.gemini_api_key else None

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def _require_client(self) -> genai.Client:
        if self._client is None:
            raise GeminiError("GEMINI_API_KEY 가 설정되지 않았습니다.")
        return self._client

    # ------------------------------------------------------------------
    # public
    # ------------------------------------------------------------------

    async def analyze_youtube_url(self, url: str, run_index: int, duration: int | None = None) -> ExtractionResult:
        part = types.Part(file_data=types.FileData(file_uri=url))
        return await self._generate(part, run_index, duration)

    async def analyze_file(self, path: Path, run_index: int, duration: int | None = None) -> ExtractionResult:
        client = self._require_client()
        uploaded = await client.aio.files.upload(file=str(path), config=types.UploadFileConfig(mime_type="video/mp4"))
        try:
            uploaded = await self._wait_until_active(uploaded)
            part = types.Part.from_uri(file_uri=uploaded.uri, mime_type=uploaded.mime_type or "video/mp4")
            return await self._generate(part, run_index, duration)
        finally:
            try:
                await client.aio.files.delete(name=uploaded.name)
            except Exception:  # noqa: BLE001 — 48시간 후 자동 삭제되므로 실패해도 무방
                logger.debug("gemini file delete failed: %s", uploaded.name)

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    async def _wait_until_active(self, file: types.File) -> types.File:
        client = self._require_client()
        deadline = asyncio.get_running_loop().time() + 120
        while file.state and file.state.name == "PROCESSING":
            if asyncio.get_running_loop().time() > deadline:
                raise GeminiError("Gemini 파일 처리 대기 시간이 초과되었습니다.")
            await asyncio.sleep(2)
            file = await client.aio.files.get(name=file.name)
        if file.state and file.state.name == "FAILED":
            raise GeminiError("Gemini 가 영상 파일을 처리하지 못했습니다.")
        return file

    def _temperature(self, run_index: int) -> float:
        # 앙상블 다양성 확보: 회차가 올라갈수록 조금씩 다양하게 샘플링 (1회차는 가장 보수적)
        return min(0.8, self._settings.gemini_temperature + 0.15 * max(0, run_index - 1))

    def _config(self, run_index: int, *, tuned: bool) -> types.GenerateContentConfig:
        extra: dict[str, Any] = {}
        if tuned:
            if self._settings.gemini_thinking_level:
                extra["thinking_config"] = types.ThinkingConfig(
                    thinking_level=types.ThinkingLevel[self._settings.gemini_thinking_level.upper()]
                )
            extra["media_resolution"] = types.MediaResolution[
                f"MEDIA_RESOLUTION_{self._settings.gemini_media_resolution.upper()}"
            ]
        return types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=self._temperature(run_index),
            response_mime_type="application/json",
            response_schema=RESPONSE_SCHEMA,
            max_output_tokens=8192,
            # 함수 호출 도구를 쓰지 않으므로 자동 함수 호출(AFC) 비활성
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            **extra,
        )

    async def _generate(self, video_part: types.Part, run_index: int, duration: int | None) -> ExtractionResult:
        client = self._require_client()
        prompt = "이 영상에서 장보기 체크리스트에 넣을 상품을 추출하세요."
        if duration:
            prompt += f" 영상 길이는 {duration}초이며 timestamp_sec 은 0~{duration} 범위여야 합니다."
        config = self._config(run_index, tuned=True)
        tuned_off: types.GenerateContentConfig | None = None

        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = await asyncio.wait_for(
                    client.aio.models.generate_content(
                        model=self._settings.gemini_model,
                        contents=[types.Content(role="user", parts=[video_part, types.Part.from_text(text=prompt)])],
                        config=config,
                    ),
                    timeout=self._settings.gemini_timeout_sec,
                )
                return self._parse(response.text or "", duration)
            except genai_errors.ClientError as exc:
                code = getattr(exc, "code", None)
                if code == 400 and config is not tuned_off and _mentions_tuning(exc):
                    # 모델이 추론/해상도 옵션을 지원하지 않으면 기본 설정으로 즉시 재시도
                    logger.warning("gemini rejected tuning options (%s) — retrying with defaults", exc)
                    config = tuned_off = self._config(run_index, tuned=False)
                    continue
                # 429(쿼터)만 재시도, 그 외 4xx 는 입력 문제이므로 즉시 실패
                if code != 429:
                    raise GeminiError(f"Gemini 요청 오류: {exc}") from exc
                last_error = exc
            except (genai_errors.ServerError, asyncio.TimeoutError) as exc:
                last_error = exc
            except GeminiError as exc:
                last_error = exc
            await asyncio.sleep(2 * (attempt + 1) ** 2)
        raise GeminiError(f"Gemini 분석 실패: {last_error}") from last_error

    def _parse(self, text: str, duration: int | None) -> ExtractionResult:
        try:
            extraction = GeminiExtraction.model_validate(json.loads(text))
        except (json.JSONDecodeError, ValidationError) as exc:
            raise GeminiError("Gemini 응답 JSON 파싱 실패") from exc

        items: list[dict[str, Any]] = []
        for item in extraction.items[:MAX_ITEMS]:
            name_ko, name_en = item.name_ko.strip(), item.name_en.strip()
            if not name_ko and not name_en:
                continue
            ts = max(0.0, float(item.timestamp_sec))
            if duration:
                ts = min(ts, max(0.0, duration - 0.5))
            items.append(
                {
                    "name_ko": name_ko or name_en,
                    "name_en": name_en or name_ko,
                    "category": item.category if item.category in SHOPPING_CATEGORIES else "기타",
                    "timestamp_sec": round(ts, 2),
                    "retailer": item.retailer.strip() or "기타/미상",
                    "edition_note": (item.edition_note or "").strip() or None,
                    "reason": _clip_note(item.reason),
                    "caution": _clip_note(item.caution),
                    "confidence": round(min(1.0, max(0.0, float(item.confidence))), 3),
                }
            )
        return ExtractionResult(items=items, summary=_clip_note(extraction.summary, MAX_SUMMARY_CHARS))


def _mentions_tuning(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(word in text for word in ("thinking", "media_resolution", "media resolution"))


def _clip_note(value: str | None, limit: int = MAX_NOTE_CHARS) -> str | None:
    text = " ".join((value or "").split())
    if not text:
        return None
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"
