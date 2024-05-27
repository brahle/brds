from copy import deepcopy
from itertools import product
from os.path import join
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse

from brds.core.crawler.browser_emulator import BrowserEmulator
from brds.core.crawler.config import ConfigStore
from brds.core.crawler.variables import VariableHolder
from brds.core.fs.writer import FileWriter
from brds.core.logger import get_logger as _get_logger
from brds.db.init_db import Database

LOGGER = _get_logger()


class Crawler:
    def __init__(
        self: "Crawler",
        configs: ConfigStore,
        database: Database,
        browser_emulator: BrowserEmulator,
        file_writer: FileWriter,
        name: str,
        variables: List[str],
        inputs: List[str],
        urls: List[Dict[str, Any]],
        _filepath: str,
        loop_variables: Optional[List[str]] = None,
    ) -> None:
        self.configs = configs
        self.database = database
        self.browser_emulator = browser_emulator
        self.file_writer = file_writer

        self.name = name
        self.variables = variables
        self.inputs = inputs
        self.urls = urls
        self.loop_variables = loop_variables
        self._filepath = _filepath

    def execute(self: "Crawler") -> None:
        for input_variables in self.iterate_inputs():
            vars = self.merge_variables(input_variables)
            if self.loop_variables:
                orig_vars = deepcopy(vars)
                for loop_vars in self.iterate_loop_variables(orig_vars):
                    for key, value in zip(self.loop_variables, loop_vars):
                        if key not in ["name", "_filepath"]:
                            vars[key] = value
                    self._process(vars)
            else:
                self._process(vars)

    def merge_variables(self: "Crawler", input_variables: Tuple[Dict[str, Any]]) -> VariableHolder:
        variables = VariableHolder()
        variables.extend(
            {
                "name": self.name,
                "_filepath": self._filepath,
            }
        )
        for input in input_variables:
            variables.extend(remove_variable_parameters(input))
        for variable in self.variables:
            variables.extend(remove_variable_parameters(self.configs[variable]))
        return variables

    def iterate_inputs(self: "Crawler") -> Iterable[Tuple[Dict[str, Any]]]:
        return product(*[self.configs.get_by_type(input) for input in self.inputs])

    def iterate_loop_variables(self: "Crawler", variables: VariableHolder) -> Iterable[Tuple[str]]:
        assert self.loop_variables is not None
        return product(*[variables[loop_variable] for loop_variable in self.loop_variables])

    def _process(self: "Crawler", variables: VariableHolder) -> None:
        self.process(variables)

    def process(self: "Crawler", variables: VariableHolder) -> None:
        raise NotImplementedError("You need to override this function")

    def url(self: "Crawler", variables: VariableHolder) -> str:
        return variables["url"] + self.urls[0]["url"].format(**variables.variables)

    def download(self: "Crawler", url: str, url_id: int) -> None:
        file_path = get_path_from_url(url)
        LOGGER.info(f"Downloading '{url}' to '{file_path}'")

        response = self.browser_emulator.get(url)
        full_path = self.file_writer.write(file_path, response)
        self.database.register_download(
            url_id,
            self.name,
            self._filepath,
            file_path,
            str(full_path),
            response.status_code,
        )

    def should_load(self: "Crawler", url_id: int, cache: bool) -> bool:
        if not cache:
            return True
        last_crawl = self.database.latest_download(url_id)
        return not last_crawl


def remove_variable_parameters(params: Dict[str, Any]) -> Dict[str, Any]:
    copy = deepcopy(params)
    for key in ["name", "_filepath"]:
        if key in copy:
            del copy[key]
    return copy


def sanitize_component(component: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in component)


def get_path_from_url(url: str) -> str:
    parsed = urlparse(url)

    domain_path = join(*sanitize_component(parsed.netloc).split("."))

    path = parsed.path if parsed.path else "/"
    path_components = [sanitize_component(component) for component in path.strip("/").split("/")]

    base_path = join(domain_path, *path_components)
    return base_path
