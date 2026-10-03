from pathlib import Path

import pytest
from fastapi import HTTPException

from brds.app import download_file
from brds.core.security import get_safe_path


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
