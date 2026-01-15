# =============================================================================
# MedSafe Dockerfile
# PHASE 1: Standardized production-ready container
# =============================================================================

FROM python:3.10-slim AS base

# =============================================================================
# BUILD ARGUMENTS & ENVIRONMENT
# =============================================================================
ARG BUILD_DATE
ARG VERSION="2.0.0"
ARG GIT_COMMIT

LABEL org.opencontainers.image.title="MedSafe"
LABEL org.opencontainers.image.description="Medical Drug Contraindication System"
LABEL org.opencontainers.image.version="${VERSION}"
LABEL org.opencontainers.image.created="${BUILD_DATE}"
LABEL org.opencontainers.image.revision="${GIT_COMMIT}"
LABEL org.opencontainers.image.vendor="MedSafe Team"

# Avoid interactive prompts
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# =============================================================================
# SYSTEM DEPENDENCIES
# =============================================================================
RUN apt-get update && apt-get install -y --no-install-recommends \
    # OCR dependencies
    tesseract-ocr \
    tesseract-ocr-por \
    tesseract-ocr-eng \
    # Image processing
    libgl1 \
    libglib2.0-0 \
    # Network utilities
    curl \
    ca-certificates \
    # PostgreSQL client
    libpq-dev \
    # Build tools (for some Python packages)
    gcc \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /tmp/* \
    && rm -rf /var/tmp/*

# =============================================================================
# NON-ROOT USER (Security best practice)
# =============================================================================
RUN groupadd -r medsafe --gid=1000 \
    && useradd -r -g medsafe --uid=1000 --home-dir=/app --shell=/sbin/nologin medsafe

# =============================================================================
# WORKING DIRECTORY
# =============================================================================
WORKDIR /app
ENV PYTHONPATH=/app:$PYTHONPATH

# =============================================================================
# PYTHON DEPENDENCIES
# =============================================================================
# Copy requirements first for better Docker layer caching
COPY requirements.txt ./

RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt

# =============================================================================
# APPLICATION CODE
# =============================================================================
COPY --chown=medsafe:medsafe backend/ ./backend/
COPY --chown=medsafe:medsafe frontend/ ./frontend/
COPY --chown=medsafe:medsafe static/ ./static/
COPY --chown=medsafe:medsafe alembic/ ./alembic/
COPY --chown=medsafe:medsafe alembic.ini ./

# Create necessary directories
RUN mkdir -p logs data static/uploads \
    && chown -R medsafe:medsafe /app

# =============================================================================
# RUNTIME CONFIGURATION
# =============================================================================
# Switch to non-root user
USER medsafe

# Expose port
EXPOSE 9000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:9000/healthz || exit 1

# Default command
# SECURITY: disable Server: uvicorn header
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "9000", "--no-server-header"]
