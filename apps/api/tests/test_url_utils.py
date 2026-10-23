import pytest

from app.services.url_utils import UnsupportedUrlError, extract_first_url, normalize_video_url


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ&si=abc",
        "https://youtu.be/dQw4w9WgXcQ?si=xyz",
        "https://m.youtube.com/shorts/dQw4w9WgXcQ",
        "https://youtube.com/embed/dQw4w9WgXcQ",
    ],
)
def test_youtube_variants_share_one_key(url: str) -> None:
    target = normalize_video_url(url)
    assert target.platform == "youtube"
    assert target.canonical_key == "youtube:dQw4w9WgXcQ"
    assert target.url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


@pytest.mark.parametrize(
    "url,key",
    [
        ("https://www.instagram.com/reel/C9abcDEF123/?igsh=xx", "instagram:C9abcDEF123"),
        ("https://instagram.com/reels/C9abcDEF123/", "instagram:C9abcDEF123"),
        ("https://www.instagram.com/someone/reel/C9abcDEF123/", "instagram:C9abcDEF123"),
        ("https://www.instagram.com/p/C9abcDEF123/", "instagram:C9abcDEF123"),
    ],
)
def test_instagram(url: str, key: str) -> None:
    assert normalize_video_url(url).canonical_key == key


def test_tiktok_full_and_short() -> None:
    full = normalize_video_url("https://www.tiktok.com/@shopper/video/7312345678901234567?lang=ko")
    assert full.canonical_key == "tiktok:7312345678901234567"
    short = normalize_video_url("https://vt.tiktok.com/ZSabc123/")
    assert short.canonical_key.startswith("tiktok-short:")


def test_url_extracted_from_share_text() -> None:
    text = "이 영상 꼭 봐! https://youtu.be/dQw4w9WgXcQ?si=1 장보기 참고"
    assert extract_first_url(text) == "https://youtu.be/dQw4w9WgXcQ?si=1"
    assert normalize_video_url(text).canonical_key == "youtube:dQw4w9WgXcQ"


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/video.mp4",
        "http://169.254.169.254/latest/meta-data",
        "https://www.youtube.com/watch?v=short",
        "https://www.instagram.com/someone/",
        "ftp://youtube.com/watch?v=dQw4w9WgXcQ",
        "그냥 텍스트",
    ],
)
def test_rejects_unsupported(url: str) -> None:
    with pytest.raises(UnsupportedUrlError):
        normalize_video_url(url)
