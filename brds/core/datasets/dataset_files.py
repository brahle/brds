from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

from brds.core.security import get_safe_path


def get_dataset_files(dataset_name: str) -> List[Tuple[str, List[Path]]]:
    root = get_safe_path(".")
    dataset_path = get_safe_path(dataset_name, root_folder=str(root))
    grouped_files: Dict[str, List[Path]] = defaultdict(list)

    for file_path in dataset_path.glob("**/*.*"):
        get_safe_path(str(file_path), root_folder=str(root))
        if not file_path.is_file():
            continue
        timestamp_str = str(file_path.parent)
        grouped_files[timestamp_str].append(file_path.relative_to(root))

    # Sort by timestamp descending
    sorted_grouped_files = sorted(grouped_files.items(), key=lambda x: x[0], reverse=True)
    return sorted_grouped_files
