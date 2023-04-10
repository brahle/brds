FROM python:3.10-slim
COPY . /app
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libatlas-base-dev \
    libblas-dev \
    liblapack-dev \
    gfortran && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/ && \
    pip install -e .
ENV ROOT_FOLDER_PATH /data
CMD ["/bin/bash", "/app/scripts/run_container.sh"]
