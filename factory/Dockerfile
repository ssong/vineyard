# Multi-stage build for smaller image
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Production stage
FROM python:3.11-slim

WORKDIR /app

# Install curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code and prompts
COPY src/ ./src/
COPY prompts/ ./prompts/

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash vineyard && \
    chown -R vineyard:vineyard /app

USER vineyard

# Expose API port for webhooks
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Default: run both Slack bot and API server
CMD ["python", "-m", "src.main"]

# Alternative modes:
# API only: CMD ["python", "-m", "src.main", "--mode", "api"]
# Slack only: CMD ["python", "-m", "src.main", "--mode", "slack"]
