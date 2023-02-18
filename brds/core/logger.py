from inspect import getmodule as _getmodule
from inspect import stack as _stack
from logging import DEBUG as _DEBUG
from logging import INFO as _INFO
from logging import WARN as _WARN
from logging import Logger as _Logger
from logging import StreamHandler as _StreamHandler
from logging import getLogger as _getLogger
from typing import Dict as _Dict
from typing import Iterable as _Iterable
from typing import List as _List
from typing import Optional as _Optional

from pythonjsonlogger import jsonlogger as _jsonlogger


def get_logger() -> _Logger:
    """Acquires a logger."""
    stack = _stack()
    caller = stack[1]

    module = _getmodule(caller[0])
    assert module
    module_name = module.__name__
    function_name = caller[3]
    logger_name = f"{module_name}.{function_name}"
    return LOGGERS.get(logger_name)


def set_logging_to_debug() -> None:
    LOGGERS.update_options(LoggerOptions().set_level(_DEBUG))


def set_logging_to_info() -> None:
    LOGGERS.update_options(LoggerOptions().set_level(_INFO))


def set_logging_to_warn() -> None:
    LOGGERS.update_options(LoggerOptions().set_level(_WARN))


class LoggerOptions:
    def __init__(self: "LoggerOptions") -> None:
        self.level = _INFO

    def set_level(self: "LoggerOptions", level: int) -> "LoggerOptions":
        self.level = level
        return self

    def update_logger(self: "LoggerOptions", logger: _Logger) -> None:
        logger.setLevel(self.level)
        for handler in logger.handlers:
            handler.setLevel(self.level)


DEFAULT_LOGGER_OPTIONS = LoggerOptions()


class Loggers:
    def __init__(self: "Loggers", options: _Optional[LoggerOptions] = None) -> None:
        self._loggers: _Dict[str, _Logger] = {}
        self._options = options if options else DEFAULT_LOGGER_OPTIONS

    def get(self: "Loggers", name: str) -> _Logger:
        if name not in self._loggers:
            self._loggers[name] = self._new(name)
        return self._loggers[name]

    def _new(self: "Loggers", name: str) -> _Logger:
        return config_logger(_getLogger(name), self._options)

    def update_options(self: "Loggers", options: LoggerOptions) -> None:
        self._options = options
        for logger in self._loggers.values():
            options.update_logger(logger)


def config_logger(logger: _Logger, options: LoggerOptions) -> _Logger:
    logger.setLevel(options.level)

    console_handler = _StreamHandler()
    console_handler.setLevel(options.level)

    custom_format = " ".join(_log_format(LEAN_KEYS))
    formatter = _jsonlogger.JsonFormatter(custom_format)
    console_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    return logger


def _log_format(keys: _Iterable[str]) -> _List[str]:
    return [f"%({key:s})s" for key in keys]


LOGGERS = Loggers()
LEAN_KEYS = [
    "asctime",
    "levelname",
    "message",
    "funcName",
    "pathname",
]

DEFAULT_KEYS = [
    "asctime",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "message",
    "name",
    "pathname",
    "relativeCreated",
    "thread",
    "threadName",
]
