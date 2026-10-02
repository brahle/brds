FROM python:3.14.7-slim-trixie@sha256:51dafde81dbdb6ebde285137a295cf18a47ca95234fe388a343719cb97305b3d
WORKDIR /app
COPY requirements.txt .
# Runtime dependencies have wheels; an unsupported platform must fail here
# rather than acquire an unpinned Debian compiler/BLAS toolchain.
RUN python -m pip install --no-cache-dir --only-binary=:all: -r requirements.txt
COPY . .
RUN python -m pip install --no-cache-dir --no-deps .
ENV ROOT_FOLDER_PATH=/data
CMD ["python", "-m", "uvicorn", "brds.app:app", "--host", "0.0.0.0", "--port", "8080"]
