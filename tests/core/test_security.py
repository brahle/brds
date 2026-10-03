import asyncio
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from brds.app import app, download_file
from brds.core.datasets.dataset_files import get_dataset_files
from brds.core.fs.reader import FileReader, fload
from brds.core.security import get_safe_path


@contextmanager
def api_client():
    def get(path: str):
        async def request():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                return await client.get(path)

        return asyncio.run(request())

    yield SimpleNamespace(get=get)


@pytest.fixture
def reader_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "data"
    root.mkdir()
    monkeypatch.setenv("FILE_READER_PATH", str(root))
    return root


@pytest.mark.parametrize("requested", ["../data-x/private.txt", "../private.txt"])
def test_rejects_paths_outside_reader_root(reader_root: Path, requested: str) -> None:
    with pytest.raises(HTTPException) as error:
        get_safe_path(requested)
    assert error.value.status_code == 403


def test_rejects_absolute_sibling_path(reader_root: Path) -> None:
    sibling = reader_root.parent / "data-x" / "private.txt"
    with pytest.raises(HTTPException) as error:
        get_safe_path(str(sibling))
    assert error.value.status_code == 403


def test_rejects_symlink_to_sibling(reader_root: Path) -> None:
    sibling = reader_root.parent / "data-x"
    sibling.mkdir()
    (sibling / "private.txt").write_text("private")
    (reader_root / "escape").symlink_to(sibling, target_is_directory=True)
    with pytest.raises(HTTPException) as error:
        get_safe_path("escape/private.txt")
    assert error.value.status_code == 403


@pytest.mark.parametrize("requested", ["public.txt", "nested/../public.txt", "./public.txt"])
def test_accepts_paths_within_reader_root(reader_root: Path, requested: str) -> None:
    (reader_root / "nested").mkdir()
    assert get_safe_path(requested) == reader_root / "public.txt"
    assert get_safe_path(str(reader_root / "public.txt")) == reader_root / "public.txt"


def test_accepts_symlink_within_reader_root(reader_root: Path) -> None:
    (reader_root / "public.txt").write_text("public")
    (reader_root / "link.txt").symlink_to(reader_root / "public.txt")
    assert get_safe_path("link.txt") == reader_root / "public.txt"


