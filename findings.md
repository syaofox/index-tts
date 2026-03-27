# Findings: Docker 部署调研

## 项目依赖分析
- Python 3.10+ 环境
- 使用 uv 包管理器（pyproject.toml + uv.lock）
- PyTorch 2.8.* 需要 CUDA 支持
- 系统依赖：ffmpeg、librosa 音频处理
- 可选依赖：gradio（WebUI）、deepspeed（加速）

## Docker 最佳实践
- 使用官方 NVIDIA CUDA 基础镜像
- 多阶段构建分离构建和运行环境
- 利用 Docker 构建缓存优化依赖安装
- 非 root 用户运行提高安全性

## Compose 最新特性
- Compose V2 规范（2024+）
- 支持 GPU 资源分配
- 健康检查和服务依赖
- 环境变量和配置文件支持

## 模型检查点需求
- 必需文件：bpe.model, gpt.pth, config.yaml, s2mel.pth, wav2vec2bert_stats.pt
- 默认路径：./checkpoints/
- 大小估计：约 2-5GB

## WebUI 启动参数
- 主机：0.0.0.0（容器内需绑定所有接口）
- 端口：7860（可配置）
- 模型目录：./checkpoints
- 可选参数：--fp16, --deepspeed, --cuda_kernel