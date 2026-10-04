# Production Dockerfile for Google Cloud Run (Python 3.13 + uv)
FROM python:3.13-slim

# Prevent Python from buffering stdout and writing .pyc files
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080 \
    HOST=0.0.0.0

WORKDIR /workspace

# Install system utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install uv from official binary
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Copy dependency files and README for layer caching
COPY pyproject.toml uv.lock* README.md ./

# Install third-party dependencies into virtual environment without installing root project package yet
RUN uv sync --no-install-project

# Copy full application codebase
COPY . .

# Finalize project install into virtual environment
RUN uv sync

# Ensure non-root user execution
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /workspace
USER appuser

EXPOSE 8080

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
