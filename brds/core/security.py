from pathlib import Path as _Path
from typing import Optional as _Optional

from fastapi import HTTPException

from brds.core.environment import reader_folder_path


def _resolve_path(path: _Path) -> _Path:
    resolved = path.resolve()
    try:
        return resolved.resolve(strict=True)
    except FileNotFoundError:
        # Preserve the library's lexical result for ordinary missing paths;
        # unlike a missing file, a symlink loop must fail on new Python too.
        return resolved


def get_safe_path(file_path: str, *, root_folder: _Optional[str] = None) -> _Path:
    if "\x00" in str(file_path):
        raise HTTPException(status_code=400, detail="Invalid path")
    try:
        base_dir = _resolve_path(_Path(reader_folder_path() if root_folder is None else root_folder))
        safe_path = _resolve_path(base_dir / file_path)
    except (RuntimeError, OSError) as exc:
        # pathlib reports symlink loops differently across supported Python
        # versions. Unresolvable paths must not become an API server error.
        raise HTTPException(status_code=404, detail="File not found") from exc

    if not safe_path.is_relative_to(base_dir):
        raise HTTPException(status_code=403, detail="Access denied")

    return safe_path
