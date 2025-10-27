#!/bin/bash

# 获取脚本所在的目录，并切换到该目录
# 这使得脚本可以从任何位置被调用
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

# 设定 Hugging Face 和 ModelScope 的缓存路径，避免占用用户主目录空间
mkdir -p "$PWD/.cache/hf_download"
mkdir -p "$PWD/.cache/modelscope"

# 当任何命令执行失败时，立即退出脚本
set -e

export HF_HOME="$PWD/.cache/hf_download"
export MODELSCOPE_CACHE="$PWD/.cache/modelscope"

uv run webui.py --verbose --fp16 --deepspeed