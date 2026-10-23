"""packages/types/src/index.ts ↔ app/schemas.py 계약 일치 검증 (ADR-002)."""

import re
from pathlib import Path
from typing import get_args

import pytest

from app import schemas

TS_FILE = Path(__file__).resolve().parents[3] / "packages" / "types" / "src" / "index.ts"

MODELS = [
    "VideoAnalysisRequest",
    "ShoppingItem",
    "VideoAnalysisResponse",
    "AnalysisJob",
    "AnalyzeResponse",
    "VideoLookupResponse",
    "UserFeedbackRequest",
    "UserFeedbackResponse",
    "RelatedVideo",
    "RelatedVideosResponse",
    "HealthResponse",
]


def parse_ts_interfaces(source: str) -> dict[str, dict[str, bool]]:
    """{interface: {field: optional}} — 주석 제거 후 단순 파싱."""
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    source = re.sub(r"//[^\n]*", "", source)
    result: dict[str, dict[str, bool]] = {}
    for match in re.finditer(r"export interface (\w+)\s*\{(.*?)\n\}", source, flags=re.S):
        fields = {}
        for field in re.finditer(r"^\s*(\w+)(\?)?\s*:", match.group(2), flags=re.M):
            fields[field.group(1)] = bool(field.group(2))
        result[match.group(1)] = fields
    return result


@pytest.fixture(scope="module")
def ts_interfaces() -> dict[str, dict[str, bool]]:
    if not TS_FILE.exists():
        pytest.skip("packages/types not available")
    return parse_ts_interfaces(TS_FILE.read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", MODELS)
def test_fields_match(name: str, ts_interfaces: dict[str, dict[str, bool]]) -> None:
    model = getattr(schemas, name)
    ts_fields = ts_interfaces[name]
    assert set(model.model_fields) == set(ts_fields), f"{name} 필드 불일치"
    for field_name, optional in ts_fields.items():
        py_field = model.model_fields[field_name]
        nullable = type(None) in get_args(py_field.annotation)
        if optional:
            assert nullable and not py_field.is_required(), f"{name}.{field_name} 는 Optional 이어야 함"
        else:
            assert not nullable, f"{name}.{field_name} 는 필수(non-null)여야 함"


def test_feedback_type_literal(ts_interfaces: dict[str, dict[str, bool]]) -> None:
    source = TS_FILE.read_text(encoding="utf-8")
    ts_values = set(re.findall(r"'(\w+)'", re.search(r"type FeedbackType = ([^;]+);", source).group(1)))
    assert ts_values == set(get_args(schemas.FeedbackType))


@pytest.mark.parametrize("ts_type", ["AnalysisJobStatus", "AnalysisJobStage"])
def test_job_literals(ts_type: str) -> None:
    source = TS_FILE.read_text(encoding="utf-8")
    ts_values = set(re.findall(r"'(\w+)'", re.search(rf"type {ts_type} = ([^;]+);", source).group(1)))
    assert ts_values == set(get_args(getattr(schemas, ts_type)))


def test_categories_match() -> None:
    source = TS_FILE.read_text(encoding="utf-8")
    block = re.search(r"SHOPPING_CATEGORIES = \[(.*?)\] as const", source, flags=re.S).group(1)
    assert tuple(re.findall(r"'([^']+)'", block)) == schemas.SHOPPING_CATEGORIES
