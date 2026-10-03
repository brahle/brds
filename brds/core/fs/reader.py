from json import load as _load
from os import listdir as _listdir
from os import makedirs as _makedirs
from os.path import exists as _exists
from os.path import join as _join
from pathlib import Path as _Path
from typing import Any as _Any
from typing import Optional as _Optional
from typing import TextIO as _TextIO
from typing import Type as _Type
from typing import TypeVar as _TypeVar

from pandas import read_html as _read_html
from pandas import read_parquet as _read_parquet

from ..environment import reader_folder_path as _reader_folder_path
from ..logger import get_logger as _get_logger
from ..security import get_safe_path as _get_safe_path

T = _TypeVar("T", bound="FileReader")

LOGGER = _get_logger()

#: Files a version directory can hold that are *about* the payload rather than
#: the payload itself. `get(None)` skips these when something else is present,
#: so a dataset can carry a sidecar descriptor without hiding its own data.
DESCRIPTOR_FILENAMES = frozenset({"manifest.json"})

#: Suffixes that mark a file as debris rather than data: checksums a writer
#: drops beside its output, half-finished writes, editor backups.
_DEBRIS_SUFFIXES = (".crc", "~", ".tmp", ".temp", ".part", ".partial", ".swp", ".bak")

#: Whole names that are markers, not data. `_SUCCESS` and friends come from
#: Hadoop-lineage writers; `.DS_Store` and dotfiles are caught by the prefix.
_DEBRIS_NAMES = frozenset({"_SUCCESS", "_temporary", "_committed", "_started"})


class AmbiguousDirectoryError(RuntimeError):
    """A directory resolved without a filename holds more than one candidate.

    Raised instead of picking one. `readdir` order is the filesystem's
    business -- ext4 htree order depends on a hash seed chosen at mkfs -- so
    "the first entry" is not a stable answer, and a loader that returns an
    unstable answer returns a *confidently wrong* one: a caller asking for a
    frame gets a dict, with no exception until several frames later.
    """


def _is_debris(name: str) -> bool:
    """Is this entry incidental to the write rather than the point of it?"""
    return name.startswith(".") or name in _DEBRIS_NAMES or name.endswith(_DEBRIS_SUFFIXES)


class RootedReader:
    def __init__(self: "RootedReader", root_folder: _Optional[str] = None) -> None:
        self._root_folder = root_folder if root_folder else _reader_folder_path()

    def static_files(self: "RootedReader", path: str, create: bool = False) -> _Any:
        reader_path = self._root_folder
        if create:
            _makedirs(reader_path, exist_ok=True)
        return FileReader(folder=reader_path, version=path)

    def versioned_files(self: "RootedReader", path: str, create: bool = False) -> _Any:
        reader_path = _join(self._root_folder, path)
        if create:
            _makedirs(_join(reader_path, "_/_"), exist_ok=True)
        return FileReader(folder=_join(self._root_folder, path))


