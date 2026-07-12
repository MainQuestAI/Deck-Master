# syntax=docker/dockerfile:1
#
# Deck Master development container. Provides a reproducible environment with
# Python 3.12, dev dependencies, Playwright Chromium, and the editable install.
# Used for local development, the Review Desk, browser smoke, and rc-gate runs.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DECK_MASTER_DOCKER=1

# System dependencies for Playwright Chromium and python-pptx (lxml/Pillow).
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates git build-essential \
        libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
        libdrm2 libdbus-1-3 libxkbcommon0 libx11-6 libxcomposite1 \
        libxdamage1 libxext6 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 \
        libcairo2 libasound2 libatspi2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first (better layer caching).
COPY pyproject.toml ./
COPY scripts ./scripts
COPY skills ./skills
COPY docs/contracts ./docs/contracts
COPY examples ./examples
COPY tests ./tests

RUN python -m pip install --quiet -e ".[dev]" \
    && python -m playwright install --with-deps chromium

# Copy the rest of the repository for a full editable checkout.
COPY . .

# Default: run the Review Desk preview server on the fixture demo.
EXPOSE 5050
CMD ["python", "scripts/preview/server.py", "examples/preview-run", "--host", "0.0.0.0", "--port", "5050"]
