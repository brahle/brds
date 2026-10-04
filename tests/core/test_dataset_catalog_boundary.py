"""Catalog metadata follows the same boundary as content, without losing valid aliases."""

from pathlib import Path
from datetime import datetime

import pytest
from fastapi import HTTPException

from brds.core.datasets.list_datasets import list_datasets
from brds.core.security import get_safe_path
from tests.core.test_security import api_client, reader_root  # noqa: F401


def payload(root: Path, name: str, day: str = "2026-10-03", contents: str = "public") -> Path:
    path = root / name / day / "12_00_00" / "payload.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents)
    return path


@pytest.mark.parametrize("root_kind", ["plain", "relative", "symlink"])
def test_catalog_omits_outside_symlink_metadata_and_keeps_valid_versions(
    reader_root: Path, monkeypatch: pytest.MonkeyPatch, root_kind: str
) -> None:
    payload(reader_root, "public", "2026-10-02", "old")
    current = payload(reader_root, "public", contents="new public")
    outside = reader_root.parent / "private.json"
    outside.write_text("private " * 8192)
    hidden = payload(reader_root, "OUTSIDE_DATASET_SENTINEL")
    hidden.unlink()
    hidden.symlink_to(outside)
    # A rejected latest entry must not advance the visible timestamp/count.
    bad_version = payload(reader_root, "public", "2026-10-04")
    bad_version.unlink()
    bad_version.symlink_to(outside)
    if root_kind == "relative":
        monkeypatch.chdir(reader_root.parent)
        monkeypatch.setenv("FILE_READER_PATH", "data")
    elif root_kind == "symlink":
        alias = reader_root.parent / "alias"
        alias.symlink_to(reader_root, target_is_directory=True)
        monkeypatch.setenv("FILE_READER_PATH", str(alias))
    datasets = list_datasets()
    assert [(ds.name, ds.file_size, ds.old_versions, ds.timestamp) for ds in datasets] == [
        ("public", current.stat().st_size, 2, datetime(2026, 10, 3, 12))
    ]
    with api_client() as client:
        response = client.get("/datasets")
    assert response.status_code == 200 and "public" in response.text
    assert "OUTSIDE_DATASET_SENTINEL" not in response.text and "2026-10-04" not in response.text


def test_catalog_keeps_contained_alias_name_and_module(reader_root: Path) -> None:
    actual = payload(reader_root, "original", contents="allowed payload")
    alias = payload(reader_root, "module/alias", "2026-10-04")
    alias.unlink()
    alias.symlink_to(actual)
    datasets = list_datasets()
    assert [(ds.module, ds.name, ds.file_size) for ds in datasets] == [
        ("module", "alias", actual.stat().st_size),
        ("", "original", actual.stat().st_size),
    ]


@pytest.mark.parametrize("kind", ["self", "two-link"])
@pytest.mark.parametrize("endpoint", ["raw", "dictionary", "html", "download", "dataset"])
def test_loop_paths_return_controlled_404(reader_root: Path, kind: str, endpoint: str) -> None:
    path = reader_root / "loop.json"
    if kind == "self":
        path.symlink_to(path.name)
    else:
        path.symlink_to("second.json")
        (reader_root / "second.json").symlink_to(path.name)
    with api_client() as client:
        response = client.get(f"/{endpoint}/loop.json")
    assert response.status_code == 404 and response.json() == {"detail": "File not found"}


def test_catalog_skips_loop_and_dangling_links_without_losing_public_dataset(reader_root: Path) -> None:
    payload(reader_root, "public")
    loop = payload(reader_root, "loop")
    loop.unlink()
    loop.symlink_to(loop.name)
    dangling = payload(reader_root, "dangling")
    dangling.unlink()
    dangling.symlink_to("missing.json")
    assert [ds.name for ds in list_datasets()] == ["public"]
    with api_client() as client:
        assert client.get("/datasets").status_code == 200


@pytest.mark.parametrize("endpoint", ["datasets", "dataset/public", "raw/public"])
def test_looped_configured_root_returns_404(reader_root: Path, monkeypatch: pytest.MonkeyPatch, endpoint: str) -> None:
    root = reader_root.parent / "root-loop"
    root.symlink_to(root.name)
    monkeypatch.setenv("FILE_READER_PATH", str(root))
    with api_client() as client:
        assert client.get(f"/{endpoint}").status_code == 404


def test_resolution_oserror_is_controlled_and_missing_path_semantics_stay_valid(
    reader_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert get_safe_path("missing.json") == reader_root / "missing.json"
    original = Path.resolve

    def resolve(path, *args, **kwargs):
        if path.name == "denied":
            raise PermissionError("synthetic inaccessible path")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", resolve)
    with pytest.raises(HTTPException) as error:
        get_safe_path("denied")
    assert error.value.status_code == 404


def test_normalized_missing_prefix_does_not_hide_a_symlink_loop(reader_root: Path) -> None:
    loop = reader_root / "loop.json"
    loop.symlink_to(loop.name)
    with pytest.raises(HTTPException) as error:
        get_safe_path("missing/../loop.json")
    assert error.value.status_code == 404


@pytest.mark.parametrize("failure", [FileNotFoundError, PermissionError])
def test_catalog_continues_if_an_entry_disappears_or_becomes_unreadable(
    reader_root: Path, monkeypatch: pytest.MonkeyPatch, failure
) -> None:
    payload(reader_root, "public")
    unstable = payload(reader_root, "unstable")
    original = Path.stat

    def stat(path, *args, **kwargs):
        if path == unstable:
            raise failure("synthetic entry unavailable")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", stat)
    assert [ds.name for ds in list_datasets()] == ["public"]
