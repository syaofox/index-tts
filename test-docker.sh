#!/bin/bash
set -e

echo "=== IndexTTS2 Docker 部署测试 ==="

# 检查 Docker 是否安装
if ! command -v docker &> /dev/null; then
    echo "错误: Docker 未安装"
    exit 1
fi

# 检查 Docker Compose 是否安装
if ! command -v docker compose &> /dev/null; then
    echo "错误: Docker Compose 未安装"
    exit 1
fi

# 检查 NVIDIA Container Toolkit
if ! docker run --rm --gpus all nvidia/cuda:12.8.0-runtime-ubuntu22.04 nvidia-smi &> /dev/null; then
    echo "警告: GPU 支持不可用，将使用 CPU 模式"
fi

# 检查模型目录
if [ ! -d "./checkpoints" ]; then
    echo "错误: 模型目录 ./checkpoints 不存在"
    echo "请先下载模型文件到 checkpoints/ 目录"
    exit 1
fi

# 检查必需文件
REQUIRED_FILES=("bpe.model" "gpt.pth" "config.yaml" "s2mel.pth" "wav2vec2bert_stats.pt")
for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "./checkpoints/$file" ]; then
        echo "错误: 缺少模型文件 ./checkpoints/$file"
        exit 1
    fi
done

echo "=== 构建 Docker 镜像 ==="
docker compose build

echo "=== 启动服务 ==="
docker compose up -d

echo "=== 等待服务启动 ==="
sleep 10

echo "=== 检查服务状态 ==="
docker compose ps

echo "=== 检查日志 ==="
docker compose logs --tail=20

echo ""
echo "=== 测试完成 ==="
echo "WebUI 应该可以通过 http://localhost:7860 访问"
echo ""
echo "常用命令:"
echo "  查看日志: docker compose logs -f"
echo "  停止服务: docker compose down"
echo "  重新构建: docker compose build --no-cache"