from os import makedirs

from brds.core.fs.reader import RootedReader

TEST_CONTENT = "test-content\n"


def test_rooted_reader():
    makedirs("/tmp/test-static-reader", exist_ok=True)
    with open("/tmp/test-static-reader/test", "w") as file:
        file.write(TEST_CONTENT)

    rooted_reader = RootedReader("/tmp")

    with rooted_reader.static_files("test-static-reader").open("test") as file:
        assert file.read() == TEST_CONTENT

    with rooted_reader.static_files("test-static-reader").open() as file:
        assert file.read() == TEST_CONTENT

    makedirs("/tmp/test-versioned-reader/2024-08-20/21_15_00", exist_ok=True)
    with open("/tmp/test-versioned-reader/2024-08-20/21_15_00/test", "w") as file:
        file.write(TEST_CONTENT)

    with rooted_reader.versioned_files("test-versioned-reader").open("test") as file:
        assert file.read() == TEST_CONTENT

    with rooted_reader.versioned_files("test-versioned-reader").open() as file:
        assert file.read() == TEST_CONTENT
