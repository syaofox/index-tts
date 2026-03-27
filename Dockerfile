FROM nvidia/cuda:12.8.0-devel-ubuntu22.04

# Prevent interactive prompts during apt-get install
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies for audio and locale
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ffmpeg \
    libsndfile1 \
    locales \
    language-pack-zh-hans \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Generate Chinese locale
RUN locale-gen zh_CN.UTF-8

# Install uv from official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set environment variables
ENV LANG=zh_CN.UTF-8
ENV LC_ALL=zh_CN.UTF-8
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_PYTHON=3.10
ENV UV_HTTP_TIMEOUT=300
ENV CUDA_HOME=/usr/local/cuda
ENV PATH="/usr/local/cuda/bin:$PATH"

WORKDIR /app

# Copy project files
COPY . .

# Create non-root user and take ownership of /app
RUN useradd -m -u 1000 appuser \
    && chown -R appuser:appuser /app

USER appuser

# Install Python, dependencies and project
RUN --mount=type=cache,target=/tmp/uv-cache,uid=1000,gid=1000 \
    UV_CACHE_DIR=/tmp/uv-cache uv sync --frozen --no-dev --all-extras

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"
ENV PYTHONUNBUFFERED=1

# Create directories for models, outputs, and DeepSpeed CUDA extension cache
RUN mkdir -p /app/checkpoints /app/outputs /home/appuser/.cache /home/appuser/.triton/autotune \
    && chmod +x /app/docker-entrypoint.sh

# Expose WebUI port
EXPOSE 7860

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:7860/ || exit 1

# Start WebUI
CMD ["/app/docker-entrypoint.sh"]
