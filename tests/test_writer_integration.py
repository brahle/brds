from brds import FileWriter, FileReader


def test_file_writer_write():
    writer = FileWriter("/tmp/test-writer")
    data = {"name": "John Doe", "age": 30}
    file = writer.write("test", data)
    assert file.exists()
    assert file.name == "output.json"
    assert file.read_text() == '{"name": "John Doe", "age": 30}'


if __name__ == "__main__":
    import pytest

    pytest.main(["-v", __file__])
