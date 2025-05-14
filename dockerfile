# Base CUDA image
FROM cnstark/pytorch:2.3.1-py3.10.15-cuda12.1.0-ubuntu22.04

# Install 3rd party apps
RUN apt-get update -y && \
    apt-get install -y --no-install-recommends ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set up working directory and permissions
WORKDIR /workspace

# Copy only requirements.txt initially to leverage Docker cache
COPY requirements.txt /workspace/

RUN pip install --no-cache-dir -r requirements.txt && \
    pip cache purge

# Copy application code and assets
COPY ./indextts /workspace/indextts/
COPY ./webui /workspace/webui/

# Expose the port used by the web UI
EXPOSE 7860

# Set the entry point command
CMD ["python", "-m", "webui.app"]
