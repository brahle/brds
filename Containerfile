FROM python:3.10-alpine
COPY . /app
WORKDIR /app
RUN apk update && apk add --no-cache \
    build-base \
    openblas-dev \
    lapack-dev \
    gfortran
RUN pip install .
CMD ["brds"]
