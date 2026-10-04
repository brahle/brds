"""Offline publication checks: no credentials, registry or running images."""

import importlib.util
import io
import itertools
import json
from pathlib import Path
import re
import subprocess
import sys
import tarfile

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("publish_container", ROOT / "scripts/publish_container.py")
publisher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(publisher)
REPOSITORY = "example/brds"
DIGEST = "sha256:" + "1" * 64
IMAGE_ID = "sha256:" + "2" * 64
OLD_DIGEST = "sha256:" + "3" * 64


class Registry:
    def __init__(self, current="0.12.1", digest=OLD_DIGEST):
        self.images = {}
        self.calls = []
        self.fail = None
        if current is not None:
            self.add(current, digest, "sha256:" + "4" * 64, f"{REPOSITORY}:latest")

    def add(self, version, digest=DIGEST, image_id=IMAGE_ID, name=None):
        image = {"Id": image_id, "Config": {"Labels": {publisher.VERSION_LABEL: version}}, "digest": digest}
        self.images[f"{REPOSITORY}@{digest}"] = image
        if name:
            self.images[name] = image

    def docker(self, *args, allow_missing=False):
        self.calls.append(args)
        if args[0] == self.fail:
            raise RuntimeError("synthetic registry failure")
        if args[0] == "pull":
            image = self.images.get(args[-1])
            if not image and allow_missing:
                return None
            return f"Digest: {image['digest']}\nStatus: Downloaded\n"
        if args[:2] == ("image", "inspect"):
            return json.dumps([self.images[args[-1]]])
        if args[0] == "tag":
            self.images[args[2]] = self.images[args[1]]
            return ""
        if args[0] == "push":
            return f"{args[-1].rsplit(':', 1)[1]}: digest: {self.images[args[-1]]['digest']} size: 1234\n"
        raise AssertionError(f"Unexpected Docker operation: {args}")


def version_receipt(version="0.13.0", digest=DIGEST, image_id=IMAGE_ID):
    return {
        "status": "success",
        "repository": REPOSITORY,
        "version": version,
        "digest": digest,
        "image_id": image_id,
    }


