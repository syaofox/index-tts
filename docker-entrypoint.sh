#!/bin/bash
set -e

# Default values
HOST="${INDXTTS_HOST:-0.0.0.0}"
PORT="${INDXTTS_PORT:-7860}"
MODEL_DIR="${INDXTTS_MODEL_DIR:-./checkpoints}"
FP16="${INDXTTS_FP16:-false}"
DEEPSPEED="${INDXTTS_DEEPSPEED:-false}"
CUDA_KERNEL="${INDXTTS_CUDA_KERNEL:-false}"
GUI_SEG_TOKENS="${INDXTTS_GUI_SEG_TOKENS:-120}"
VERBOSE="${INDXTTS_VERBOSE:-false}"

# Build command arguments
CMD_ARGS="--host $HOST --port $PORT --model_dir $MODEL_DIR"

if [ "$FP16" = "true" ]; then
    CMD_ARGS="$CMD_ARGS --fp16"
fi

if [ "$DEEPSPEED" = "true" ]; then
    CMD_ARGS="$CMD_ARGS --deepspeed"
fi

if [ "$CUDA_KERNEL" = "true" ]; then
    CMD_ARGS="$CMD_ARGS --cuda_kernel"
fi

if [ "$VERBOSE" = "true" ]; then
    CMD_ARGS="$CMD_ARGS --verbose"
fi

CMD_ARGS="$CMD_ARGS --gui_seg_tokens $GUI_SEG_TOKENS"

# Check if model directory exists
if [ ! -d "$MODEL_DIR" ]; then
    echo "Error: Model directory $MODEL_DIR does not exist."
    echo "Please mount the model checkpoints directory to $MODEL_DIR"
    exit 1
fi

# Check required model files
REQUIRED_FILES=("bpe.model" "gpt.pth" "config.yaml" "s2mel.pth" "wav2vec2bert_stats.pt")
for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$MODEL_DIR/$file" ]; then
        echo "Error: Required model file $MODEL_DIR/$file not found."
        exit 1
    fi
done

echo "Starting IndexTTS WebUI..."
echo "Host: $HOST"
echo "Port: $PORT"
echo "Model directory: $MODEL_DIR"
echo "FP16: $FP16"
echo "DeepSpeed: $DEEPSPEED"
echo "CUDA Kernel: $CUDA_KERNEL"
echo "GUI Seg Tokens: $GUI_SEG_TOKENS"

# Execute the WebUI with all arguments
exec python webui.py $CMD_ARGS