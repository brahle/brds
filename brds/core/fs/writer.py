from datetime import datetime as _datetime
from json import dump as _dump
from pathlib import Path as _Path
from typing import Any as _Any
from typing import Optional as _Optional
from typing import Type as _Type
from typing import TypeVar as _TypeVar
from typing import Union as _Union

from pandas import DataFrame as _DataFrame

from ..environment import writer_folder_path as _writer_folder_path
from ..logger import get_logger as _get_logger

T = _TypeVar("T", bound="FileWriter")
LOGGER = _get_logger()
WriterTypes = _Union[_DataFrame, _Any]


class FileWriter:
    def __init__(self: "FileWriter", folder: str, timestamp_col: _Optional[str] = None) -> None:
        self._timestamp = _datetime.utcnow()
        self._folder = _Path(folder)
        self._folder.mkdir(parents=True, exist_ok=True)
        self._timestamp_col = timestamp_col

    def write(self: "FileWriter", name: str, data: _Any) -> None:
        LOGGER.info("Writing file '%s'", name)
        if isinstance(data, _DataFrame):
            self.write_pandas(name, data)
        else:
            self.write_json(name, data)

    def write_pandas(self: "FileWriter", name: str, data: _DataFrame) -> None:
        file = self._get_file(name, "data.parquet")
        if self._timestamp_col:
            data[self._timestamp_col] = self._timestamp
        LOGGER.debug(f"Writing file '{file}'.")
        data.to_parquet(file)

    def write_json(self: "FileWriter", name: str, data: _Any) -> None:
        file = self._get_file(name, "output.json")
        if self._timestamp_col:
            if not isinstance(data, dict):
                data = {"data": data}
            data[self._timestamp_col] = self._timestamp.isoformat()
        LOGGER.debug(f"Writing file '{file}'.")
        with open(file, "w+") as output:
            _dump(data, output)

    @classmethod
    def from_environment(cls: _Type[T], **kwargs: _Any) -> T:
        return cls(_writer_folder_path(), **kwargs)

    def _get_file(self: "FileWriter", data_name: str, file_name: str) -> _Path:
        file = (
            self._folder.joinpath(data_name)
            .joinpath(self._timestamp.strftime("%Y-%m-%d/%H_%M_%S"))
            .joinpath(file_name)
        )
        file.parent.mkdir(parents=True, exist_ok=True)
        return file