@pytest.fixture
def registry(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    instance = Registry()
    instance.add("0.13.0")
    monkeypatch.setattr(publisher, "docker", instance.docker)
    Path("version-receipt.json").write_text(json.dumps(version_receipt()))
    return instance


def test_promote_pulls_and_tags_the_recorded_digest(registry):
    receipt = {}
    publisher.promote_latest(REPOSITORY, "0.13.0", receipt)
    assert receipt["previous_version"] == "0.12.1"
    assert receipt["latest_digest"] == DIGEST
    assert ("tag", f"{REPOSITORY}@{DIGEST}", f"{REPOSITORY}:latest") in registry.calls
    assert all(call[0] not in {"run", "build"} for call in registry.calls)


@pytest.mark.parametrize("version", ["0.12.0", "0.9.99", "0.10.99"])
def test_older_hotfix_publishes_no_latest(registry, version):
    Path("version-receipt.json").write_text(json.dumps(version_receipt(version)))
    receipt = {}
    publisher.promote_latest(REPOSITORY, version, receipt)
    assert receipt["decision"] == "skipped-older-version"
    assert not any(call[0] in {"tag", "push"} for call in registry.calls)


@pytest.mark.parametrize("version", ["0.14.0rc1", "0.14.0.dev1", "0.14.0.post1", "v0.14.0", "00.14.0"])
def test_noncanonical_and_prerelease_tags_do_not_touch_latest(registry, version):
    Path("version-receipt.json").write_text(json.dumps(version_receipt(version)))
    receipt = {}
    publisher.promote_latest(REPOSITORY, version, receipt)
    assert receipt["decision"] == "skipped-non-stable-version"
    assert registry.calls == []


def test_all_completion_orders_end_at_the_highest_stable_version(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    versions = ["0.12.2", "0.13.0", "0.12.9", "0.14.0rc1"]
    for order in itertools.permutations(versions):
        registry = Registry()
        monkeypatch.setattr(publisher, "docker", registry.docker)
        for index, version in enumerate(order, 5):
            digest = "sha256:" + str(index) * 64
            registry.add(version, digest)
            Path("version-receipt.json").write_text(json.dumps(version_receipt(version, digest)))
            publisher.promote_latest(REPOSITORY, version, {})
        assert registry.images[f"{REPOSITORY}:latest"]["Config"]["Labels"][publisher.VERSION_LABEL] == "0.13.0"


def test_first_latest_and_same_digest_retry(registry):
    del registry.images[f"{REPOSITORY}:latest"]
    receipt = {}
    publisher.promote_latest(REPOSITORY, "0.13.0", receipt)
    assert receipt["decision"] == "promoted-latest"
    registry.calls.clear()
    receipt = {}
    publisher.promote_latest(REPOSITORY, "0.13.0", receipt)
    assert receipt["decision"] == "already-current"
    assert not any(call[0] == "push" for call in registry.calls)


def test_same_version_with_another_digest_is_refused(registry):
    registry.add("0.13.0", OLD_DIGEST, name=f"{REPOSITORY}:latest")
    with pytest.raises(RuntimeError, match="different digest"):
        publisher.promote_latest(REPOSITORY, "0.13.0", {})
    assert not any(call[0] == "push" for call in registry.calls)


@pytest.mark.parametrize(
    "field,value",
    [
        ("status", "failed"),
        ("repository", "other/brds"),
        ("version", "0.13.1"),
        ("digest", "sha256:bad"),
        ("image_id", "sha256:bad"),
    ],
)
def test_invalid_upstream_receipt_never_touches_registry(registry, field, value):
    receipt = version_receipt()
    receipt[field] = value
    Path("version-receipt.json").write_text(json.dumps(receipt))
    with pytest.raises(RuntimeError, match="Invalid upstream"):
        publisher.promote_latest(REPOSITORY, "0.13.0", {})
    assert registry.calls == []


def test_digest_pull_must_retain_the_validated_image_id(registry):
    registry.images[f"{REPOSITORY}@{DIGEST}"]["Id"] = OLD_DIGEST
    with pytest.raises(RuntimeError, match="differs from the validated"):
        publisher.promote_latest(REPOSITORY, "0.13.0", {})
    assert not any(call[0] == "push" for call in registry.calls)


def test_unknown_latest_version_refuses_promotion(registry):
    registry.add("unknown", OLD_DIGEST, name=f"{REPOSITORY}:latest")
    with pytest.raises(RuntimeError, match="unrecognized stable version"):
        publisher.promote_latest(REPOSITORY, "0.13.0", {})
    assert not any(call[0] == "push" for call in registry.calls)


@pytest.mark.parametrize("version", ["0.13.0", "0.12.0", "0.14.0rc1"])
def test_version_only_publication_retains_archive_and_registry_receipts(registry, version):
    registry.add(version, name="brds:release-test")
    Path("image.id").write_text(IMAGE_ID + "\n")
    Path("image.sha256").write_text("a" * 64 + "  image.tar.gz\n")
    receipt = {}
    publisher.publish_version(REPOSITORY, version, receipt)
    assert receipt["digest"] == DIGEST
    assert receipt["archive_sha256"] == "a" * 64
    assert receipt["immutable_reference"] == f"{REPOSITORY}@{DIGEST}"
    assert ("push", f"{REPOSITORY}:{version}") in registry.calls
    assert not any(":latest" in arg for call in registry.calls for arg in call)


@pytest.mark.parametrize("mismatch", ["version", "id"])
def test_loaded_image_mismatch_blocks_publication(registry, mismatch):
    registry.add("0.12.1" if mismatch == "version" else "0.13.0", name="brds:release-test")
    Path("image.id").write_text(OLD_DIGEST if mismatch == "id" else IMAGE_ID)
    with pytest.raises(RuntimeError, match="differs"):
        publisher.publish_version(REPOSITORY, "0.13.0", {})
    assert not any(call[0] == "push" for call in registry.calls)


def test_failed_promotion_leaves_receipt_and_successful_version(registry, monkeypatch):
    registry.fail = "push"
    monkeypatch.setattr(sys, "argv", ["publish_container.py", "latest"])
    monkeypatch.setenv("IMAGE_REPOSITORY", REPOSITORY)
    monkeypatch.setenv("RELEASE_TAG", "0.13.0")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", "summary.md")
    with pytest.raises(RuntimeError, match="synthetic registry failure"):
        publisher.main()
    receipt = json.loads(Path("latest-receipt.json").read_text())
    assert receipt["status"] == "failed"
    assert receipt["previous_digest"] == OLD_DIGEST
    assert receipt["digest"] == DIGEST
    assert json.loads(Path("version-receipt.json").read_text())["status"] == "success"
    assert '"status": "failed"' in Path("summary.md").read_text()


@pytest.mark.parametrize(
    "error", ["unauthorized", "rate limit exceeded", "connection refused", "manifest unknown: unauthorized"]
)
def test_registry_errors_fail_closed(monkeypatch, error):
    # Test the subprocess boundary, not the fake registry's missing-tag behavior.
    monkeypatch.setattr(publisher.subprocess, "run", lambda *a, **kw: subprocess.CompletedProcess(a, 1, "", error))
    with pytest.raises(RuntimeError, match="docker pull failed"):
        publisher.docker("pull", "example/brds:latest", allow_missing=True)


def test_only_explicit_missing_manifest_allows_bootstrap(monkeypatch):
    monkeypatch.setattr(
        publisher.subprocess,
        "run",
        lambda *a, **kw: subprocess.CompletedProcess(
            a, 1, "", "Error response from daemon: manifest for example/brds:latest not found: manifest unknown"
        ),
    )
    assert publisher.docker("pull", "example/brds:latest", allow_missing=True) is None


def archive_bytes(entries):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as archive:
        for path, content in entries:
            data = content.encode()
            info = tarfile.TarInfo(path)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return stream.getvalue()


def test_legacy_image_version_comes_from_stopped_container_metadata(monkeypatch):
    calls = []

    def docker(*args):
        calls.append(args)
        if args[:2] == ("image", "inspect"):
            return '[{"Config":{"Labels":null}}]'
        if args[0] == "create":
            return "stopped-container\n"
        assert args == ("rm", "stopped-container")

    def export(args, stdout, **kwargs):
        assert args == ["docker", "export", "stopped-container"]
        stdout.write(
            archive_bytes(
                [
                    (
                        "usr/local/lib/python3.9/site-packages/brds-0.12.1.dist-info/METADATA",
                        "Name: brds\nVersion: 0.12.1\n",
                    )
                ]
            )
        )

    monkeypatch.setattr(publisher, "docker", docker)
    monkeypatch.setattr(publisher.subprocess, "run", export)
    assert publisher.image_version("example/brds@" + OLD_DIGEST) == "0.12.1"
    assert calls[-1] == ("rm", "stopped-container")
    assert not any(call[0] == "run" for call in calls)


def test_legacy_export_failure_removes_the_stopped_container(monkeypatch):
    calls = []

    def docker(*args):
        calls.append(args)
        if args[:2] == ("image", "inspect"):
            return '[{"Config":{"Labels":null}}]'
        return "stopped-container\n"

    def export(*args, **kwargs):
        raise subprocess.CalledProcessError(1, ["docker", "export", "stopped-container"])

    monkeypatch.setattr(publisher, "docker", docker)
    monkeypatch.setattr(publisher.subprocess, "run", export)
    with pytest.raises(subprocess.CalledProcessError):
        publisher.image_version("example/brds@" + OLD_DIGEST)
    assert calls[-1] == ("rm", "stopped-container")


def test_successful_cli_receipt_records_run_provenance(registry, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["publish_container.py", "latest"])
    for name, value in {
        "IMAGE_REPOSITORY": REPOSITORY,
        "RELEASE_TAG": "0.13.0",
        "GITHUB_SHA": "a" * 40,
        "GITHUB_RUN_ID": "123",
        "GITHUB_RUN_ATTEMPT": "2",
        "UPSTREAM_ARTIFACT_ID": "456",
    }.items():
        monkeypatch.setenv(name, value)
    publisher.main()
    receipt = json.loads(Path("latest-receipt.json").read_text())
    assert receipt["status"] == "success"
    assert receipt["source_commit"] == "a" * 40
    assert (receipt["run_id"], receipt["run_attempt"], receipt["upstream_artifact_id"]) == ("123", "2", "456")


def test_failed_version_push_retains_validated_image_evidence(registry, monkeypatch):
    registry.add("0.13.0", name="brds:release-test")
    Path("image.id").write_text(IMAGE_ID)
    Path("image.sha256").write_text("a" * 64 + "  image.tar.gz\n")
    registry.fail = "push"
    monkeypatch.setattr(sys, "argv", ["publish_container.py", "version"])
    monkeypatch.setenv("IMAGE_REPOSITORY", REPOSITORY)
    monkeypatch.setenv("RELEASE_TAG", "0.13.0")
    with pytest.raises(RuntimeError):
        publisher.main()
    receipt = json.loads(Path("version-receipt.json").read_text())
    assert receipt["status"] == "failed"
    assert receipt["image_id"] == IMAGE_ID
    assert receipt["archive_sha256"] == "a" * 64
    assert "digest" not in receipt


@pytest.mark.parametrize(
    "entries",
    [
        [],
        [("brds-0.12.1.dist-info/METADATA", "Name: brds\nVersion: 0.12.1\n")],
        [("lib/brds-0.12.1.dist-info/METADATA", "Name: brds\nVersion: 0.12.1\nVersion: 99.0.0\n")],
        [("lib/brds-0.12.1.dist-info/METADATA", "Name: other\nVersion: 0.12.1\n")],
        [
            ("lib/brds-0.12.1.dist-info/METADATA", "Name: brds\nVersion: 0.12.1\n"),
            ("lib/brds-0.13.0.dist-info/METADATA", "Name: brds\nVersion: 0.13.0\n"),
        ],
    ],
)
def test_ambiguous_or_missing_legacy_metadata_is_refused(entries):
    with tarfile.open(fileobj=io.BytesIO(archive_bytes(entries))) as archive:
        with pytest.raises(RuntimeError):
            publisher.legacy_version(archive)


def test_push_receipt_needs_manifest_digest_not_config_id():
    assert publisher.pushed_digest(f"0.13.0: digest: {DIGEST} size: 1234\n") == DIGEST
    with pytest.raises(RuntimeError):
        publisher.pushed_digest(f"Loaded image ID: {IMAGE_ID}\n")


def workflow():
    return yaml.safe_load((ROOT / ".github/workflows/release.yml").read_text())


def test_publication_dependencies_block_every_downstream_stage():
    jobs = workflow()["jobs"]
    assert jobs["release"]["needs"] == "validate"
    assert jobs["release"]["if"] == "github.ref_type == 'tag'"
    assert set(jobs["deploy"]["needs"]) == {"validate", "release"}
    assert set(jobs["build-and-push"]["needs"]) == {"validate", "deploy"}
    assert jobs["promote-latest"]["needs"] == "build-and-push"
    for name in ["deploy", "build-and-push", "promote-latest"]:
        assert "if" not in jobs[name]  # Default success gate; no always() bypass.
        assert not any("build-push-action" in step.get("uses", "") for step in jobs[name]["steps"])
    assert jobs["promote-latest"]["concurrency"] == {
        "group": "brds-container-latest",
        "queue": "max",
        "cancel-in-progress": False,
    }


def test_workflow_downloads_exact_upstream_artifact_ids_and_retains_checksums():
    jobs = workflow()["jobs"]
    for name, expression in [
        ("deploy", "${{ needs.validate.outputs.distributions_artifact_id }}"),
        ("build-and-push", "${{ needs.validate.outputs.container_artifact_id }}"),
        ("promote-latest", "${{ needs.build-and-push.outputs.receipt_artifact_id }}"),
    ]:
        downloads = [step for step in jobs[name]["steps"] if "download-artifact" in step.get("uses", "")]
        assert [step["with"]["artifact-ids"] for step in downloads] == [expression]
    commands = "\n".join(step.get("run", "") for step in jobs["build-and-push"]["steps"])
    assert "sha256sum --check image.sha256" in commands
    assert "docker load --input image.tar.gz" in commands
    assert "$(cat image.id)" in commands
    for name in ["build-and-push", "promote-latest"]:
        uploads = [step for step in jobs[name]["steps"] if "upload-artifact" in step.get("uses", "")]
        assert len(uploads) == 1
        assert uploads[0]["if"].startswith("always() && hashFiles(")
        assert uploads[0]["with"]["if-no-files-found"] == "error"


def test_all_workflow_actions_are_immutable_commits():
    for path in (ROOT / ".github/workflows").glob("*.yml"):
        for job in yaml.safe_load(path.read_text())["jobs"].values():
            for step in job["steps"]:
                if "uses" in step:
                    assert re.fullmatch(r"[\w-]+/[\w-]+@[0-9a-f]{40}", step["uses"]), step["uses"]


def test_documented_smoke_tag_matches_the_validated_image():
    steps = workflow()["jobs"]["validate"]["steps"]
    built = next(step for step in steps if "build-push-action" in step.get("uses", ""))
    assert built["with"]["tags"] == "brds:release-test"
    assert "org.opencontainers.image.version=${{ steps.metadata.outputs.version }}" in built["with"]["labels"]
    document = (ROOT / "docs/container-release.md").read_text()
    assert "brds:container-test" not in document
    assert "python3 scripts/check_container.py brds:release-test" in document
