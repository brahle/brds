#!/usr/bin/env python3
"""Exercise a built brds image with synthetic data; no registry credentials.

Used on PRs and before publishing a release image. Checking an import alone
misses the server command, compiled readers and packaged HTML templates.
"""

import argparse
import http.client
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import uuid


def docker(*args):
    result = subprocess.run(["docker", *args], text=True, capture_output=True, timeout=90)
    if result.returncode:
        raise RuntimeError(f"docker {args[0]} failed:\n{result.stdout}\n{result.stderr}")
    return result.stdout.strip()


def check_image(image):
    name = "brds-smoke-" + uuid.uuid4().hex[:12]
    relative = "smoke/dataset/2026-10-01/12_00_00/rows"
    rows = [{"label": "alpha", "value": 3}, {"label": "beta", "value": 4}]
    started = False
    with tempfile.TemporaryDirectory(prefix="brds-container-smoke-") as folder:
        mount = "type=bind,source=" + folder + ",target=/data"
        try:
            # The image itself writes and reads Parquet. This tests its
            # binary wheels without installing any dependency on the host.
            code = f"""
from pathlib import Path
import pandas as pd
from brds import fload
stem = Path('/data/{relative}')
stem.parent.mkdir(parents=True)
frame = pd.DataFrame({rows!r})
frame.to_parquet(stem.with_suffix('.parquet'), index=False)
stem.with_name('manifest.json').write_text('{{"kind": "synthetic"}}')
pd.testing.assert_frame_equal(fload('smoke/dataset', 'rows.parquet'), frame)
"""
            docker(
                "run",
                "--rm",
                "--user",
                f"{os.getuid()}:{os.getgid()}",
                "--workdir",
                "/tmp",
                "--network",
                "none",
                "--mount",
                mount,
                "--entrypoint",
                "python",
                image,
                "-c",
                code,
            )
            docker(
                "run",
                "--detach",
                "--name",
                name,
                "--mount",
                mount + ",readonly",
                "--publish",
                "127.0.0.1::8080",
                image,
            )
            started = True
            address = docker("port", name, "8080/tcp")
            base = "http://" + address

            def fetch(path):
                with urllib.request.urlopen(base + path, timeout=5) as response:
                    return response.read()

            until = time.monotonic() + 60
            while True:
                try:
                    schema = json.loads(fetch("/openapi.json"))
                    break
                except (urllib.error.URLError, TimeoutError, http.client.RemoteDisconnected, ConnectionError):
                    if time.monotonic() >= until:
                        raise RuntimeError("container did not become ready within 60 seconds")
                    if docker("inspect", "--format", "{{.State.Running}}", name) != "true":
                        raise RuntimeError("container exited before serving requests")
                    time.sleep(0.25)
            assert "/datasets" in schema["paths"]
            assert json.loads(fetch("/raw/" + relative + ".parquet")) == rows
            assert json.loads(fetch("/raw/" + relative.rsplit("/", 1)[0] + "/manifest.json")) == {"kind": "synthetic"}
            assert json.loads(fetch("/dictionary/" + relative + ".parquet")) == rows
            assert json.loads(fetch("/raw/smoke/dataset")) == rows
            assert json.loads(fetch("/dictionary/smoke/dataset")) == rows
            assert b"alpha" in fetch("/html/" + relative + ".parquet")
            assert b"alpha" in fetch("/html/smoke/dataset")
            assert b"dataset" in fetch("/datasets")
            assert b"rows.parquet" in fetch("/dataset/smoke/dataset")
            assert fetch("/download/" + relative + ".parquet") == (Path(folder) / (relative + ".parquet")).read_bytes()
            try:
                fetch("/raw/smoke/missing.parquet")
            except urllib.error.HTTPError as error:
                assert error.code == 404
            else:
                raise AssertionError("a missing file must return 404")
            print(
                "Container smoke passed: startup, Parquet/JSON readers, JSON/HTML routes, "
                "dataset templates, download and missing-file response"
            )
        except Exception:
            if started:
                result = subprocess.run(
                    ["docker", "logs", name], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30
                )
                print(result.stdout)
            raise
        finally:
            if started:
                subprocess.run(["docker", "rm", "--force", name], capture_output=True, timeout=30)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", help="a locally built image tag")
    check_image(parser.parse_args().image)
