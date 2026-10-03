#!/usr/bin/env python3
"""Publish the saved, validated image and monotonically promote stable latest.

The workflow serializes promotion jobs. No image is built or executed here.
Version publication and promotion each leave a JSON receipt, including failures.
"""

import argparse
from email.parser import Parser
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile


DIGEST = r"sha256:[0-9a-f]{64}"
VERSION_LABEL = "org.opencontainers.image.version"


def stable_version(value):
    if re.fullmatch(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", value):
        return tuple(int(part) for part in value.split("."))
    return None


def docker(*args, allow_missing=False):
    result = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=600)
    output = result.stdout + "\n" + result.stderr
    if result.returncode:
        # Only an explicit missing manifest means first publication. Authentication,
        # transport and rate-limit failures must never authorize replacing latest.
        if allow_missing and re.search(
            r"^Error response from daemon: (?:manifest for \S+ not found: )?"
            r"manifest unknown(?:: manifest unknown)?\s*$",
            output,
            re.MULTILINE,
        ):
            return None
        raise RuntimeError(f"docker {args[0]} failed (exit {result.returncode})")
    return result.stdout


def pushed_digest(output):
    matches = re.findall(r"^\S+: digest: (" + DIGEST + r") size: [0-9]+\s*$", output, re.MULTILINE)
    if len(set(matches)) != 1:
        raise RuntimeError("Push did not return one immutable manifest digest")
    return matches[0]


def pulled_digest(output):
    matches = re.findall(r"^Digest: (" + DIGEST + r")\s*$", output, re.MULTILINE)
    if len(set(matches)) != 1:
        raise RuntimeError("Pull did not return one immutable manifest digest")
    return matches[0]


def inspect(image):
    return json.loads(docker("image", "inspect", image))[0]


def legacy_version(archive):
    """Read installed package metadata, without extracting files or running code."""
    versions = set()
    for member in archive:
        if not re.search(r"/(brds-[^/]+\.dist-info/METADATA|brds[^/]*\.egg-info/PKG-INFO)$", member.name):
            continue
        if not member.isfile() or member.size > 1024 * 1024:
            raise RuntimeError("Invalid legacy BRDS package metadata")
        with archive.extractfile(member) as stream:
            metadata = Parser().parsestr(stream.read().decode("utf-8"))
        if metadata.get_all("Name") != ["brds"] or len(metadata.get_all("Version", [])) != 1:
            raise RuntimeError("Ambiguous legacy BRDS package metadata")
        versions.add(metadata["Version"])
    if len(versions) != 1:
        raise RuntimeError("Cannot identify one legacy BRDS version; inspect latest before retrying")
    return versions.pop()


def image_version(image):
    labels = inspect(image)["Config"].get("Labels") or {}
    if VERSION_LABEL in labels:
        return labels[VERSION_LABEL]
    container = docker("create", image).strip()
    try:
        # A temporary tar stays on disk; neither the legacy entrypoint nor any
        # package code executes. docker export does not include mounted volumes.
        with tempfile.TemporaryFile() as stream:
            subprocess.run(["docker", "export", container], stdout=stream, check=True, timeout=600)
            stream.seek(0)
            with tarfile.open(fileobj=stream, mode="r|") as archive:
                return legacy_version(archive)
    finally:
        docker("rm", container)


def publish_version(repository, version, receipt):
    image_id = Path("image.id").read_text().strip()
    if not re.fullmatch(DIGEST, image_id) or inspect("brds:release-test")["Id"] != image_id:
        raise RuntimeError("Loaded image differs from the validated image ID")
    if image_version("brds:release-test") != version:
        raise RuntimeError("Tested image version label differs from the release tag")
    receipt.update(image_id=image_id, archive_sha256=Path("image.sha256").read_text().split()[0])
    reference = f"{repository}:{version}"
    docker("tag", "brds:release-test", reference)
    receipt["digest"] = pushed_digest(docker("push", reference))
    receipt["immutable_reference"] = f"{repository}@{receipt['digest']}"
    receipt["decision"] = "published-version"


def promote_latest(repository, version, receipt):
    published = json.loads(Path("version-receipt.json").read_text())
    if (
        published.get("status") != "success"
        or published.get("repository") != repository
        or published.get("version") != version
        or not re.fullmatch(DIGEST, published.get("digest", ""))
        or not re.fullmatch(DIGEST, published.get("image_id", ""))
    ):
        raise RuntimeError("Invalid upstream version receipt")
    receipt.update(digest=published["digest"], image_id=published["image_id"], version_receipt=published)
    candidate = stable_version(version)
    if candidate is None:
        receipt["decision"] = "skipped-non-stable-version"
        return
    latest = f"{repository}:latest"
    previous = docker("pull", "--platform", "linux/amd64", latest, allow_missing=True)
    if previous is not None:
        digest = pulled_digest(previous)
        current_version = image_version(f"{repository}@{digest}")
        current = stable_version(current_version)
        receipt.update(previous_digest=digest, previous_version=current_version)
        if current is None:
            raise RuntimeError("Latest has an unrecognized stable version; inspect it before retrying")
        if candidate < current:
            receipt["decision"] = "skipped-older-version"
            return
        if candidate == current:
            if digest != published["digest"]:
                raise RuntimeError("Latest already has this version with a different digest")
            receipt["decision"] = "already-current"
            return
    immutable = f"{repository}@{published['digest']}"
    pulled = docker("pull", "--platform", "linux/amd64", immutable)
    if pulled_digest(pulled) != published["digest"] or inspect(immutable)["Id"] != published["image_id"]:
        raise RuntimeError("Registry image differs from the validated version receipt")
    if image_version(immutable) != version:
        raise RuntimeError("Registry version label differs from the version receipt")
    docker("tag", immutable, latest)
    receipt["latest_digest"] = pushed_digest(docker("push", latest))
    if receipt["latest_digest"] != published["digest"]:
        raise RuntimeError("Latest digest differs from the published version digest")
    receipt["decision"] = "promoted-latest"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["version", "latest"])
    args = parser.parse_args()
    repository, version = os.environ["IMAGE_REPOSITORY"], os.environ["RELEASE_TAG"]
    if not re.fullmatch(r"[a-z0-9._/-]+", repository) or not re.fullmatch(
        r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}", version
    ):
        parser.error("Invalid Docker repository or version tag")
    receipt = {
        "repository": repository,
        "version": version,
        "stage": args.stage,
        "source_commit": os.environ.get("GITHUB_SHA"),
        "run_id": os.environ.get("GITHUB_RUN_ID"),
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "upstream_artifact_id": os.environ.get("UPSTREAM_ARTIFACT_ID"),
        "status": "failed",
    }
    try:
        (publish_version if args.stage == "version" else promote_latest)(repository, version, receipt)
        receipt["status"] = "success"
    except Exception as error:
        receipt["error"] = str(error)
        raise
    finally:
        content = json.dumps(receipt, indent=2) + "\n"
        Path(f"{args.stage}-receipt.json").write_text(content)
        if os.environ.get("GITHUB_STEP_SUMMARY"):
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as summary:
                summary.write(f"### Container {args.stage} receipt\n\n```json\n{content}```\n")


if __name__ == "__main__":
    main()
