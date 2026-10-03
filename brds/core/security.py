from pathlib import Path as _Path

from fastapi import HTTPException

from brds.core.environment import reader_folder_path


def get_safe_path(file_path: str) -> _Path:
    base_dir = _Path(reader_folder_path()).resolve()
    safe_path = (base_dir / file_path).resolve()

    if not safe_path.is_relative_to(base_dir):
        raise HTTPException(status_code=403, detail="Access denied")

    return safe_path
