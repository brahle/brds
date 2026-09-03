"""Which file `FileReader.get(None)` returns when a directory holds more than one.

The old answer was `_listdir(folder)[0]` -- whichever entry `readdir` handed
back first. Every version directory brds writes holds exactly one file, so for
as long as that stayed true the answer was right; the moment a second file
appeared it became *arbitrary*, and `load()` dispatches on the extension, so
an arbitrary file is a confidently wrong return rather than an error. A caller
doing `fload("model/club_form").shape` gets an `AttributeError` on a dict,
several frames from the cause. One doing `len(...)` gets the number of keys in
a descriptor and no error at all.

`readdir` order is not something a test may take for granted: ext4 htree order
depends on a hash seed chosen at mkfs, so a store copied onto a new volume can
list the same directory the other way round. Every test here that cares about
order therefore runs under *every* permutation of it, rather than under the
one the developer's filesystem happens to produce.
"""

from itertools import permutations
from json import dumps
from os import listdir, makedirs
from os.path import basename, join

import pytest
from pandas import DataFrame

from brds.core.fs import reader as _reader
from brds.core.fs.reader import AmbiguousDirectoryError, FileReader


@pytest.fixture
def leaf(tmp_path):
    """A brds version directory: `<root>/<dataset>/<date>/<time>/`."""
    directory = tmp_path / "model" / "club_form" / "2026-09-01" / "12_00_00"
    makedirs(directory)
    return directory


@pytest.fixture
def reader(tmp_path, leaf):
    return FileReader(join(str(tmp_path), "model", "club_form"))


def a_parquet(directory, rows=3):
    DataFrame({"element_id": list(range(rows))}).to_parquet(directory / "data.parquet")
    return "data.parquet"


def under_every_readdir_order(monkeypatch, directory, call):
    """Run `call()` once per possible `readdir` order, and report each outcome.

    Returns a list of `(order, outcome)`, where an outcome is the resolved
    basename or the exception raised. A resolver that depends on the ordering
    shows up as more than one distinct outcome.
    """
    real = _reader._listdir
    target = str(directory)
    outcomes = []
    for order in permutations(sorted(listdir(target))):
        monkeypatch.setattr(_reader, "_listdir", lambda path, o=order: list(o) if path == target else real(path))
        try:
            outcomes.append((order, basename(call())))
        except Exception as error:  # noqa: B902 -- the failure mode is part of the outcome
            outcomes.append((order, error))
    return outcomes


class TestOneFileInTheDirectory:
    """The layout brds actually writes has to keep resolving exactly as before."""

    @pytest.mark.parametrize("filename", ["data.parquet", "output.json", "index.html"])
    def test_the_single_file_is_returned_whatever_it_is_called(self, leaf, reader, filename):
        (leaf / filename).write_bytes(b"")

        assert basename(reader.get()) == filename

    def test_a_lone_descriptor_is_still_returned(self, leaf, reader):
        """`manifest.json` is skipped *in favour of* a payload, not deleted from view.

        A directory holding only a descriptor has no other candidate, so the
        descriptor is what the caller meant. Skipping it here would turn a
        readable directory into a `FileNotFoundError`.
        """
        (leaf / "manifest.json").write_text(dumps({"stage": 6}))

        assert basename(reader.get()) == "manifest.json"

    def test_an_empty_directory_says_so(self, reader):
        with pytest.raises(FileNotFoundError, match="holds no loadable file"):
            reader.get()


class TestASidecarDescriptorDoesNotDisplaceThePayload:
    """The case that motivated this: a `manifest.json` beside `data.parquet`."""

    def test_the_parquet_is_returned_under_every_readdir_order(self, monkeypatch, leaf, reader):
        a_parquet(leaf)
        (leaf / "manifest.json").write_text(dumps({"stage": 6}))

        outcomes = under_every_readdir_order(monkeypatch, leaf, reader.get)

        assert {name for _, name in outcomes} == {"data.parquet"}, outcomes

    def test_and_load_returns_a_frame_rather_than_a_dict(self, monkeypatch, leaf, reader):
        """The end-to-end shape of the bug, at the seam a caller actually uses.

        Before this fix, the `('manifest.json', 'data.parquet')` order returned
        `{'stage': 6}` here -- type `dict`, no exception -- and a caller reading
        `.shape` off it failed somewhere else entirely.
        """
        a_parquet(leaf, rows=3)
        (leaf / "manifest.json").write_text(dumps({"stage": 6}))

        outcomes = under_every_readdir_order(monkeypatch, leaf, lambda: "ok" if _shape(reader) == (3, 1) else "wrong")

        assert {name for _, name in outcomes} == {"ok"}, outcomes


class TestDebrisBesideThePayload:
    """A checksum or a half-written file is not an answer to `load()`."""

    @pytest.mark.parametrize(
        "junk", [".DS_Store", ".data.parquet.crc", "data.parquet~", "_SUCCESS", "data.parquet.tmp"]
    )
    def test_the_payload_wins_under_every_readdir_order(self, monkeypatch, leaf, reader, junk):
        a_parquet(leaf)
        (leaf / junk).write_bytes(b"")

        outcomes = under_every_readdir_order(monkeypatch, leaf, reader.get)

        assert {name for _, name in outcomes} == {"data.parquet"}, outcomes

    def test_a_directory_of_nothing_but_debris_is_not_loadable(self, leaf, reader):
        (leaf / "_SUCCESS").write_bytes(b"")
        (leaf / ".DS_Store").write_bytes(b"")

        with pytest.raises(FileNotFoundError, match="holds no loadable file"):
            reader.get()


class TestTwoPayloadsAreRefused:
    """Deterministic is not enough: picking one of two silently is the same bug."""

    @pytest.mark.parametrize("second", ["output.json", "part-0001.parquet", "index.html"])
    def test_the_reader_refuses_rather_than_choosing(self, leaf, reader, second):
        a_parquet(leaf)
        (leaf / second).write_bytes(b"")

        with pytest.raises(AmbiguousDirectoryError) as raised:
            reader.get()

        assert "data.parquet" in str(raised.value) and second in str(raised.value)

    def test_the_refusal_does_not_depend_on_readdir_order(self, monkeypatch, leaf, reader):
        a_parquet(leaf)
        (leaf / "output.json").write_text(dumps({"stage": 6}))

        outcomes = under_every_readdir_order(monkeypatch, leaf, reader.get)

        assert all(isinstance(outcome, AmbiguousDirectoryError) for _, outcome in outcomes), outcomes

    def test_naming_the_file_is_still_a_way_through(self, leaf, reader):
        """The refusal has an escape, and the message names it."""
        a_parquet(leaf)
        (leaf / "output.json").write_text(dumps({"stage": 6}))

        assert basename(reader.get("output.json")) == "output.json"
        assert reader.load("output.json") == {"stage": 6}


def _shape(reader):
    loaded = reader.load()
    return getattr(loaded, "shape", type(loaded))
