from brds.core.crawler.variables import VariableHolder
from brds.db.init_db import Database


class TemplatedUrl:
    def __init__(self: "TemplatedUrl", database: Database, name: str, url: str, cache: bool) -> None:
        self.name = name
        self.url = url
        self.cache = cache

    def resolve(self: "TemplatedUrl", variables: VariableHolder) -> str:
        return variables["base_url"] + self.url.format(**variables.variables)
