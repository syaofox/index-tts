# Stage 1: Build stage
FROM nvidia/cuda:12.8.0-runtime-ubuntu22.04 AS builder

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3.10-venv \
    python3-pip \
    git \
    curl \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Set Python 3.10 as default
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1 \
    && update-alternatives --install /usr/bin/python python /usr/bin/python3.10 1

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies with uv (including webui optional dependency)
RUN uv sync --frozen --no-dev --no-install-project --extra webui

# Copy project files
COPY . .

# Install project in development mode
RUN uv sync --frozen --no-dev --extra webui

# Stage 2: Runtime stage
FROM nvidia/cuda:12.8.0-runtime-ubuntu22.04

# Install runtime system dependencies + Chinese locale
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3.10-venv \
    ffmpeg \
    libsndfile1 \
    curl \
    locales \
    language-pack-zh-hans \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Generate Chinese locale
RUN locale-gen zh_CN.UTF-8

# Set Python 3.10 as default
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1 \
    && update-alternatives --install /usr/bin/python python /usr/bin/python3.10 1

# Create non-root user
RUN useradd -m -u 1000 appuser
USER appuser
WORKDIR /home/appuser/app

# Copy virtual environment from builder
COPY --from=builder --chown=appuser:appuser /app/.venv /home/appuser/app/.venv
COPY --from=builder --chown=appuser:appuser /app /home/appuser/app

# Copy entrypoint script
COPY --from=builder --chown=appuser:appuser /app/docker-entrypoint.sh /home/appuser/app/docker-entrypoint.sh

# Set environment variables
ENV PATH="/home/appuser/app/.venv/bin:$PATH"
ENV PYTHONPATH="/home/appuser/app"
ENV PYTHONUNBUFFERED=1
ENV LANG=zh_CN.UTF-8
ENV LC_ALL=zh_CN.UTF-8

# Create directories for models and outputs
RUN mkdir -p /home/appuser/app/checkpoints /home/appuser/app/outputs

# Expose WebUI port
EXPOSE 7860

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:7860/ || exit 1

# Start WebUI
CMD ["/home/appuser/app/docker-entrypoint.sh"]