#!/bin/bash

cd /home/syaofox/data/dev/index-tts

# 使用 uv 运行 main.py
source .venv/bin/activate
# python webui.py --verbose --fp16 --deepspeed
python webui.py --verbose --fp16