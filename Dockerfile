FROM python:3.12-slim

ARG TARGETARCH=amd64
ARG LITESTREAM_VERSION=0.5.18

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && case "${TARGETARCH}" in amd64) LITESTREAM_ARCH=x86_64 ;; arm64) LITESTREAM_ARCH=arm64 ;; *) echo "Unsupported architecture: ${TARGETARCH}" >&2; exit 1 ;; esac \
    && curl -fsSL "https://github.com/benbjohnson/litestream/releases/download/v${LITESTREAM_VERSION}/litestream-${LITESTREAM_VERSION}-linux-${LITESTREAM_ARCH}.deb" -o /tmp/litestream.deb \
    && curl -fsSL "https://github.com/benbjohnson/litestream/releases/download/v${LITESTREAM_VERSION}/checksums.txt" -o /tmp/litestream-checksums.txt \
    && grep "  litestream-${LITESTREAM_VERSION}-linux-${LITESTREAM_ARCH}.deb$" /tmp/litestream-checksums.txt | sha256sum -c - \
    && apt-get install -y --no-install-recommends /tmp/litestream.deb \
    && rm -f /tmp/litestream.deb /tmp/litestream-checksums.txt \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /data

ENV DATABASE_PATH=/data/eivorak_brain.db
CMD ["python", "scripts/start.py"]
