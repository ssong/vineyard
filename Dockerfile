# =============================================================================
# Vineyard Bot - Unified Docker Image
# =============================================================================
# Combines Research Agent and Factory into a single container

FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies (including WeasyPrint requirements)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# =============================================================================
# Production Stage
# =============================================================================
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # WeasyPrint PDF generation
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi8 \
    shared-mime-info \
    fonts-liberation \
    fonts-dejavu-core \
    # Health check
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code - keep original directory names!
COPY main.py ./
COPY research-agent/ ./research-agent/
COPY factory/ ./factory/

# Create required directories
RUN mkdir -p /app/outputs /app/state && chmod 755 /app/outputs /app/state

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash vineyard && \
    chown -R vineyard:vineyard /app

USER vineyard

# Expose API port for Linear webhooks
EXPOSE 8000

# Health check - API endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# CRITICAL: Add both subdirectories to PYTHONPATH so internal imports work
# Each project's internal `from src.*` imports will resolve correctly
ENV PYTHONPATH=/app:/app/research-agent:/app/factory

# Default: run both Slack bot and API server
CMD ["python", "main.py"]

# Alternative modes:
# API only: CMD ["python", "main.py", "--mode", "api"]
# Slack only: CMD ["python", "main.py", "--mode", "slack"]

