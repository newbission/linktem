import json

from app.config import Settings
from app.services.frame_selector import FrameSelector, parse_choices


def test_parse_choices_validates_ranges() -> None:
    text = json.dumps(
        {
            "choices": [
                {"product": 1, "best": 3},
                {"product": 2, "best": -1},  # 보이는 후보 없음
                {"product": 3, "best": 9},  # 범위 밖
                {"product": 7, "best": 0},  # 없는 상품
                {"product": "x", "best": 0},
            ]
        }
    )
    assert parse_choices(text, [5, 5, 5, 5]) == [3, None, None, None]


def test_disabled_without_key_or_model() -> None:
    assert not FrameSelector(Settings(gemini_api_key="")).enabled
    assert not FrameSelector(Settings(gemini_api_key="k", frame_selection_model="")).enabled
    assert FrameSelector(Settings(gemini_api_key="k")).enabled
