FROM python:3.14.7-slim-trixie@sha256:51dafde81dbdb6ebde285137a295cf18a47ca95234fe388a343719cb97305b3d AS build
WORKDIR /src
COPY requirements-build.lock .
RUN python -m pip install --no-cache-dir --only-binary=:all: --require-hashes -r requirements-build.lock
COPY . .
RUN python -m build --no-isolation

FROM python:3.14.7-slim-trixie@sha256:51dafde81dbdb6ebde285137a295cf18a47ca95234fe388a343719cb97305b3d
WORKDIR /app
COPY requirements-container.lock .
# Every runtime wheel and transitive dependency is pinned and hash-checked.
RUN python -m pip install --no-cache-dir --only-binary=:all: --require-hashes -r requirements-container.lock
# Retain the exact wheel/sdist for release validation and PyPI publication.
COPY --from=build /src/dist /opt/brds-dist
RUN python -m pip install --no-cache-dir --no-deps /opt/brds-dist/*.whl && python -m pip check
ENV ROOT_FOLDER_PATH=/data
CMD ["python", "-m", "uvicorn", "brds.app:app", "--host", "0.0.0.0", "--port", "8080"]
