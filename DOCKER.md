# IndexTTS2 Docker 使用指南

本文档介绍如何使用 Docker 容器化方式运行 IndexTTS2。

## 📋 前置要求

1. **Docker**：安装 Docker Engine（推荐 20.10 或更高版本）
2. **NVIDIA Docker**：安装 NVIDIA Container Toolkit 以支持 GPU
3. **Docker Compose**（可选）：用于更便捷的容器管理
4. **模型文件**：需要手动下载 IndexTTS-2 模型到本地 `checkpoints` 目录

### 安装 NVIDIA Container Toolkit

**方法一：官方推荐（Ubuntu/Debian）**

```bash
# 配置仓库
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

# 安装
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit

# 配置 Docker 运行时
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

**方法二：使用安装脚本（更简单）**

```bash
# 下载并运行安装脚本
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

distribution=$(. /etc/os-release;echo $ID$VERSION_ID) \
  && curl -fsSL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
     sed "s#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g" | \
     sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

**方法三：如果您使用的是 Ubuntu 24.04**

如果上述方法遇到 "Unsupported distribution" 错误，可以使用 Ubuntu 22.04 的源：

```bash
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

echo "deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://nvidia.github.io/libnvidia-container/stable/deb/amd64 /" | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

### 验证 GPU 支持

```bash
docker run --rm --gpus all nvidia/cuda:13.0.1-base-ubuntu24.04 nvidia-smi
```

### 下载模型文件

在构建和运行 Docker 容器之前，您需要先下载 IndexTTS-2 模型文件到本地。

**方法一：使用 ModelScope（推荐国内用户）**

```bash
# 安装 modelscope
pip install modelscope

# 下载模型到本地 checkpoints 目录
modelscope download --model IndexTeam/IndexTTS-2 --local_dir ./checkpoints
```

**方法二：使用 HuggingFace CLI**

```bash
# 安装 huggingface-hub
pip install "huggingface-hub[cli]"

# 下载模型到本地 checkpoints 目录
huggingface-cli download IndexTeam/IndexTTS-2 --local-dir ./checkpoints
```

**方法三：手动下载**

从以下任一地址下载模型文件：
- ModelScope: https://www.modelscope.cn/models/IndexTeam/IndexTTS-2
- HuggingFace: https://huggingface.co/IndexTeam/IndexTTS-2

下载完成后，确保 `checkpoints` 目录包含以下文件：
- `config.yaml`
- `pinyin.vocab`
- 其他模型权重文件

## 🚀 快速开始

### 方法一：使用 Docker Compose（推荐）

这是最简单的方式，一条命令即可完成构建和启动：

```bash
# 构建并启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

访问 WebUI：打开浏览器访问 `http://localhost:7860`

### 方法二：使用 Docker 命令

#### 1. 构建镜像

```bash
# 构建镜像
docker build -t indextts2:latest .
```

构建过程说明：
- 第一阶段（Builder）：编译依赖（约需 10-20 分钟，取决于网络速度）
- 第二阶段（Runtime）：创建精简的运行镜像
- 注意：模型文件不包含在镜像中，需要通过卷挂载方式提供

#### 2. 运行容器

**启动 WebUI（必须挂载 checkpoints 目录）：**

```bash
docker run --gpus all -p 7860:7860 \
  -v $(pwd)/checkpoints:/app/checkpoints \
  -v $(pwd)/outputs:/app/outputs \
  --name indextts2 \
  indextts2:latest
```

**后台运行：**

```bash
docker run -d --gpus all -p 7860:7860 \
  -v $(pwd)/checkpoints:/app/checkpoints \
  -v $(pwd)/outputs:/app/outputs \
  --name indextts2 \
  indextts2:latest
```

**交互式运行（调试）：**

```bash
docker run --gpus all -it --rm \
  -v $(pwd)/checkpoints:/app/checkpoints \
  indextts2:latest bash
```

**运行自定义脚本：**

```bash
docker run --gpus all --rm \
  -v $(pwd)/checkpoints:/app/checkpoints \
  -v $(pwd)/my_script.py:/app/my_script.py \
  indextts2:latest \
  python my_script.py
```

## 🎛️ 高级配置

### 自定义 WebUI 参数

```bash
docker run --gpus all -p 7860:7860 \
  -v $(pwd)/checkpoints:/app/checkpoints \
  indextts2:latest \
  python webui.py --server-name 0.0.0.0 --server-port 7860 --use-fp16
```

### 使用 DeepSpeed 加速

```bash
docker run --gpus all -p 7860:7860 \
  -v $(pwd)/checkpoints:/app/checkpoints \
  indextts2:latest \
  python webui.py --use-deepspeed
```

### 环境变量配置

```bash
docker run --gpus all -p 7860:7860 \
  -v $(pwd)/checkpoints:/app/checkpoints \
  -e CUDA_VISIBLE_DEVICES=0,1 \
  indextts2:latest
```

