#!/usr/bin/env python3
"""Refresh release wheel locks inside the pinned Python 3.14.7 amd64 base.

Only this maintenance command resolves new versions. Image builds/publication
install the committed locks with --require-hashes and --only-binary=:all:.
"""

import argparse
import json
from pathlib import Path
import subprocess
import tempfile
import tomllib


def refresh(kind):
    if kind == "container":
        requirements = ["-r", "requirements.txt"]
    elif kind == "build":
        backend = tomllib.loads(Path("pyproject.toml").read_text())["build-system"][
            "requires"
        ]
        requirements = [*backend, "build==1.3.0"]
    else:
        requirements = ["twine==6.2.0"]
    with tempfile.TemporaryDirectory() as folder:
        report = Path(folder) / "report.json"
        subprocess.run(
            [
                "python",
                "-m",
                "pip",
                "install",
                "--dry-run",
                "--ignore-installed",
                "--only-binary=:all:",
                "--report",
                str(report),
                *requirements,
            ],
            check=True,
        )
        items = json.loads(report.read_text())["install"]
    lines = ["# Python 3.14.7, linux/amd64. See docs/container-release.md to refresh."]
    for item in sorted(items, key=lambda item: item["metadata"]["name"].lower()):
        metadata = item["metadata"]
        digest = item["download_info"]["archive_info"]["hashes"]["sha256"]
        lines.append(
            f"{metadata['name']}=={metadata['version']} --hash=sha256:{digest}"
        )
    Path(f"requirements-{kind}.lock").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("container", "build", "publish"))
    refresh(parser.parse_args().kind)
