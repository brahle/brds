from gzip import decompress as _decompress
from json import loads as _loads
from typing import Any as _Any
from typing import Dict as _Dict
from urllib.parse import urljoin as _urljoin

from requests import get as _get

from .importer import Importer as _Importer


class GunzipImporter(_Importer):
    def __init__(self: "GunzipImporter", domain: str) -> None:
        self.domain = domain

    def get(self: "GunzipImporter", url: str) -> _Dict[str, _Any]:
        response = _get(_urljoin(self.domain, url), verify=False)
        data = _decompress(response.content)
        ret: _Dict[str, _Any] = _loads(data)
        return ret
