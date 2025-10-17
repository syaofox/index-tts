# ==========================================
# IndexTTS2 多阶段 Docker 构建配置
# ==========================================
#
# 本 Dockerfile 已配置国内加速镜像：
#   - APT 源：阿里云镜像（mirrors.aliyun.com）
#   - Python 包：阿里云 PyPI 镜像（mirrors.aliyun.com/pypi/simple/）
#   - 备用源：清华大学镜像（pypi.tuna.tsinghua.edu.cn/simple/）
#
# 构建命令：
#   docker build -t indextts2:latest .
#
# 运行命令（启动 WebUI）：
#   docker run --gpus all -p 7860:7860 indextts2:latest
#
# 运行命令（交互式 shell）：
#   docker run --gpus all -it indextts2:latest bash
#
# 运行命令（自定义脚本）：
#   docker run --gpus all indextts2:latest python your_script.py
#
# ==========================================

# ==========================================
# 第一阶段：构建环境（Builder Stage）
# ==========================================
FROM nvidia/cuda:13.0.1-cudnn-devel-ubuntu24.04 AS builder

# 设置环境变量
ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONUNBUFFERED=1

# 配置国内 APT 镜像源（阿里云）
RUN sed -i 's@archive.ubuntu.com@mirrors.aliyun.com@g' /etc/apt/sources.list.d/ubuntu.sources && \
    sed -i 's@security.ubuntu.com@mirrors.aliyun.com@g' /etc/apt/sources.list.d/ubuntu.sources

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    git-lfs \
    curl \
    wget \
    build-essential \
    ffmpeg \
    libsndfile1 \
    libsndfile1-dev \
    libavcodec-extra \
    libavformat-dev \
    libavutil-dev \
    libswresample-dev \
    libmpg123-0 \
    libmpg123-dev \
    libmad0 \
    libmad0-dev \
    libflac12 \
    libflac-dev \
    libvorbis0a \
    libvorbis-dev \
    libopus0 \
    libopus-dev \
    libogg0 \
    libogg-dev \
    software-properties-common \
    && add-apt-repository ppa:deadsnakes/ppa -y \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-dev \
    python3.11-venv \
    llvm-14 \
    llvm-14-dev \
    && git lfs install \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 安装 uv 包管理器
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# 配置 uv 和 pip 使用国内镜像源（阿里云）
ENV UV_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/ \
    UV_EXTRA_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple/ \
    PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/ \
    PIP_TRUSTED_HOST=mirrors.aliyun.com

# 设置 LLVM 环境变量，用于构建 llvmlite
ENV LLVM_CONFIG=/usr/bin/llvm-config-14

# 设置工作目录
WORKDIR /build

# 复制依赖配置文件（利用 Docker 缓存层）
COPY pyproject.toml uv.lock README.md ./

# 复制项目源代码（某些依赖包在安装时可能需要源代码）
COPY indextts ./indextts
COPY webui.py run_webui.sh ./
COPY tools ./tools
COPY examples ./examples

# 使用 uv 创建虚拟环境并安装依赖
RUN uv sync --python python3.11 --all-extras

# ==========================================
# 第二阶段：运行环境（Runtime Stage）
# ==========================================
FROM nvidia/cuda:13.0.1-cudnn-runtime-ubuntu24.04

# 设置环境变量
ENV DEBIAN_FRONTEND=noninteractive \
    LANG=zh_CN.UTF-8 \
    LC_ALL=zh_CN.UTF-8 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app:$PYTHONPATH"

# 配置国内 APT 镜像源（阿里云）
RUN sed -i 's@archive.ubuntu.com@mirrors.aliyun.com@g' /etc/apt/sources.list.d/ubuntu.sources && \
    sed -i 's@security.ubuntu.com@mirrors.aliyun.com@g' /etc/apt/sources.list.d/ubuntu.sources

# 安装运行时依赖（最小化）并配置中文环境
RUN apt-get update && apt-get install -y --no-install-recommends \
    git-lfs \
    ffmpeg \
    libsndfile1 \
    libsndfile1-dev \
    libavcodec-extra \
    libavformat-dev \
    libavutil-dev \
    libswresample-dev \
    libmpg123-0 \
    libmad0 \
    libflac12 \
    libvorbis0a \
    libopus0 \
    libogg0 \
    software-properties-common \
    ca-certificates \
    curl \
    locales \
    && add-apt-repository ppa:deadsnakes/ppa -y \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-venv \
    && git lfs install \
    && locale-gen zh_CN.UTF-8 \
    && update-locale LANG=zh_CN.UTF-8 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 从构建阶段复制必要的文件
# 1. 复制 Python 虚拟环境
COPY --from=builder /build/.venv /app/.venv

# 2. 复制项目文件
COPY --from=builder /build/pyproject.toml /build/uv.lock ./
COPY --from=builder /build/indextts ./indextts
COPY --from=builder /build/webui.py /build/run_webui.sh ./
COPY --from=builder /build/tools ./tools
COPY --from=builder /build/examples ./examples

# 暴露 WebUI 端口
EXPOSE 7860

# 健康检查（可选）
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:7860/ || exit 1

# 默认启动 WebUI
# 可以通过 docker run 时覆盖命令来运行其他脚本
CMD ["python", "webui.py", "--host", "0.0.0.0", "--port", "7860", "--verbose", "--fp16"]

