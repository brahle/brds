# brds

[![CI](https://github.com/brahle/brds/actions/workflows/main.yml/badge.svg)](https://github.com/brahle/brds/actions/workflows/main.yml)

Bruno Rahle's Data Science library.

## Install it from PyPI

```bash
pip install brds
```

## Usage

```python
from brds import FileReader

reader = FileReader(folder="/data/example", version="", allowed_root="/data")
data = reader.load("data.parquet")
```

`allowed_root` checks resolved paths before listing version directories or opening
a payload. Omitting it preserves ordinary `FileReader` and `fload` behavior.
The HTTP API pins readers to the normalized `FILE_READER_PATH`, including its
automatic latest-version selection. Paths or symlinks outside that root return
403; NUL request paths return 400, and unresolvable paths (including symlink
loops) return 404. The dataset index omits outside, dangling and unreadable
entries before reporting their metadata; valid in-root aliases keep their logical
dataset names and timestamps. Relative and symlinked configured roots are
supported by file reading and dataset listings. Python 3.9 or newer is required.

## Development

Read the [CONTRIBUTING.md](CONTRIBUTING.md) file.
