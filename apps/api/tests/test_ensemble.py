from app.services.ensemble import (
    UNKNOWN_RETAILER,
    RawItem,
    build_consensus,
    feedback_penalty,
    normalize_name,
    normalize_retailer,
    parse_runs,
    required_votes,
)


def item(name_ko: str, name_en: str, ts: float = 10.0, retailer: str = "이마트", conf: float = 0.9, **kw) -> dict:
    return {
        "name_ko": name_ko,
        "name_en": name_en,
        "category": kw.get("category", "가공식품"),
        "timestamp_sec": ts,
        "retailer": retailer,
        "edition_note": kw.get("edition_note"),
        "confidence": conf,
    }


GYOZA = ("비비고 왕교자", "Bibigo Wang Gyoza")
RAMEN = ("신라면", "Shin Ramyun")
GHOST = ("유령 상품", "Ghost Product")


def test_required_votes() -> None:
    assert [required_votes(n) for n in (1, 2, 3, 4)] == [1, 1, 2, 2]


def test_single_run_keeps_everything_sorted_by_timestamp() -> None:
    runs = parse_runs([[item(*RAMEN, ts=30), item(*GYOZA, ts=5)]])
    result = build_consensus(runs)
    assert [c.name_en for c in result] == ["Bibigo Wang Gyoza", "Shin Ramyun"]
    assert [c.position for c in result] == [0, 1]
    assert all(c.votes == 1 for c in result)


def test_majority_drops_one_off_hallucination() -> None:
    runs = parse_runs(
        [
            [item(*GYOZA, ts=10), item(*RAMEN, ts=20)],
            [item(*GYOZA, ts=12), item(*RAMEN, ts=21), item(*GHOST, ts=40, conf=0.3)],
            [item("비비고왕교자", "bibigo wang-gyoza", ts=11), item(*RAMEN, ts=22)],
        ]
    )
    result = build_consensus(runs)
    names = [c.name_en for c in result]
    assert "Ghost Product" not in names
    assert len(result) == 2
    gyoza = result[0]
    assert gyoza.votes == 3
    assert gyoza.timestamp_sec == 11.0  # median
    assert gyoza.name_en == "Bibigo Wang Gyoza"  # mode


def test_duplicates_within_one_run_count_once() -> None:
    runs = parse_runs([[item(*GYOZA, ts=1), item(*GYOZA, ts=50)], [], []])
    result = build_consensus(runs)
    assert result == []  # 1 vote < required 2


def test_feedback_penalty_removes_item() -> None:
    runs = parse_runs([[item(*GYOZA), item(*RAMEN)], [item(*GYOZA), item(*RAMEN)]])
    penalties = {normalize_name("Shin Ramyun"): feedback_penalty(same_count=0, different_count=3)}
    result = build_consensus(runs, penalties)
    assert [c.name_en for c in result] == ["Bibigo Wang Gyoza"]


def test_feedback_penalty_curve() -> None:
    assert feedback_penalty(0, 1) == 0
    assert feedback_penalty(1, 3) == 1
    assert feedback_penalty(0, 3) == 2
    assert feedback_penalty(5, 2) == 0


def test_retailer_prefers_known_over_unknown() -> None:
    runs = parse_runs([[item(*GYOZA, retailer="unknown")], [item(*GYOZA, retailer="Costco")]])
    assert build_consensus(runs)[0].retailer == "코스트코"


def test_retailer_normalization() -> None:
    assert normalize_retailer("E-Mart") == "이마트"
    assert normalize_retailer("이마트 트레이더스 월계점") == "트레이더스"
    assert normalize_retailer("이마트에브리데이 성수점") == "이마트에브리데이"
    assert normalize_retailer("") == UNKNOWN_RETAILER
    assert normalize_retailer("동네 정육점") == "동네 정육점"


def test_invalid_category_falls_back() -> None:
    raw = RawItem.from_dict(item(*GYOZA, category="음식"))
    assert raw.category == "기타"


def test_product_key_stable_across_spacing() -> None:
    runs_a = build_consensus(parse_runs([[item("비비고 왕교자", "Bibigo Wang Gyoza")]]))
    runs_b = build_consensus(parse_runs([[item("비비고 왕교자", "BIBIGO  wang gyoza!")]]))
    assert runs_a[0].product_key == runs_b[0].product_key
