"""5회 점진적 앙상블의 다수결 병합 로직 (I/O 없는 순수 함수).

각 Gemini 회차의 결과(run)는 RawItem 리스트다. 여러 회차를 다음 규칙으로 합친다.

1. 클러스터링: 영문/한글 이름 유사도로 같은 상품끼리 묶는다.
2. 득표: 클러스터에 포함된 *서로 다른 회차* 수 = votes.
3. 채택 기준: votes - 피드백 감점 >= ceil(회차 수 / 2)  (1회차는 전부 채택)
4. 대표값: 이름/카테고리/판매처는 최빈값(동률은 confidence 합이 큰 쪽), 타임스탬프는 중앙값.
"""

from __future__ import annotations

import math
import re
import statistics
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any, Iterable

from app.schemas import SHOPPING_CATEGORIES

UNKNOWN_RETAILER = "기타/미상"

_RETAILER_ALIASES: dict[str, str] = {
    "emart": "이마트",
    "이마트": "이마트",
    "emarteveryday": "이마트에브리데이",
    "이마트에브리데이": "이마트에브리데이",
    "traders": "트레이더스",
    "emarttraders": "트레이더스",
    "트레이더스": "트레이더스",
    "이마트트레이더스": "트레이더스",
    "costco": "코스트코",
    "코스트코": "코스트코",
    "homeplus": "홈플러스",
    "홈플러스": "홈플러스",
    "lottemart": "롯데마트",
    "롯데마트": "롯데마트",
    "coupang": "쿠팡",
    "쿠팡": "쿠팡",
    "로켓배송": "쿠팡",
    "daiso": "다이소",
    "다이소": "다이소",
    "oliveyoung": "올리브영",
    "올리브영": "올리브영",
    "kurly": "컬리",
    "marketkurly": "컬리",
    "컬리": "컬리",
    "마켓컬리": "컬리",
    "nobrand": "노브랜드",
    "노브랜드": "노브랜드",
    "gs25": "GS25",
    "cu": "CU",
    "7eleven": "세븐일레븐",
    "seveneleven": "세븐일레븐",
    "세븐일레븐": "세븐일레븐",
    "emart24": "이마트24",
    "이마트24": "이마트24",
    "ikea": "이케아",
    "이케아": "이케아",
    "naver": "네이버쇼핑",
    "네이버": "네이버쇼핑",
    "네이버쇼핑": "네이버쇼핑",
    "musinsa": "무신사",
    "무신사": "무신사",
}
_ALIASES_BY_LENGTH = sorted(_RETAILER_ALIASES.items(), key=lambda kv: len(kv[0]), reverse=True)
_UNKNOWN_RETAILER_TOKENS = {"", "unknown", "none", "null", "na", "미상", "모름", "알수없음", "기타", "기타미상"}

SIMILARITY_EN = 0.82
SIMILARITY_KO = 0.85


@dataclass
class RawItem:
    name_ko: str
    name_en: str
    category: str
    timestamp_sec: float
    retailer: str
    edition_note: str | None = None
    confidence: float = 0.5

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RawItem":
        return cls(
            name_ko=str(data.get("name_ko") or "").strip(),
            name_en=str(data.get("name_en") or "").strip(),
            category=normalize_category(str(data.get("category") or "")),
            timestamp_sec=max(0.0, float(data.get("timestamp_sec") or 0.0)),
            retailer=normalize_retailer(str(data.get("retailer") or "")),
            edition_note=(str(data["edition_note"]).strip() or None) if data.get("edition_note") else None,
            confidence=min(1.0, max(0.0, float(data.get("confidence") if data.get("confidence") is not None else 0.5))),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name_ko": self.name_ko,
            "name_en": self.name_en,
            "category": self.category,
            "timestamp_sec": self.timestamp_sec,
            "retailer": self.retailer,
            "edition_note": self.edition_note,
            "confidence": self.confidence,
        }


@dataclass
class ConsensusItem:
    name_ko: str
    name_en: str
    category: str
    retailer: str
    timestamp_sec: float
    edition_note: str | None
    votes: int
    position: int = 0

    @property
    def product_key(self) -> str:
        return product_key(self.name_en or self.name_ko)


@dataclass
class _Cluster:
    members: list[tuple[int, RawItem]] = field(default_factory=list)

    @property
    def runs(self) -> set[int]:
        return {run_idx for run_idx, _ in self.members}

    def representative(self) -> RawItem:
        return max(self.members, key=lambda m: m[1].confidence)[1]


# ---------------------------------------------------------------------------
# 정규화
# ---------------------------------------------------------------------------


