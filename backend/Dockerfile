# ==============================================================================
# Multi-stage Dockerfile for AI Office IT Help Desk FastAPI Backend
# ==============================================================================

# ------------------------------------------------------------------------------
# Stage 1: Build Dependencies
# ------------------------------------------------------------------------------
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ------------------------------------------------------------------------------
# Stage 2: Final Production Image
# ------------------------------------------------------------------------------
FROM python:3.12-slim AS runner

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy python packages from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Create non-root user
RUN useradd -u 10001 -m appuser && \
    mkdir -p /app/uploads && \
    chown -R appuser:appuser /app

# Copy application source
COPY . /app
RUN chown -R appuser:appuser /app

USER appuser

# Expose FastAPI port
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Launch production server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
