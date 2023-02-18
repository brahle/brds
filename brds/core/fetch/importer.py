from abc import ABC as _ABC
from abc import abstractmethod as _abstractmethod

from ..fs.writer import WriterTypes as _WriterTypes


class Importer(_ABC):
    @_abstractmethod
    def get(self: "Importer", url: str) -> _WriterTypes:
        pass
