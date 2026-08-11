#!/bin/bash
set -e

# Default values
HOST="${INDXTTS_HOST:-0.0.0.0}"
PORT="${INDXTTS_PORT:-7860}"
MODEL_DIR="${INDXTTS_MODEL_DIR:-./checkpoints}"
VERSION="${INDXTTS_VERSION:-2.5}"
FP16="${INDXTTS_FP16:-false}"
DEEPSPEED="${INDXTTS_DEEPSPEED:-false}"
CUDA_KERNEL="${INDXTTS_CUDA_KERNEL:-false}"
ACCEL="${INDXTTS_ACCEL:-false}"
TORCH_COMPILE="${INDXTTS_TORCH_COMPILE:-false}"
GUI_SEG_TOKENS="${INDXTTS_GUI_SEG_TOKENS:-120}"
VERBOSE="${INDXTTS_VERBOSE:-false}"

# Validate model version
if [ "$VERSION" != "2" ] && [ "$VERSION" != "2.5" ]; then
    echo "Error: Invalid model version $VERSION. Must be '2' or '2.5'."
    exit 1
fi

# Build command arguments
CMD_ARGS="--host $HOST --port $PORT --model_dir $MODEL_DIR --version $VERSION"

if [ "$FP16" = "true" ]; then
    CMD_ARGS="$CMD_ARGS --fp16"
fi

if [ "$DEEPSPEED" = "true" ]; then
    CMD_ARGS="$CMD_ARGS --deepspeed"
fi

if [ "$CUDA_KERNEL" = "true" ]; then
    CMD_ARGS="$CMD_ARGS --cuda_kernel"
fi

if [ "$ACCEL" = "true" ]; then
    CMD_ARGS="$CMD_ARGS --accel"
fi

if [ "$TORCH_COMPILE" = "true" ]; then
    CMD_ARGS="$CMD_ARGS --torch_compile"
fi

if [ "$VERBOSE" = "true" ]; then
    CMD_ARGS="$CMD_ARGS --verbose"
fi

CMD_ARGS="$CMD_ARGS --gui_seg_tokens $GUI_SEG_TOKENS"

# Check if model directory exists
if [ ! -d "$MODEL_DIR" ]; then
    echo "Error: Model directory $MODEL_DIR does not exist."
    echo "Please mount the model checkpoints directory to $MODEL_DIR"
    echo "or set INDXTTS_MODEL_DIR to the correct path."
    exit 1
fi

# File integrity is checked by webui.py itself: missing files for the selected
# --version are downloaded automatically (snapshot_download). Note that a
# read-only mount (e.g. docker-compose `:ro`) will block auto-download.
echo "Starting IndexTTS WebUI..."
echo "Host: $HOST"
echo "Port: $PORT"
echo "Model directory: $MODEL_DIR"
echo "Model version: $VERSION"
echo "FP16: $FP16"
echo "DeepSpeed: $DEEPSPEED"
echo "CUDA Kernel: $CUDA_KERNEL"
echo "Accel: $ACCEL"
echo "Torch Compile: $TORCH_COMPILE"
echo "GUI Seg Tokens: $GUI_SEG_TOKENS"

# Execute the WebUI with all arguments
exec /app/.venv/bin/python3 webui.py $CMD_ARGS
