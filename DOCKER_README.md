# IndexTTS2 Docker 部署指南

## 前置要求

1. 安装 Docker 和 Docker Compose
2. 安装 NVIDIA Container Toolkit（用于 GPU 支持）
3. 准备模型检查点文件

## 快速开始

### 1. 准备模型检查点

将模型文件放置在 `checkpoints/` 目录下，确保包含以下文件：
- `bpe.model`
- `gpt.pth`
- `config.yaml`
- `s2mel.pth`
- `wav2vec2bert_stats.pt`

### 2. 构建并启动容器

```bash
# 构建镜像并启动服务
docker compose up --build

# 或者后台运行
docker compose up --build -d
```

### 3. 访问 WebUI

打开浏览器访问：http://localhost:7860

## Dockerfile 版本说明

| 文件 | 基础镜像 | DeepSpeed | 预估大小 | 用途 |
|------|----------|-----------|----------|------|
| `Dockerfile` | `cuda:12.8.0-runtime` | ❌ | ~7GB | 日常使用 |
| `Dockerfile.devel` | `cuda:12.8.0-devel` | ✅ | ~10GB | 需要 DeepSpeed 加速 |

使用完整版构建：
```bash
docker compose build --build-arg DOCKERFILE=Dockerfile.devel indextts-webui
```

## 配置选项

可以通过环境变量配置容器行为：

```bash
# 修改 docker-compose.yml 中的 environment 部分
# 或者使用 .env 文件

# 示例：启用 FP16 模式
INDXTTS_FP16=true

# 示例：修改端口
INDXTTS_PORT=8080
```

### 可用环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `INDXTTS_HOST` | `0.0.0.0` | 监听地址 |
| `INDXTTS_PORT` | `7860` | 监听端口 |
| `INDXTTS_MODEL_DIR` | `./checkpoints` | 模型目录 |
| `INDXTTS_FP16` | `true` | 启用 FP16 推理 |
| `INDXTTS_DEEPSPEED` | `false` | 启用 DeepSpeed（需 `Dockerfile.devel`） |
| `INDXTTS_CUDA_KERNEL` | `false` | 启用 CUDA 内核 |
| `INDXTTS_GUI_SEG_TOKENS` | `120` | 分句最大 Token 数 |
| `INDXTTS_VERBOSE` | `false` | 启用详细日志 |

## 数据持久化

- **模型检查点**：只读挂载到 `./checkpoints`
- **生成音频**：持久化到 `./outputs`
- **HuggingFace 缓存**：持久化到 `./hf_cache`

## 常用命令

```bash
# 查看日志
docker compose logs -f

# 停止服务
docker compose down

# 重新构建（不使用缓存）
docker compose build --no-cache

# 进入容器调试
docker compose exec indextts-webui bash
```

## 故障排除

### 1. GPU 不可用
确保已安装 NVIDIA Container Toolkit：
```bash
# 验证 GPU 支持
docker run --rm --gpus all nvidia/cuda:12.8.0-runtime-ubuntu22.04 nvidia-smi
```

### 2. 模型文件缺失
检查 `checkpoints/` 目录是否包含所有必需文件。

### 3. 端口冲突
修改 `docker-compose.yml` 中的端口映射：
```yaml
ports:
  - "8080:7860"  # 使用 8080 端口访问
```

### 4. DeepSpeed 报错
默认镜像不含 DeepSpeed，如需启用：
1. 使用 `Dockerfile.devel` 构建
2. 设置 `INDXTTS_DEEPSPEED=true`

## 生产部署建议

1. 使用 `.env` 文件管理环境变量
2. 配置反向代理（Nginx/Caddy）
3. 启用 HTTPS
4. 设置资源限制：
```yaml
deploy:
  resources:
    limits:
      memory: 8G
    reservations:
      memory: 4G
```
