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
templates, downloads and a missing-file 404. Its named server is removed on
success or failure. It requires Docker and a host Python 3 interpreter, with
no host Python packages or production data.

The release job performs the same check **before** Docker Hub login and push.
An image failure remains a failed release job; it is not hidden with
`continue-on-error`. PyPI publishing remains a separate job. No release is
triggered by creating this PR.

## Consumer scope and maintenance

The inspected FPL setup installs brds from PyPI and builds its own FPL image.
The inspected repository and deployment configuration contain no known fleet
consumer of the published brds image. This does not establish that a public
Docker Hub image has no external users. The repository still supplies the
standalone API and `make docker-run`, so this change preserves that artifact
for review rather than silently removing it. If the owner retires the API
image, removing the release job is a separate valid choice.

The base digest fixes the OS/Python input; Python runtime requirements still
resolve their declared versions. Changing the base or dependency requirements
must pass the image check. Wheel availability is checked for the advertised
amd64 platform; this workflow does not promise a multi-platform release.
