# EST Synthesizer — production image
# Python 3.12 slim with system libs for WeasyPrint + uv for dep management.

FROM python:3.12-slim

WORKDIR /app

# System deps: WeasyPrint needs Pango + Cairo + GdkPixbuf.
# curl for the healthcheck.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 \
        libpangoft2-1.0-0 \
        libcairo2 libcairo-gobject2 \
        libffi-dev libharfbuzz0b libxml2 libxslt1.1 \
        shared-mime-info \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv (the dep manager the project uses).
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy lockfile + manifest first for layer caching.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy the rest of the source.
COPY backend ./backend
COPY run.py ./
COPY litellm_proxy.yaml ./
COPY scripts ./scripts

# Runtime data dirs (mounted as volumes in compose, but created for safety).
RUN mkdir -p data/db data/generated data/logs

EXPOSE 8000

# Lightweight HTTP healthcheck — hits the FastAPI /health endpoint.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

# Run the app. UVICORN_RELOAD must stay False here.
ENV UVICORN_RELOAD=false
CMD ["uv", "run", "python", "run.py"]