def test_resolves_configured_root_symlink_and_relative_root(
    reader_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    alias = reader_root.parent / "alias"
    alias.symlink_to(reader_root, target_is_directory=True)
    monkeypatch.setenv("FILE_READER_PATH", str(alias))
    assert get_safe_path("public.txt") == reader_root / "public.txt"
    monkeypatch.chdir(reader_root.parent)
    monkeypatch.setenv("FILE_READER_PATH", "data")
    assert get_safe_path("public.txt") == reader_root / "public.txt"


@pytest.mark.asyncio
async def test_download_rejects_existing_sibling_and_allows_root_file(reader_root: Path) -> None:
    sibling = reader_root.parent / "data-x"
    sibling.mkdir()
    (sibling / "private.txt").write_text("private")
    (reader_root / "public.txt").write_text("public")
    with pytest.raises(HTTPException) as error:
        await download_file("../data-x/private.txt")
    assert error.value.status_code == 403
    response = await download_file("public.txt")
    assert response.path == reader_root / "public.txt"


@pytest.mark.asyncio
async def test_missing_file_within_root_still_returns_404(reader_root: Path) -> None:
    with pytest.raises(HTTPException) as error:
        await download_file("missing.txt")
    assert error.value.status_code == 404


def _escaped_dataset(root: Path, level: str) -> Path:
    outside = root.parent / "private"
    outside.mkdir()
    (outside / "payload.json").write_text('{"private":"OUTSIDE_SENTINEL"}')
    dataset = root / "evil"
    dataset.mkdir()
    if level == "date":
        (outside / "time").mkdir()
        (outside / "time" / "payload.json").write_text('{"private":"OUTSIDE_SENTINEL"}')
        (dataset / "2026-10-03").symlink_to(outside, target_is_directory=True)
    elif level == "time":
        (dataset / "2026-10-03").mkdir()
        (dataset / "2026-10-03" / "time").symlink_to(outside, target_is_directory=True)
    else:
        version = dataset / "2026-10-03" / "time"
        version.mkdir(parents=True)
        (version / "payload.json").symlink_to(outside / "payload.json")
    return outside


@pytest.mark.parametrize("endpoint", ["raw", "dictionary", "html"])
@pytest.mark.parametrize("level", ["date", "time", "payload"])
def test_api_rechecks_version_directories_and_final_file(reader_root: Path, endpoint: str, level: str) -> None:
    _escaped_dataset(reader_root, level)
    with api_client() as client:
        response = client.get(f"/{endpoint}/evil")
    assert response.status_code == 403
    assert "OUTSIDE_SENTINEL" not in response.text


def test_root_guard_runs_before_listing_outside_version(reader_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from brds.core.fs import reader

    outside = _escaped_dataset(reader_root, "date")
    original = reader._listdir

    def guarded_listdir(path: str):
        assert not Path(path).resolve().is_relative_to(outside)
        return original(path)

    monkeypatch.setattr(reader, "_listdir", guarded_listdir)
    with api_client() as client:
        assert client.get("/raw/evil").status_code == 403


@pytest.mark.parametrize("endpoint", ["raw", "dictionary", "html"])
def test_api_allows_contained_payload_symlink(reader_root: Path, endpoint: str) -> None:
    import pandas as pd

    pd.DataFrame([{"public": "contained"}]).to_parquet(reader_root / "data.parquet")
    version = reader_root / "public" / "2026-10-03" / "time"
    version.mkdir(parents=True)
    (version / "link.parquet").symlink_to(reader_root / "data.parquet")
    with api_client() as client:
        response = client.get(f"/{endpoint}/public")
    assert response.status_code == 200
    assert "contained" in response.text


@pytest.mark.parametrize("root_kind", ["relative", "symlink"])
def test_dataset_listing_works_with_normalized_root(
    reader_root: Path, monkeypatch: pytest.MonkeyPatch, root_kind: str
) -> None:
    version = reader_root / "public" / "2026-10-03" / "time"
    version.mkdir(parents=True)
    payload = version / "payload.json"
    payload.write_text('{"public":true}')
    if root_kind == "relative":
        monkeypatch.chdir(reader_root.parent)
        monkeypatch.setenv("FILE_READER_PATH", "data")
    else:
        alias = reader_root.parent / "alias"
        alias.symlink_to(reader_root, target_is_directory=True)
        monkeypatch.setenv("FILE_READER_PATH", str(alias))
    assert get_dataset_files("public")[0][1] == [payload.relative_to(reader_root)]
    with api_client() as client:
        response = client.get("/dataset/public")
    assert response.status_code == 200 and "payload.json" in response.text


def test_dataset_listing_rejects_outside_payload_link(reader_root: Path) -> None:
    _escaped_dataset(reader_root, "payload")
    with api_client() as client:
        assert client.get("/dataset/evil").status_code == 403


@pytest.mark.parametrize("endpoint", ["raw", "dictionary", "html", "download", "dataset"])
@pytest.mark.parametrize("filename", ["safe%00.json", "%00"])
def test_api_null_paths_return_400(reader_root: Path, endpoint: str, filename: str) -> None:
    with api_client() as client:
        response = client.get(f"/{endpoint}/{filename}")
    assert response.status_code == 400 and response.json() == {"detail": "Invalid path"}


def test_null_path_library_validation_returns_400(reader_root: Path) -> None:
    with pytest.raises(HTTPException) as error:
        get_safe_path("unsafe\x00.json")
    assert error.value.status_code == 400


def test_unrestricted_file_reader_and_fload_still_work(reader_root: Path) -> None:
    outside = _escaped_dataset(reader_root, "payload")
    assert FileReader(folder=str(outside), version="").load("payload.json") == {"private": "OUTSIDE_SENTINEL"}
    assert fload("evil") == {"private": "OUTSIDE_SENTINEL"}


def test_restricted_reader_keeps_cwd_relative_folder_semantics(
    reader_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    public = reader_root / "public"
    public.mkdir()
    (public / "payload.json").write_text('{"public":true}')
    monkeypatch.chdir(reader_root.parent)
    reader = FileReader(folder="data/public", version="", allowed_root="data")
    assert reader.load("payload.json") == {"public": True}


def test_restricted_reader_null_filename_returns_400(reader_root: Path) -> None:
    reader = FileReader(folder=str(reader_root), version="", allowed_root=str(reader_root))
    with pytest.raises(HTTPException) as error:
        reader.load("unsafe\x00.json")
    assert error.value.status_code == 400
