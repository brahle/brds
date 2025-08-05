import os
import pytest
from datetime import datetime
from io import BytesIO
from unittest.mock import MagicMock, patch

import pandas as pd
from requests import Response

from brds.core.fs.minio_writer import MinioWriter


@pytest.fixture
def mock_minio_client():
    with patch("brds.core.fs.minio_writer._Minio") as mock_minio:
        mock_client = MagicMock()
        mock_minio.return_value = mock_client
        mock_client.bucket_exists.return_value = True
        yield mock_client


@pytest.fixture
def minio_writer(mock_minio_client):
    writer = MinioWriter(
        endpoint="localhost:9000",
        access_key="minioadmin",
        secret_key="minioadmin",
        bucket="test-bucket",
        prefix="test-prefix",
        secure=False,
    )
    return writer


def test_init_creates_bucket_if_not_exists(mock_minio_client):
    mock_minio_client.bucket_exists.return_value = False

    writer = MinioWriter(
        endpoint="localhost:9000",
        access_key="minioadmin",
        secret_key="minioadmin",
        bucket="new-bucket",
    )

    mock_minio_client.bucket_exists.assert_called_once_with("new-bucket")
    mock_minio_client.make_bucket.assert_called_once_with("new-bucket")


def test_write_pandas(minio_writer, mock_minio_client):
    df = pd.DataFrame({"col1": [1, 2, 3], "col2": ["a", "b", "c"]})

    result = minio_writer.write_pandas("test_data", df)

    assert result.startswith("s3://test-bucket/")
    assert "test_data" in result
    assert "data.parquet" in result

    # Verify put_object was called
    assert mock_minio_client.put_object.called
    call_args = mock_minio_client.put_object.call_args
    assert call_args[0][0] == "test-bucket"
    assert "test-prefix/test_data" in call_args[0][1]
    assert isinstance(call_args[0][2], BytesIO)


def test_write_pandas_with_timestamp_col(minio_writer, mock_minio_client):
    minio_writer._timestamp_col = "created_at"
    df = pd.DataFrame({"col1": [1, 2, 3], "col2": ["a", "b", "c"]})

    result = minio_writer.write_pandas("test_data", df)

    # Verify timestamp column was added
    call_args = mock_minio_client.put_object.call_args
    buffer = call_args[0][2]
    buffer.seek(0)

    # Read back the parquet data
    df_written = pd.read_parquet(buffer)
    assert "created_at" in df_written.columns
    assert all(df_written["created_at"] == minio_writer._timestamp)


def test_write_json(minio_writer, mock_minio_client):
    data = {"key": "value", "number": 42}

    result = minio_writer.write_json("test_json", data)

    assert result.startswith("s3://test-bucket/")
    assert "test_json" in result
    assert "output.json" in result

    # Verify put_object was called
    assert mock_minio_client.put_object.called
    call_args = mock_minio_client.put_object.call_args
    assert call_args[1]["content_type"] == "application/json"


def test_write_json_with_timestamp_col(minio_writer, mock_minio_client):
    minio_writer._timestamp_col = "timestamp"
    data = {"key": "value"}

    result = minio_writer.write_json("test_json", data)

    # Verify timestamp was added to JSON
    call_args = mock_minio_client.put_object.call_args
    buffer = call_args[0][2]
    buffer.seek(0)

    import json

    written_data = json.loads(buffer.read().decode("utf-8"))
    assert "timestamp" in written_data
    assert written_data["timestamp"] == minio_writer._timestamp.isoformat()


def test_write_response(minio_writer, mock_minio_client):
    response = MagicMock(spec=Response)
    response.text = "<html><body>Test HTML</body></html>"

    result = minio_writer.write_response("test_html", response)

    assert result.startswith("s3://test-bucket/")
    assert "test_html" in result
    assert "index.html" in result

    # Verify put_object was called
    assert mock_minio_client.put_object.called
    call_args = mock_minio_client.put_object.call_args
    assert call_args[1]["content_type"] == "text/html"


def test_write_dispatches_correctly(minio_writer, mock_minio_client):
    # Test DataFrame
    df = pd.DataFrame({"col": [1, 2, 3]})
    result = minio_writer.write("test_df", df)
    assert "data.parquet" in result

    # Test Response
    response = MagicMock(spec=Response)
    response.text = "HTML content"
    result = minio_writer.write("test_response", response)
    assert "index.html" in result

    # Test JSON/dict
    data = {"key": "value"}
    result = minio_writer.write("test_dict", data)
    assert "output.json" in result

    # Test other data types (list)
    data = [1, 2, 3]
    result = minio_writer.write("test_list", data)
    assert "output.json" in result


@pytest.mark.asyncio
async def test_stream_write(minio_writer, mock_minio_client):
    from aiohttp import ClientResponse

    # Mock response with async content
    mock_response = MagicMock(spec=ClientResponse)
    mock_response.headers = {"Content-Type": "text/plain"}

    # Mock the async iterator
    async def mock_iter_chunked(size):
        yield b"chunk1"
        yield b"chunk2"
        yield b"chunk3"

    mock_response.content.iter_chunked = mock_iter_chunked

    result = await minio_writer.stream_write("test_stream", "output.txt", mock_response)

    assert result.startswith("s3://test-bucket/")
    assert "test_stream" in result
    assert "output.txt" in result

    # Verify put_object was called with combined chunks
    assert mock_minio_client.put_object.called
    call_args = mock_minio_client.put_object.call_args
    buffer = call_args[0][2]
    buffer.seek(0)
    assert buffer.read() == b"chunk1chunk2chunk3"


def test_from_environment():
    env_vars = {
        "MINIO_ENDPOINT": "test-endpoint:9000",
        "MINIO_ACCESS_KEY": "test-key",
        "MINIO_SECRET_KEY": "test-secret",
        "MINIO_BUCKET": "test-bucket",
        "MINIO_PREFIX": "test-prefix",
        "MINIO_SECURE": "false",
    }

    with patch.dict(os.environ, env_vars):
        with patch("brds.core.fs.minio_writer._Minio") as mock_minio:
            mock_client = MagicMock()
            mock_minio.return_value = mock_client
            mock_client.bucket_exists.return_value = True

            writer = MinioWriter.from_environment(timestamp_col="created")

            mock_minio.assert_called_once_with(
                endpoint="test-endpoint:9000",
                access_key="test-key",
                secret_key="test-secret",
                secure=False,
            )

            assert writer._bucket == "test-bucket"
            assert writer._prefix == "test-prefix"
            assert writer._timestamp_col == "created"


def test_get_object_name(minio_writer):
    # Test with prefix
    object_name = minio_writer._get_object_name("data", "file.json")
    assert object_name.startswith("test-prefix/data/")
    assert object_name.endswith("/file.json")

    # Test without prefix
    writer_no_prefix = MinioWriter(
        endpoint="localhost:9000",
        access_key="minioadmin",
        secret_key="minioadmin",
        bucket="test-bucket",
        prefix="",
    )
    with patch("brds.core.fs.minio_writer._Minio"):
        object_name = writer_no_prefix._get_object_name("data", "file.json")
        assert object_name.startswith("data/")
        assert not object_name.startswith("/data/")
