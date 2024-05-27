from brds.core.crawler.config import remove_default_params
from brds.core.crawler.crawler import Crawler
from brds.core.crawler.templated_url import TemplatedUrl
from brds.core.crawler.variables import VariableHolder
from brds.core.logger import get_logger as _get_logger

LOGGER = _get_logger()


class RootCrawler(Crawler):
    TYPE_NAME = "root-crawl"

    def __init__(self: "RootCrawler", *args, **kwargs) -> None:
        super(RootCrawler, self).__init__(*args, **kwargs)
        self.templated_urls = [TemplatedUrl(database=self.database, **remove_default_params(url)) for url in self.urls]

    def process(self: "RootCrawler", variables: VariableHolder) -> None:
        for templated_url in self.templated_urls:
            url = templated_url.resolve(variables)
            url_id = self.database.register_web_page(url)
            self.database.set_vriables(url_id, variables.variables)
            if self.should_load(url_id, templated_url.cache):
                self.download(url, url_id)
            else:
                LOGGER.info(f"Will not download '{url}', as I've already downloaded it")
