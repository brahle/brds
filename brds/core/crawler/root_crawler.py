from copy import deepcopy
from itertools import product
from os.path import join
from typing import Any, Dict, Iterable, List, Tuple
from urllib.parse import urlparse

from brds.core.fs.writer import FileWriter
from brds.core.crawler.browser_emulator import BrowserEmulator
from brds.core.crawler.config import ConfigStore, remove_default_params
from brds.core.crawler.variables import VariableHolder
from brds.db.init_db import Database


class Crawler():
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
            loop_variables: List[str],
            _filepath: str,
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
            orig_vars = deepcopy(vars)
            for loop_vars in self.iterate_loop_variables(orig_vars):
                for key, value in zip(self.loop_variables, loop_vars):
                    vars[key] = value
                self._process(vars)

    def merge_variables(self: "Crawler", input_variables: Tuple[Dict[str, Any]]) -> VariableHolder:
        variables = VariableHolder()
        for input in input_variables:
            variables.extend(remove_default_params(input))
        for variable in self.variables:
            variables.extend(remove_default_params(self.configs[variable]))
        return variables

    def iterate_inputs(self: "Crawler") -> Iterable[Tuple[Dict[str, Any]]]:
        return product(*[self.configs.get_by_type(input) for input in self.inputs])

    def iterate_loop_variables(self: "Crawler", variables: VariableHolder) -> Iterable[Tuple[str]]:
        return product(*[variables[loop_variable] for loop_variable in self.loop_variables])

    def _process(self: "Crawler", variables: VariableHolder) -> None:
        self.process(variables)

    def process(self: "Crawler", variables: VariableHolder) -> None:
        raise NotImplementedError("You need to override this function")

    def url(self: "Crawler", variables: VariableHolder) -> str:
        return variables["url"] + self.urls[0]["url"].format(**variables.variables)



class RootCrawler(Crawler):
    TYPE_NAME = "root-crawl"

    def __init__(self: "RootCrawler", *args, **kwargs) -> None:
        super(RootCrawler, self).__init__(*args, **kwargs)
        self.templated_urls = [TemplatedUrl(database=self.database, **remove_default_params(url)) for url in self.urls]

    def process(self: "RootCrawler", variables: VariableHolder) -> None:
        for templated_url in self.templated_urls:
            url = templated_url.resolve(variables)
            if self.should_load(url, templated_url.cache):
                self.download(url)
            else:
                print(f"Will not download '{url}', as I've already downloaded it")

    def should_load(self: "RootCrawler", url: str, cache: bool) -> bool:
        if not cache:
            return True
        url_id = self.database.register_web_page(url)
        last_crawl = self.database.latest_download(url_id)
        return not last_crawl

    def download(self: "RootCrawler", url: str) -> None:
        url_id = self.database.get_url_id(url)
        file_path = get_path_from_url(url)
        print(f"Downloading '{url}' to '{file_path}'")

        response = self.browser_emulator.get(url)
        full_path = self.file_writer.write(file_path, response)
        self.database.register_download(url_id, self.name, self._filepath, file_path, str(full_path), response.status_code)


class TemplatedUrl():
    def __init__(self: "TemplatedUrl", database: Database, name: str, url: str, cache: bool) -> None:
        self.name = name
        self.url = url
        self.cache = cache

    def resolve(self: "TemplatedUrl", variables: VariableHolder) -> None:
        return variables["url"] + self.url.format(**variables.variables)


def sanitize_component(component: str) -> str:
    return ''.join(c if c.isalnum() or c in '-_.' else '_' for c in component)


def get_path_from_url(url: str) -> str:
    parsed = urlparse(url)

    domain_path = join(*sanitize_component(parsed.netloc).split('.'))

    path = parsed.path if parsed.path else "/"
    path_components = [sanitize_component(component) for component in path.strip('/').split('/')]

    base_path = join(domain_path, *path_components)
    return base_path
