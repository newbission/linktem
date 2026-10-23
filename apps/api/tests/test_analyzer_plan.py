"""Analyzer._plan_sync — 회차가 바뀌어도 아이템 ID 가 유지되는지 검증."""

import uuid

from app.config import Settings
from app.services.analyzer import Analyzer
from app.services.ensemble import build_consensus, parse_runs, product_key


def make_analyzer() -> Analyzer:
    return Analyzer(
        settings=Settings(),
        pool=None,
        downloader=None,  # type: ignore[arg-type]
        gemini=None,  # type: ignore[arg-type]
        images=None,  # type: ignore[arg-type]
        storage=None,  # type: ignore[arg-type]
    )


def row(name_ko: str, name_en: str, ts: float, image_key: str = "captures/x.webp", retailer: str = "이마트") -> dict:
    return {
        "id": uuid.uuid4(),
        "name_ko": name_ko,
        "name_en": name_en,
        "normalized_key": product_key(name_en),
        "timestamp_sec": ts,
        "image_key": image_key,
    }


def raw(name_ko: str, name_en: str, ts: float) -> dict:
    return {"name_ko": name_ko, "name_en": name_en, "category": "가공식품", "timestamp_sec": ts,
            "retailer": "이마트", "confidence": 0.9}


def test_plan_keeps_ids_and_recaptures_only_moved_items() -> None:
    gyoza = row("비비고 왕교자", "Bibigo Wang Gyoza", 10)
    ramen = row("신라면", "Shin Ramyun", 20)
    stale = row("없어진 상품", "Removed Thing", 30)
    consensus = build_consensus(
        parse_runs([[raw("비비고 왕교자", "Bibigo Wang-Gyoza", 11), raw("신라면", "Shin Ramyun", 26),
                     raw("햇반", "Hetbahn", 40)]])
    )
    plans = make_analyzer()._plan_sync(consensus, [gyoza, ramen, stale], can_capture=True)

    by_name = {p.consensus.name_en: p for p in plans}
    assert by_name["Bibigo Wang-Gyoza"].existing is gyoza
    assert by_name["Bibigo Wang-Gyoza"].needs_capture is False  # 1초 이동 → 재캡처 불필요
    assert by_name["Shin Ramyun"].existing is ramen
    assert by_name["Shin Ramyun"].needs_capture is True  # 6초 이동 → 재캡처
    assert by_name["Hetbahn"].existing is None and by_name["Hetbahn"].needs_capture
    assert all(p.existing is not stale for p in plans)


def test_plan_without_video_skips_new_items() -> None:
    gyoza = row("비비고 왕교자", "Bibigo Wang Gyoza", 10, image_key="")
    consensus = build_consensus(parse_runs([[raw("비비고 왕교자", "Bibigo Wang Gyoza", 10), raw("햇반", "Hetbahn", 40)]]))
    plans = make_analyzer()._plan_sync(consensus, [gyoza], can_capture=False)
    assert len(plans) == 1
    assert plans[0].existing is gyoza and plans[0].needs_capture is False
