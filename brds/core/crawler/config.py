import os
from copy import deepcopy
from typing import Any, Dict, Iterable, List, Tuple

import yaml


def find_md_files(dir: str) -> Iterable[Tuple[str, str]]:
    for a, b, c in os.walk(dir):
        for file in c:
            if file.endswith(".md"):
                yield (file, (os.path.join(a, file)))


def get_configs(file_name: str) -> Iterable[List[str]]:
    config: List[str] = []
    in_config = False

    with open(file_name, "r") as file:
        for line in file:
            clean = line.strip()
            if clean == "```yaml":
                in_config = True
                continue
            if in_config:
                if clean == "```":
                    in_config = False
                    yield config
                    config = []
                    continue
                config.append(line)


def get_all_configs(root: str) -> Any:
    for file_name, full_path in find_md_files(root):
        for config in get_configs(full_path):
            try:
                res = yaml.safe_load("".join(config))
            except yaml.scanner.ScannerError as err:
                raise RuntimeError(f"Error processing {full_path}") from err
            res["_filepath"] = full_path
            yield res


def remove_default_params(params: Dict[str, Any]) -> Dict[str, Any]:
    ret = deepcopy(params)
    for key in ["type"]:
        if key in ret:
            del ret[key]
    return ret


class ConfigStore:
    def __init__(self: "ConfigStore", root: str) -> None:
        self.root = root
        self.configs = list(get_all_configs(root))

        self.name_index: Dict[str, Any] = {}
        for config in self.configs:
            assert config["name"] not in self.name_index, f"Duplicate config with name '{config['name']}'"
            self.name_index[config["name"]] = config

        self.type_index: Dict[str, Any] = {}
        for config in self.configs:
            if config["type"] not in self.type_index:
                self.type_index[config["type"]] = []
            self.type_index[config["type"]].append(config)

    def __getitem__(self: "ConfigStore", name: str) -> Any:
        return self.name_index[name]

    def get_by_type(self: "ConfigStore", type: str) -> Any:
        return self.type_index[type]
