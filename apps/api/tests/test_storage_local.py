from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.services.storage import LocalStorage, R2Storage, StorageError, build_image_key, create_storage


def make(tmp_path: Path, **kw) -> LocalStorage:
    return LocalStorage(Settings(local_storage_dir=str(tmp_path / "media"), **kw))


async def test_upload_and_delete(tmp_path: Path) -> None:
    storage = make(tmp_path)
    key = build_image_key("video-1")
    uploaded = await storage.upload_webp(key, b"RIFFxxxxWEBP")

    assert uploaded.url == f"/media/{key}"
    assert (tmp_path / "media" / key).read_bytes() == b"RIFFxxxxWEBP"
    assert await storage.delete_keys([key, ""]) == 1
    assert not (tmp_path / "media" / key).exists()
    assert not (tmp_path / "media" / "captures" / "video-1").exists(), "빈 영상 폴더 정리"


async def test_rejects_path_outside_root(tmp_path: Path) -> None:
    with pytest.raises(StorageError):
        await make(tmp_path).upload_webp("../escape.webp", b"x")


def test_auto_backend_selection(tmp_path: Path) -> None:
    assert isinstance(create_storage(Settings(local_storage_dir=str(tmp_path))), LocalStorage)
    r2 = Settings(r2_account_id="a", r2_access_key_id="b", r2_secret_access_key="c", local_storage_dir=str(tmp_path))
    assert isinstance(create_storage(r2), R2Storage)
    forced = Settings(storage_backend="local", r2_account_id="a", r2_access_key_id="b", r2_secret_access_key="c",
                      local_storage_dir=str(tmp_path))
    assert isinstance(create_storage(forced), LocalStorage)


async def test_media_served_by_api(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import get_settings
    from app.main import app

    # 앱 시작 시 DB 에 연결하지 않도록 (로컬 앱 DB 의 진행 중 작업을 건드리지 않게)
    monkeypatch.setenv("DATABASE_URL", "")
    get_settings.cache_clear()

    storage = app.state.storage
    assert isinstance(storage, LocalStorage)
    key = build_image_key("served")
    await storage.upload_webp(key, b"RIFFxxxxWEBP")
    try:
        with TestClient(app) as client:
            resp = client.get(f"/media/{key}")
            assert resp.status_code == 200
            assert resp.content == b"RIFFxxxxWEBP"
            assert resp.headers["content-type"] == "image/webp"
            assert "immutable" in resp.headers["cache-control"]
            assert client.get("/media/captures/none.webp").status_code == 404
    finally:
        await storage.delete_keys([key])
        get_settings.cache_clear()