def normalize_name(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").lower()
    return re.sub(r"[^0-9a-z가-힣]+", "", text)


def normalize_retailer(text: str) -> str:
    key = normalize_name(text)
    if key in _UNKNOWN_RETAILER_TOKENS:
        return UNKNOWN_RETAILER
    if key in _RETAILER_ALIASES:
        return _RETAILER_ALIASES[key]
    # "이마트에브리데이 성수점" 이 "이마트" 로 잡히지 않도록 긴 별칭부터 부분 일치 검사
    for alias, canonical in _ALIASES_BY_LENGTH:
        if len(alias) >= 3 and alias in key:
            return canonical
    return text.strip()[:40] or UNKNOWN_RETAILER


def normalize_category(text: str) -> str:
    text = (text or "").strip()
    return text if text in SHOPPING_CATEGORIES else "기타"


def product_key(name: str) -> str:
    """영상 간 동일 상품 매칭 키. 판매처는 영상마다 다를 수 있으므로 키에 넣지 않는다 (ADR-010)."""
    return normalize_name(name)


def similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def names_match(en_a: str, ko_a: str, en_b: str, ko_b: str) -> bool:
    na, nb = normalize_name(en_a), normalize_name(en_b)
    ka, kb = normalize_name(ko_a), normalize_name(ko_b)
    if na and nb:
        if na == nb or similarity(na, nb) >= SIMILARITY_EN:
            return True
        shorter, longer = sorted((na, nb), key=len)
        if len(shorter) >= 6 and shorter in longer:
            return True
    if ka and kb:
        if ka == kb or similarity(ka, kb) >= SIMILARITY_KO:
            return True
        shorter, longer = sorted((ka, kb), key=len)
        if len(shorter) >= 4 and shorter in longer:
            return True
    return False


def is_same_product(a: RawItem, b: RawItem) -> bool:
    return names_match(a.name_en, a.name_ko, b.name_en, b.name_ko)


# ---------------------------------------------------------------------------
# 다수결 병합
# ---------------------------------------------------------------------------


def required_votes(n_runs: int) -> int:
    return max(1, math.ceil(n_runs / 2))


def parse_runs(raw_runs: Iterable[Iterable[dict[str, Any]]]) -> list[list[RawItem]]:
    runs: list[list[RawItem]] = []
    for run in raw_runs:
        items = [RawItem.from_dict(d) for d in run]
        runs.append([i for i in items if i.name_ko or i.name_en])
    return runs


def _mode(values: list[tuple[str, float]], default: str = "") -> str:
    """(값, 가중치) 리스트의 최빈값. 빈도 → 가중치 합 순으로 비교."""
    counts: dict[str, int] = defaultdict(int)
    weights: dict[str, float] = defaultdict(float)
    for value, weight in values:
        if not value:
            continue
        counts[value] += 1
        weights[value] += weight
    if not counts:
        return default
    return max(counts, key=lambda v: (counts[v], weights[v]))


def build_consensus(
    runs: list[list[RawItem]],
    penalties: dict[str, int] | None = None,
) -> list[ConsensusItem]:
    """회차별 결과를 병합해 채택된 상품 리스트를 타임스탬프 순으로 반환한다.

    penalties: {normalize_name(name_en): 감점} — 사용자 피드백("다른 제품이에요") 반영.
    """
    n_runs = len(runs)
    if n_runs == 0:
        return []

    clusters: list[_Cluster] = []
    for run_idx, run in enumerate(runs):
        for item in run:
            best: _Cluster | None = None
            for cluster in clusters:
                if is_same_product(cluster.representative(), item):
                    best = cluster
                    break
            if best is None:
                best = _Cluster()
                clusters.append(best)
            best.members.append((run_idx, item))

    threshold = required_votes(n_runs)
    penalties = penalties or {}
    result: list[ConsensusItem] = []

    for cluster in clusters:
        items = [m[1] for m in cluster.members]
        votes = len(cluster.runs)
        name_en = _mode([(i.name_en, i.confidence) for i in items])
        name_ko = _mode([(i.name_ko, i.confidence) for i in items], default=name_en)
        penalty = _lookup_penalty(penalties, name_en)
        if votes - penalty < threshold:
            continue
        avg_conf = sum(i.confidence for i in items) / len(items)
        # 다회차인데 겨우 기준을 넘긴 저신뢰 항목은 오탐일 가능성이 높아 제외
        if n_runs >= 3 and votes == threshold and avg_conf < 0.35:
            continue

        known_retailers = [(i.retailer, i.confidence) for i in items if i.retailer != UNKNOWN_RETAILER]
        result.append(
            ConsensusItem(
                name_ko=name_ko or name_en,
                name_en=name_en or name_ko,
                category=_mode([(i.category, i.confidence) for i in items], default="기타"),
                retailer=_mode(known_retailers, default=UNKNOWN_RETAILER),
                timestamp_sec=round(float(statistics.median(i.timestamp_sec for i in items)), 2),
                edition_note=_mode([(i.edition_note or "", i.confidence) for i in items]) or None,
                votes=votes,
            )
        )

    result.sort(key=lambda c: c.timestamp_sec)
    for position, item in enumerate(result):
        item.position = position
    return result


def _lookup_penalty(penalties: dict[str, int], name_en: str) -> int:
    key = normalize_name(name_en)
    if not key or not penalties:
        return 0
    if key in penalties:
        return penalties[key]
    best = 0
    for pkey, value in penalties.items():
        if similarity(pkey, key) >= SIMILARITY_EN:
            best = max(best, value)
    return best


def feedback_penalty(same_count: int, different_count: int) -> int:
    """'다른 제품이에요' 가 '맞아요' 보다 2표 이상 많을 때부터 1표씩 감점."""
    diff = different_count - same_count
    return max(0, diff - 1)
