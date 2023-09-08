from brds.core.crawler.config import remove_default_params
from brds.core.crawler.crawler import Crawler
from brds.core.crawler.variables import VariableHolder
from brds.core.crawler.templated_url import TemplatedUrl, get_path_from_url
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

    def should_load(self: "RootCrawler", url_id: int, cache: bool) -> bool:
        if not cache:
            return True
        last_crawl = self.database.latest_download(url_id)
        return not last_crawl

    def download(self: "RootCrawler", url: str, url_id: int) -> None:
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
