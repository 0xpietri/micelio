# syntax=docker/dockerfile:1
# Mycelium: one small container that reads a vault mounted read-only.

ARG PYTHON_VERSION=3.12

# --- build: resolve the locked dependencies and install the package into /app/.venv
FROM ghcr.io/astral-sh/uv:0.13 AS uv
FROM python:${PYTHON_VERSION}-slim AS build
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /src
# Dependencies first, so editing the code does not reinstall them.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project
COPY README.md LICENSE ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable

# --- runtime: Python and the virtual environment, nothing else
FROM python:${PYTHON_VERSION}-slim
ARG VERSION=dev
LABEL org.opencontainers.image.title="Mycelium" \
      org.opencontainers.image.description="Your Markdown notes as a living network of ideas" \
      org.opencontainers.image.source="https://github.com/0xpietri/mycelium" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="${VERSION}"

RUN groupadd --gid 10001 mycelium \
 && useradd --uid 10001 --no-log-init --gid mycelium --no-create-home --home-dir /data mycelium \
 && mkdir -p /vault /data \
 && chown mycelium:mycelium /data
COPY --from=build /app/.venv /app/.venv

ENV PATH=/app/.venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MYCELIUM_VAULT=/vault \
    MYCELIUM_DATA=/data \
    MYCELIUM_HOST=0.0.0.0 \
    MYCELIUM_PORT=8765

USER mycelium
WORKDIR /data
VOLUME ["/data"]
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen(f\"http://127.0.0.1:{os.environ.get('MYCELIUM_PORT', '8765')}/healthz\", timeout=4)"]
ENTRYPOINT ["mycelium"]
CMD ["serve"]
