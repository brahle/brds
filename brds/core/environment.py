"""
This module contains the environment variables used by the application.
"""

from os import environ as _environ
from os.path import expanduser as _expanduser
from os.path import join as _join

from dotenv import load_dotenv as _load_dotenv

_load_dotenv()


def root_folder_path() -> str:
    """
    Get the root folder path for the data storage.
    """
    if "ROOT_FOLDER_PATH" in _environ:
        return _environ["ROOT_FOLDER_PATH"]
    return _join(_expanduser("~"), "data")


def writer_folder_path() -> str:
    """
    Get the folder path for the data writer.
    """
    if "FILE_WRITER_PATH" in _environ:
        return _environ["FILE_WRITER_PATH"]
    return root_folder_path()


def reader_folder_path() -> str:
    """
    Get the folder path for the data reader.
    """
    if "FILE_READER_PATH" in _environ:
        return _environ["FILE_READER_PATH"]
    return root_folder_path()


def vault_token() -> str:
    """
    Get the vault token.
    """
    if "VAULT_TOKEN" in _environ:
        return _environ["VAULT_TOKEN"]
    return ""
