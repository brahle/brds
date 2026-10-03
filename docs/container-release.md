# Container release

The standalone API image is built for `linux/amd64`. Its Python 3.14.7
Debian slim base is pinned by OCI digest. Runtime dependencies must install
from binary wheels; the build no longer installs Debian compiler or BLAS
packages. This removes the release failure caused by `libatlas-base-dev`
being unavailable in the floating base's repositories.

The image retains `/data` as its default store and serves port 8080. Bind a
store to `/data` to expose its versioned datasets through the existing API.
Direct file URLs use a static reader; dataset URLs continue to resolve the
latest dated version. Dictionary responses are lists of records, and dataset
pages use the current request-first template API.

## Check before publishing

Pull-request CI builds the image without registry credentials and runs:

```sh
docker build --platform linux/amd64 -t brds:container-test -f Containerfile .
python3 scripts/check_container.py brds:container-test
```

The check writes synthetic Parquet and JSON inside a temporary mounted store,
starts the image's default server on a loopback-only ephemeral port, and checks
its readers, JSON and HTML routes, latest-version dataset access, dataset
templates, downloads and a missing-file 404. It also checks that development
and build/publish tools are absent from the runtime. Its named server is removed on
success or failure. It requires Docker and a host Python 3 interpreter, with
no host Python packages or production data.

The release workflow runs validation on pull requests and main pushes, and on
release tags. A manual run on a branch validates only; publication requires a
tag matching `brds/VERSION` exactly. It builds the wheel and source distribution
in a separate stage, installs that wheel in the runtime image, smoke-tests the
image and runs `twine check --strict` on those distributions. Both distributions
and the Docker archive are saved as artifacts with SHA-256 receipts; the image
receipt also records its image ID.

The publication chain is **validation → GitHub release → PyPI → Docker Hub**.
A failed/skipped upstream job blocks subsequent publication. The PyPI job
verifies and uploads the saved distributions. Only after it succeeds does the
Docker job verify the archive and image ID, load it, and tag/push that same
image. Neither publication job rebuilds. Artifact downloads use IDs returned by the successful validation job within
the same workflow run. Upload names include the run attempt, so rerunning
validation produces fresh artifacts and a publication-only retry reuses its
validated upstream IDs. Artifacts are retained for seven days; after expiry a new
validation run is needed. A partial registry failure remains a failed job;
there is no automatic rollback of a completed GitHub/PyPI publication.

## Dependency inputs

`requirements.txt` describes library runtime dependencies for PyPI consumers;
it keeps normal dependency resolution for supported consumer environments.
Type checkers and stubs belong to `requirements-test.txt`, never the runtime
image. PyYAML is an explicit runtime requirement because crawler configuration
imports it. The three platform-specific release locks pin every resolved wheel
and SHA-256 hash:

- `requirements-container.lock`: runtime dependencies for Python 3.14.7,
  Linux amd64, including transitive dependencies.
- `requirements-build.lock`: the pinned PEP 517 backend from `pyproject.toml`,
  the build frontend and their dependencies, used only in the build stage.
- `requirements-publish.lock`: Twine and its dependencies, used only on the
  validation/PyPI runners.

Template lookup uses the installed package location, so the server and its
HTML pages also work outside a source checkout. The final image contains the
runtime and packaged BRDS wheel, plus its small
release distributions; it contains no type checker, stubs or build/publish tools.
The source distribution includes the requirement files needed by its backend.
The locks deliberately cover the advertised image/release platform, rather than
constraining the library's Python 3.9 consumer CI to Python 3.14 wheels.

To refresh a lock, run the maintenance resolver inside the same pinned base
from the repository root (change the last argument to `build` or `publish`):

```sh
docker run --rm --platform linux/amd64 \
  --mount "type=bind,source=$PWD,target=/src" --workdir /src \
  python:3.14.7-slim-trixie@sha256:51dafde81dbdb6ebde285137a295cf18a47ca95234fe388a343719cb97305b3d \
  python scripts/lock_container_dependencies.py container
```

Review the changed versions/hashes, rebuild the image, run the smoke check and
validate the distributions before committing refreshed locks. A new Python,
base platform or backend also requires regenerating the applicable locks.
Hash-checking and binary-only installation fail closed if a locked wheel is
missing or differs. These locks fix dependency inputs; they do not promise
byte-for-byte rebuilds across source timestamps or build-tool metadata.

## Consumer scope and maintenance

The inspected FPL setup installs brds from PyPI and builds its own FPL image.
The inspected repository and deployment configuration contain no known fleet
consumer of the published brds image. This does not establish that a public
Docker Hub image has no external users. The repository still supplies the
standalone API and `make docker-run`, so this change preserves that artifact
for review rather than silently removing it. If the owner retires the API
image, removing the release job is a separate valid choice.

The base digest fixes the OS/Python input, and the release locks fix Python
wheel inputs. Changing these inputs must pass the image check. The workflow
does not promise a multi-platform release.
