from datetime import datetime as _datetime
from json import dump as _dump
from pathlib import Path as _Path
from typing import Any as _Any
from typing import Optional as _Optional
from typing import Type as _Type
from typing import TypeVar as _TypeVar
from typing import Union as _Union

from aiohttp import ClientResponse as _ClientResponse
from pandas import DataFrame as _DataFrame
from requests import Response

from brds.core.environment import writer_folder_path as _writer_folder_path
from brds.core.logger import get_logger as _get_logger

T = _TypeVar("T", bound="FileWriter")
LOGGER = _get_logger()
WriterTypes = _Union[_DataFrame, _Any]


class FileWriter:
    def __init__(self: "FileWriter", folder: str, timestamp_col: _Optional[str] = None) -> None:
        self._timestamp = _datetime.utcnow()
        self._folder = _Path(folder)
        self._folder.mkdir(parents=True, exist_ok=True)
        self._timestamp_col = timestamp_col

    def write(self: "FileWriter", name: str, data: _Any) -> _Path:
        LOGGER.info("Writing file '%s'", name)
        if isinstance(data, _DataFrame):
            return self.write_pandas(name, data)
        if isinstance(data, Response):
            return self.write_response(name, data)
        else:
            return self.write_json(name, data)

    def write_pandas(self: "FileWriter", name: str, data: _DataFrame) -> _Path:
        file = self._get_file(name, "data.parquet")
        if self._timestamp_col:
            data[self._timestamp_col] = self._timestamp
        LOGGER.debug(f"Writing file '{file}'.")
        data.to_parquet(file)
        return file

    def write_json(self: "FileWriter", name: str, data: _Any) -> _Path:
        file = self._get_file(name, "output.json")
        if self._timestamp_col:
            if not isinstance(data, dict):
                data = {"data": data}
            data[self._timestamp_col] = self._timestamp.isoformat()
        LOGGER.debug(f"Writing file '{file}'.")
        with open(file, "w+") as output:
            _dump(data, output)
        return file

    def write_response(self: "FileWriter", name: str, data: Response) -> _Path:
        file = self._get_file(name, "index.html")
        LOGGER.debug(f"Writing file '{file}'.")
        with open(file, "w+") as output:
            output.write(data.text)
        return file

    async def stream_write(self: "FileWriter", name: str, output_file_name: str, response: _ClientResponse) -> _Path:
        file = self._get_file(name, output_file_name)
        LOGGER.debug(f"Writing file '{file}'.")
        with open(file, "wb") as output:
            while True:
                chunk = await response.content.read(1024)  # Read in 1KB chunks
                if not chunk:
                    break
                output.write(chunk)
        return file

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


async def test_file_writer_stream_write():
    from brds.core.http.client import HttpClient

    async with HttpClient() as client:
        writer = FileWriter("/tmp/test-writer")
        response = await client.get("https://www.example.com")
        file = await writer.stream_write("test", "index.html", response)
        assert file.exists()
        assert file.name == "index.html"


if __name__ == "__main__":
    from asyncio import run as _run

    _run(test_file_writer_stream_write())