### 限制 GPU 使用

```bash
# 使用特定 GPU
docker run --gpus '"device=0"' -p 7860:7860 \
  -v $(pwd)/checkpoints:/app/checkpoints \
  indextts2:latest

# 使用多个 GPU
docker run --gpus '"device=0,1"' -p 7860:7860 \
  -v $(pwd)/checkpoints:/app/checkpoints \
  indextts2:latest
```

## 📁 目录结构

容器内的目录结构：

```
/app/
├── indextts/          # 源代码
├── checkpoints/       # 预训练模型（需要从宿主机挂载）
├── examples/          # 示例音频
├── tools/             # 工具脚本
├── webui.py           # WebUI 入口
├── .venv/             # Python 虚拟环境
└── outputs/           # 输出目录（建议挂载）
```

**重要说明**：
- `checkpoints/` 目录必须从宿主机挂载，镜像中不包含模型文件
- `outputs/` 目录建议挂载，以便持久化生成的音频文件

## 🔧 常见问题

### 1. 模型文件未找到或加载失败

确保在启动容器前已经下载了模型文件到本地 `checkpoints` 目录，并正确挂载：

```bash
# 检查本地 checkpoints 目录是否存在模型文件
ls -l checkpoints/

# 确保启动时挂载了 checkpoints 目录
docker run --gpus all -p 7860:7860 \
  -v $(pwd)/checkpoints:/app/checkpoints \
  indextts2:latest
```

如果需要重新下载模型：

```bash
# 使用 ModelScope
modelscope download --model IndexTeam/IndexTTS-2 --local_dir ./checkpoints

# 或使用 HuggingFace
huggingface-cli download IndexTeam/IndexTTS-2 --local-dir ./checkpoints
```

### 2. GPU 不可用

检查以下项：
- 宿主机是否安装了 NVIDIA 驱动
- 是否安装了 nvidia-container-toolkit
- 运行命令是否包含 `--gpus all` 参数

```bash
# 验证 GPU
docker run --rm --gpus all \
  -v $(pwd)/checkpoints:/app/checkpoints \
  indextts2:latest python tools/gpu_check.py
```

### 3. 端口被占用

更改映射端口：

```bash
docker run --gpus all -p 8080:7860 \
  -v $(pwd)/checkpoints:/app/checkpoints \
  indextts2:latest
```

然后访问 `http://localhost:8080`

### 4. 容器内存不足

增加 Docker 内存限制：

```bash
docker run --gpus all -p 7860:7860 \
  -v $(pwd)/checkpoints:/app/checkpoints \
  --memory=16g \
  --shm-size=8g \
  indextts2:latest
```

### 5. 镜像体积优化

当前配置已经通过以下方式优化了镜像体积：
- 使用多阶段构建分离构建环境和运行环境
- 模型文件通过卷挂载而非打包到镜像中
- 清理了 apt 缓存和临时文件

如需进一步优化，可以使用 `.dockerignore` 排除更多不必要的文件。

## 📊 性能优化

### 使用 FP16（半精度）

减少显存占用，提升推理速度：

```bash
docker run --gpus all -p 7860:7860 \
  -v $(pwd)/checkpoints:/app/checkpoints \
  indextts2:latest \
  python webui.py --use-fp16
```

### 编译 CUDA 内核

首次运行会编译，后续运行更快：

```bash
docker run --gpus all -p 7860:7860 \
  -v $(pwd)/checkpoints:/app/checkpoints \
  indextts2:latest \
  python webui.py --use-cuda-kernel
```

## 🛠️ 开发模式

挂载本地代码进行开发：

```bash
docker run --gpus all -it --rm \
  -p 7860:7860 \
  -v $(pwd)/checkpoints:/app/checkpoints \
  -v $(pwd)/indextts:/app/indextts \
  -v $(pwd)/webui.py:/app/webui.py \
  indextts2:latest \
  bash
```

在容器内：

```bash
# 修改代码后直接运行
python webui.py
```

## 📝 日志管理

查看容器日志：

```bash
# Docker Compose
docker-compose logs -f

# Docker
docker logs -f indextts2
```

## 🔄 更新镜像

```bash
# 拉取最新代码
git pull

# 重新构建
docker-compose build --no-cache

# 或使用 Docker 命令
docker build --no-cache -t indextts2:latest .
```

## 🧹 清理

```bash
# 停止并删除容器
docker-compose down
# 或
docker stop indextts2 && docker rm indextts2

# 删除镜像
docker rmi indextts2:latest

# 清理未使用的镜像和容器
docker system prune -a
```

## 📞 获取帮助

- GitHub Issues：https://github.com/index-tts/index-tts/issues
- QQ 群：663272642(No.4) 1013410623(No.5)
- Discord：https://discord.gg/uT32E7KDmy
- Email：indexspeech@bilibili.com

## 📄 许可证

本项目遵循 Bilibili IndexTTS 许可证。详见 `LICENSE` 文件。

