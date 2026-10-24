import io
import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from app.config import Settings
from app.services.image_processor import ImageProcessor, resize_short_side

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


@pytest.fixture(scope="module")
def sample_video(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("video") / "sample.mp4"
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc2=size=1920x1080:rate=30:duration=4",
            "-pix_fmt", "yuv420p", "-y", str(path),
        ],
        check=True,
    )
    return path


async def test_capture_produces_720p_full_and_256p_thumb(sample_video: Path, tmp_path: Path) -> None:
    settings = Settings()
    processor = ImageProcessor(settings)
    captured = await processor.capture_webp(sample_video, 2.0, tmp_path, duration=4)

    full = Image.open(io.BytesIO(captured.full))
    assert full.format == "WEBP" and full.size == (1280, 720)
    assert len(captured.full) <= settings.image_target_max_bytes

    thumb = Image.open(io.BytesIO(captured.thumb))
    assert thumb.format == "WEBP" and min(thumb.size) == settings.image_thumb_short_side
    assert len(captured.thumb) < len(captured.full)
    assert not list(tmp_path.glob("*.png")), "temporary frames must be cleaned up"


async def test_timestamp_beyond_duration_is_clamped(sample_video: Path, tmp_path: Path) -> None:
    captured = await ImageProcessor(Settings()).capture_webp(sample_video, 999.0, tmp_path, duration=4)
    assert Image.open(io.BytesIO(captured.full)).format == "WEBP"
    assert Image.open(io.BytesIO(captured.thumb)).format == "WEBP"


def test_resize_never_upscales() -> None:
    small = Image.new("RGB", (360, 640))
    assert resize_short_side(small, 720).size == (360, 640)
    vertical = Image.new("RGB", (1080, 1920))
    assert resize_short_side(vertical, 720).size == (720, 1280)


def test_encode_cover_makes_small_webp() -> None:
    buf = io.BytesIO()
    Image.new("RGB", (1280, 720), (200, 30, 30)).save(buf, format="JPEG")
    data = ImageProcessor(Settings()).encode_cover(buf.getvalue())
    cover = Image.open(io.BytesIO(data))
    assert cover.format == "WEBP" and min(cover.size) == Settings().image_thumb_short_side
