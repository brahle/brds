from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from fastapi import HTTPException

from ..security import get_safe_path
from .dataset_info import DatasetInfo


def parse_timestamp(timestamp_str: str) -> datetime:
    try:
        return datetime.strptime(timestamp_str, "%Y-%m-%d/%H_%M_%S")
    except ValueError as ve:
        raise RuntimeError(f"Can't parse '{timestamp_str}'") from ve


def extract_dataset_info(dataset_path: Path, root: Path) -> Dict[str, Any]:
    relative_path = dataset_path.relative_to(root)
    parts = list(relative_path.parts)
    date_str, time_str, _ = parts[-3:]
    dataset_name = parts[-4]
    module_name_parts = parts[:-4]
    module_name = "/".join(module_name_parts)
    full_name = f"{module_name}/{dataset_name}" if module_name else dataset_name
    timestamp = parse_timestamp(f"{date_str}/{time_str}")
    file_size = get_safe_path(str(dataset_path.absolute()), root_folder=str(root)).stat().st_size

    return {"full_name": full_name, "timestamp": timestamp, "file_size": file_size}


def list_datasets() -> List[DatasetInfo]:
    root = get_safe_path(".")
    dataset_list: List[DatasetInfo] = []

    dataset_versions: Dict[str, int] = defaultdict(int)
    dataset_data: Dict[str, Dict[str, Any]] = defaultdict(dict)

    for dataset_path in root.glob("**/*.*"):
        try:
            safe_path = get_safe_path(str(dataset_path), root_folder=str(root))
            if not safe_path.is_file():
                continue
            # Names/timestamps use the logical catalog path; the guarded final
            # target supplies its size. Do not rename an in-root alias.
            dataset_info = extract_dataset_info(dataset_path, root)
        except HTTPException as exc:
            if exc.status_code not in (403, 404):
                raise
            continue
        except OSError:
            # A disappearing/unreadable entry must not abort the whole index.
            continue
        full_name = dataset_info["full_name"]

        if full_name not in dataset_data or dataset_info["timestamp"] > dataset_data[full_name]["timestamp"]:
            dataset_data[full_name] = {"timestamp": dataset_info["timestamp"], "file_size": dataset_info["file_size"]}
        dataset_versions[full_name] += 1

    for full_name, data in dataset_data.items():
        if "/" in full_name:
            module_name, dataset_name = full_name.rsplit("/", 1)
        else:
            module_name = ""
            dataset_name = full_name
        dataset = DatasetInfo(
            module=module_name,
            name=dataset_name,
            timestamp=data["timestamp"],
            file_size=data["file_size"],
            old_versions=dataset_versions[full_name],
        )
        dataset_list.append(dataset)

    # Sort datasets by most recent modification time
    dataset_list.sort(key=lambda ds: ds.timestamp, reverse=True)
    return dataset_list