class FileReader:
    def __init__(
        self: "FileReader", folder: str, version: _Optional[str] = None, *, allowed_root: _Optional[str] = None
    ) -> None:
        # Standalone readers remain unrestricted. API callers pin the root so
        # latest-version traversal and the eventual payload share a boundary.
        self._allowed_root = allowed_root
        folder = self._checked_path(folder)
        self._root_folder = folder

        if version is None:
            self._folder = _last_folder(_last_folder(folder, allowed_root), allowed_root)
            self._version = self._folder[len(folder) :]
        else:
            self._folder = self._checked_path(_join(folder, version))
            self._version = version

    def open(
        self: "FileReader",
        filename: _Optional[str] = None,
        *args: _Any,
        **kwargs: _Any,
    ) -> _TextIO:
        ret: _TextIO = open(self.get(filename), *args, **kwargs)
        return ret

    def get(self: "FileReader", filename: _Optional[str] = None) -> str:
        if filename is None:
            return self._checked_path(_join(self._folder, self._sole_file()))
        return self._checked_path(_join(self._folder, filename))

    def _checked_path(self: "FileReader", path: str) -> str:
        if self._allowed_root is None:
            return path
        return str(_get_safe_path(str(_Path(path).absolute()), root_folder=self._allowed_root))

    def _sole_file(self: "FileReader") -> str:
        """The one file in `self._folder` a caller who named none must have meant.

        This used to be `_listdir(folder)[0]`, which is whichever entry
        `readdir` handed back first. Every version directory brds writes holds
        exactly one file, so that was right for as long as it stayed true and
        silently wrong the moment it did not -- the second file could be
        returned in place of the first, and `load` would happily parse a
        `manifest.json` into a dict where the caller expected a DataFrame.

        The rule now is: ignore debris, take the single remaining file, and if
        two files could both be it, refuse rather than guess.
        """
        folder = self._checked_path(self._folder)
        entries = sorted(name for name in _listdir(folder) if not _is_debris(name))
        if not entries:
            raise FileNotFoundError(
                f"Directory '{self._folder}' holds no loadable file "
                "(it is empty, or holds only checksums, markers and hidden files)."
            )
        if len(entries) == 1:
            return entries[0]
        payloads = [name for name in entries if name not in DESCRIPTOR_FILENAMES]
        if len(payloads) == 1:
            return payloads[0]
        raise AmbiguousDirectoryError(
            f"Directory '{self._folder}' holds {len(entries)} candidate files "
            f"({', '.join(entries)}) and no filename was given, so which one is "
            "meant is the filesystem's readdir order rather than anything you "
            "asked for. Name the file -- `fload(folder, filename)` or "
            "`FileReader(...).load(filename)` -- or leave one payload in the "
            "directory."
        )

    def exists(self: "FileReader", filename: str) -> bool:
        try:
            resolved_path = self.get(filename)
        except FileNotFoundError:
            return False
        return _exists(resolved_path)

    @classmethod
    def from_environment(cls: _Type[T], subfolder: str) -> T:
        return cls(_join(_reader_folder_path(), subfolder))

    def load(self: "FileReader", filename: _Optional[str] = None, *args, **kwargs) -> _Any:
        new_file_name = self.get(filename)
        if filename:
            LOGGER.debug(
                "Latest file for folder '%s' (with filename='%s') resolved to '%s'.",
                self._root_folder,
                filename,
                new_file_name,
            )
        else:
            LOGGER.debug(
                "Latest file for folder '%s' resolved to '%s'.",
                self._root_folder,
                new_file_name,
            )
        if new_file_name.endswith(".json"):
            with open(new_file_name) as input_file:
                return _load(input_file, *args, **kwargs)
        if new_file_name.endswith(".parquet"):
            return _read_parquet(new_file_name, *args, **kwargs)
        if new_file_name.endswith(".html"):
            try:
                return _read_html(new_file_name, *args, **kwargs)
            except ValueError as ve:
                raise ValueError(f"Error parsing HTML from '{new_file_name}'") from ve
        raise NotImplementedError(f"Do not know how to load the file `{filename}`: `{new_file_name}`")


def _last_folder(folder: str, allowed_root: _Optional[str] = None) -> str:
    if allowed_root is not None:
        folder = str(_get_safe_path(folder, root_folder=allowed_root))
    try:
        selected = _join(folder, sorted(_listdir(folder), reverse=True)[0])
        if allowed_root is not None:
            return str(_get_safe_path(selected, root_folder=allowed_root))
        return selected
    except IndexError:
        raise FileNotFoundError(f"Folder '{folder}' is empty.")


def fload(folder: str, filename: _Optional[str] = None) -> _Any:
    if not filename:
        LOGGER.debug("Loading the file '%s'", folder)
    else:
        LOGGER.debug("Loading the file '%s/%s'", folder, filename)
    return FileReader.from_environment(folder).load(filename)
