from pathlib import Path as _Path
from typing import Optional as _Optional

from fastapi import HTTPException

from brds.core.environment import reader_folder_path


def get_safe_path(file_path: str, *, root_folder: _Optional[str] = None) -> _Path:
    if "\x00" in str(file_path):
        raise HTTPException(status_code=400, detail="Invalid path")
    base_dir = _Path(reader_folder_path() if root_folder is None else root_folder).resolve()
    safe_path = (base_dir / file_path).resolve()

    if not safe_path.is_relative_to(base_dir):
        raise HTTPException(status_code=403, detail="Access denied")

    return safe_path
