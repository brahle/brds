from datetime import datetime as _datetime
from io import BytesIO as _BytesIO
from json import dumps as _dumps
from typing import Any as _Any
from typing import Optional as _Optional
from typing import Type as _Type
from typing import TypeVar as _TypeVar
from typing import Union as _Union
from uuid import uuid4 as _uuid4

from aiohttp import ClientResponse as _ClientResponse
from minio import Minio as _Minio
from pandas import DataFrame as _DataFrame
from requests import Response

from brds.core.logger import get_logger as _get_logger

T = _TypeVar("T", bound="MinioWriter")
LOGGER = _get_logger()
WriterTypes = _Union[_DataFrame, _Any]


class MinioWriter:
    def __init__(
        self: "MinioWriter",
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        prefix: str = "",
        secure: bool = True,
        timestamp_col: _Optional[str] = None,
    ) -> None:
        self._timestamp = _datetime.now()
        self._bucket = bucket
        self._prefix = prefix.rstrip("/") if prefix else ""
        self._timestamp_col = timestamp_col
        self._id = _uuid4()

        self._client = _Minio(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
        )

        # Ensure bucket exists
        if not self._client.bucket_exists(bucket):
            self._client.make_bucket(bucket)
            LOGGER.info(f"[{self._id}] Created bucket '{bucket}'")

    def write(self: "MinioWriter", name: str, data: _Any) -> str:
        LOGGER.debug(f"[{self._id}] Writing object '{name}'")
        if isinstance(data, _DataFrame):
            return self.write_pandas(name, data)
        if isinstance(data, Response):
            return self.write_response(name, data)
        else:
            return self.write_json(name, data)

    def write_pandas(self: "MinioWriter", name: str, data: _DataFrame) -> str:
        object_name = self._get_object_name(name, "data.parquet")
        if self._timestamp_col:
            data = data.copy()
            data[self._timestamp_col] = self._timestamp

        LOGGER.info(f"[{self._id}] Writing object '{name}' to '{self._bucket}/{object_name}'.")

        # Convert DataFrame to bytes
        buffer = _BytesIO()
        data.to_parquet(buffer)
        buffer.seek(0)

        # Upload to MinIO
        self._client.put_object(
            self._bucket,
            object_name,
            buffer,
            length=buffer.getbuffer().nbytes,
            content_type="application/octet-stream",
        )
        return f"s3://{self._bucket}/{object_name}"

    def write_json(self: "MinioWriter", name: str, data: _Any) -> str:
        object_name = self._get_object_name(name, "output.json")
        if self._timestamp_col:
            if not isinstance(data, dict):
                data = {"data": data}
            data = data.copy()
            data[self._timestamp_col] = self._timestamp.isoformat()

        LOGGER.info(f"[{self._id}] Writing object '{name}' to '{self._bucket}/{object_name}'.")

        # Convert to JSON bytes
        json_bytes = _dumps(data).encode("utf-8")
        buffer = _BytesIO(json_bytes)

        # Upload to MinIO
        self._client.put_object(
            self._bucket,
            object_name,
            buffer,
            length=len(json_bytes),
            content_type="application/json",
        )
        return f"s3://{self._bucket}/{object_name}"

    def write_response(self: "MinioWriter", name: str, data: Response) -> str:
        object_name = self._get_object_name(name, "index.html")
        LOGGER.info(f"[{self._id}] Writing object '{name}' to '{self._bucket}/{object_name}'.")

        # Convert to bytes
        html_bytes = data.text.encode("utf-8")
        buffer = _BytesIO(html_bytes)

        # Upload to MinIO
        self._client.put_object(
            self._bucket,
            object_name,
            buffer,
            length=len(html_bytes),
            content_type="text/html",
        )
        return f"s3://{self._bucket}/{object_name}"

    async def stream_write(self: "MinioWriter", name: str, output_file_name: str, response: _ClientResponse) -> str:
        object_name = self._get_object_name(name, output_file_name)
        LOGGER.info(f"[{self._id}] Streaming object '{name}' to '{self._bucket}/{object_name}'.")

        # Collect chunks in memory (for simplicity; could be optimized for large files)
        chunks = []
        async for chunk in response.content.iter_chunked(1024):
            chunks.append(chunk)

        data = b"".join(chunks)
        buffer = _BytesIO(data)

        # Determine content type
        content_type = response.headers.get("Content-Type", "application/octet-stream")

        # Upload to MinIO
        self._client.put_object(
            self._bucket,
            object_name,
            buffer,
            length=len(data),
            content_type=content_type,
        )
        return f"s3://{self._bucket}/{object_name}"

    @classmethod
    def from_environment(cls: _Type[T], **kwargs: _Any) -> T:
        import os

        endpoint = os.environ.get("MINIO_ENDPOINT", "localhost:9000")
        access_key = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
        secret_key = os.environ.get("MINIO_SECRET_KEY", "minioadmin")
        bucket = os.environ.get("MINIO_BUCKET", "data")
        prefix = os.environ.get("MINIO_PREFIX", "")
        secure = os.environ.get("MINIO_SECURE", "true").lower() == "true"

        return cls(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            bucket=bucket,
            prefix=prefix,
            secure=secure,
            **kwargs,
        )

    def _get_object_name(self: "MinioWriter", data_name: str, file_name: str) -> str:
        timestamp_path = self._timestamp.strftime("%Y-%m-%d/%H_%M_%S")
        parts = []
        if self._prefix:
            parts.append(self._prefix)
        parts.extend([data_name, timestamp_path, file_name])
        return "/".join(parts)


async def test_minio_writer_stream_write():
    from brds.core.http.client import HttpClient

    async with HttpClient() as client:
        writer = MinioWriter.from_environment()
        response = await client.get("https://www.example.com")
        object_path = await writer.stream_write("test", "index.html", response)
        assert object_path.startswith("s3://")
        print(f"Written to: {object_path}")


if __name__ == "__main__":
    from asyncio import run as _run

    _run(test_minio_writer_stream_write())
