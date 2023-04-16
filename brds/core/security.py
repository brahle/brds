from pathlib import Path as _Path

from fastapi import HTTPException

from brds.core.environment import reader_folder_path


def get_safe_path(file_path: str) -> _Path:
    base_dir = reader_folder_path()
    safe_path = _Path(base_dir) / file_path
    safe_path = safe_path.resolve()

    if not str(safe_path).startswith(base_dir):
        raise HTTPException(status_code=403, detail="Access denied")

    return safe_path
