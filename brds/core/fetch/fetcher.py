from typing import Any as _Any
from typing import List as _List
from typing import Tuple as _Tuple
from typing import Union as _Union

from ..fs.writer import FileWriter as _FileWriter
from ..importer.importer import Importer as _Importer
from ..logger import get_logger as _get_logger

LOGGER = _get_logger()


class Fetcher:
    """
    Fetches the given list of urls using the given importer and stores the result using the given
    writer.

    TODO: parse the domain from the url to set the prefix
    """

    def __init__(
        self: "Fetcher",
        importer: _Importer,
        writer: _FileWriter,
        urls: _List[_Union[str, _Tuple[str, _Any, _Any]]],
        prefix: str = "",
    ) -> None:
        self.importer = importer
        self.writer = writer
        self.urls = urls
        self.prefix = prefix

    def fetch(self: "Fetcher") -> None:
        for url in self.urls:
            if isinstance(url, str):
                args = []
                kwargs = {}
            else:
                args = url[1]
                kwargs = url[2]
                url = url[0]
            LOGGER.debug(f"Fetching '{url}'")
            self.writer.write(self.get_name(url), self.importer.get(url, *args, **kwargs))

    def get_name(self: "Fetcher", url: str) -> str:
        return self.prefix + url
