from typing import Iterable

from brds import fload
from brds.core.crawler.config import remove_default_params
from brds.core.crawler.crawler import Crawler
from brds.core.crawler.variables import VariableHolder
from brds.core.logger import get_logger as _get_logger

LOGGER = _get_logger()


class PipelineCrawler(Crawler):
    def __init__(self: "PipelineCrawler", *args, **kwargs) -> None:
        super(PipelineCrawler, self).__init__(*args, **kwargs)
        self.links_from_table = [LinksFromTable(**remove_default_params(url)) for url in self.urls]

    def process(self: "PipelineCrawler", variables: VariableHolder) -> None:
        for links in self.links_from_table:
            for url in links.load(variables):
                url_id = self.database.register_web_page(url)
                self.database.set_vriables(url_id, variables.variables)
                if self.should_load(url_id, True):
                    self.download(url, url_id)
                else:
                    LOGGER.info(f"Will not download '{url}', as I've already downloaded it")


class LinksFromTable:
    def __init__(self: "LinksFromTable", table: str, column_with_link: str) -> None:
        self.table = table
        self.column_with_link = column_with_link

    def load(self: "LinksFromTable", variables: VariableHolder) -> Iterable[str]:
        table = fload(self.table)
        for value in table[self.column_with_link]:
            if value:
                yield variables["base_url"] + value
