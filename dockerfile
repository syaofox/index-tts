# Base CUDA image
FROM cnstark/pytorch:2.3.1-py3.10.15-cuda12.1.0-ubuntu22.04

# Set up working directory
WORKDIR /app

# Copy requirements.txt
COPY requirements.txt /app/

# Install all dependencies and clean up cache
RUN apt-get update -y && \
    apt-get install -y --no-install-recommends ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    pip install --no-cache-dir -r requirements.txt && \
    pip cache purge && \
    find /usr -name "__pycache__" -type d -exec rm -rf {} +  2>/dev/null || true && \
    find /usr -name "*.pyc" -delete

# Copy application code
COPY ./indextts /app/indextts/
COPY ./webui /app/webui/

# Remove unnecessary files
RUN find /app -type d -name "__pycache__" -exec rm -rf {} +  2>/dev/null || true && \
    find /app -name "*.pyc" -delete

# Expose the port used by the web UI
EXPOSE 7860

# Set the entry point command
CMD ["python", "-m", "webui.app"]
