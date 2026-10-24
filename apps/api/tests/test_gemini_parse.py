import json

from app.config import Settings
from app.services.gemini import MAX_NOTE_CHARS, MAX_SUMMARY_CHARS, GeminiAnalyzer


def parse(payload: dict):
    return GeminiAnalyzer(Settings(gemini_api_key=""))._parse(json.dumps(payload), duration=30)


def test_summary_and_notes_are_trimmed() -> None:
    result = parse(
        {
            "summary": "  트레이더 조   하울  " + "가" * 300,
            "items": [
                {
                    "name_ko": "어니언 솔트",
                    "name_en": "Onion Salt",
                    "category": "가공식품",
                    "timestamp_sec": 99,
                    "retailer": "트레이더 조",
                    "reason": " 감자튀김에 뿌리면 최고 ",
                    "caution": "나" * 500,
                    "confidence": 0.9,
                }
            ],
        }
    )
    assert result.summary is not None and result.summary.startswith("트레이더 조 하울")
    assert len(result.summary) == MAX_SUMMARY_CHARS and result.summary.endswith("…")
    item = result.items[0]
    assert item["reason"] == "감자튀김에 뿌리면 최고"
    assert len(item["caution"]) == MAX_NOTE_CHARS
    assert item["timestamp_sec"] == 29.5, "영상 길이 안으로 보정"


def test_missing_summary_is_none() -> None:
    result = parse({"items": []})
    assert result.summary is None and result.items == []
