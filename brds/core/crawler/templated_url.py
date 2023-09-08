from os.path import join
from urllib.parse import urlparse

from brds.core.crawler.variables import VariableHolder
from brds.db.init_db import Database


class TemplatedUrl:
    def __init__(self: "TemplatedUrl", database: Database, name: str, url: str, cache: bool) -> None:
        self.name = name
        self.url = url
        self.cache = cache

    def resolve(self: "TemplatedUrl", variables: VariableHolder) -> str:
        return variables["base_url"] + self.url.format(**variables.variables)


def sanitize_component(component: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in component)


def get_path_from_url(url: str) -> str:
    parsed = urlparse(url)

    domain_path = join(*sanitize_component(parsed.netloc).split("."))

    path = parsed.path if parsed.path else "/"
    path_components = [sanitize_component(component) for component in path.strip("/").split("/")]

    base_path = join(domain_path, *path_components)
    return base_path
