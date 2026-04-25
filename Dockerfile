# syntax=docker/dockerfile:1.7
#
# geoseo-mcp container
#
# Builds a minimal image that runs `geoseo-mcp` over stdio (the MCP transport).
# Multi-stage to keep the runtime image small.
#
#   docker build -t geoseo-mcp .
#   docker run --rm -i geoseo-mcp
#
# All credentials are passed via environment variables, e.g.:
#   docker run --rm -i \
#     -e GEOSEO_PERPLEXITY_API_KEY=... \
#     -e GEOSEO_OPENAI_API_KEY=... \
#     geoseo-mcp

# ---- builder ----------------------------------------------------------------
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Install build deps (lxml needs libxml2/libxslt headers)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libxml2-dev \
        libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN pip install --upgrade pip build \
    && pip wheel --no-deps --wheel-dir /wheels . \
    && pip wheel --wheel-dir /wheels .

# ---- runtime ----------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Runtime deps for lxml (just the shared libs, not the -dev headers)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libxml2 \
        libxslt1.1 \
    && rm -rf /var/lib/apt/lists/*

# Non-root user
RUN useradd --create-home --shell /bin/bash mcp
WORKDIR /home/mcp

COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/*.whl \
    && rm -rf /wheels

USER mcp

# stdio is the MCP transport — no port to expose
ENTRYPOINT ["geoseo-mcp"]
