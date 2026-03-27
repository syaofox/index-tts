# Task Plan: Docker 部署方案

## Goal
为 IndexTTS2 项目创建完整的 Docker 部署方案，使用最新版本的 Docker Compose，容器启动后自动启动 WebUI。

## Current Phase
All phases complete

## Phases

### Phase 1: 需求分析与技术调研
- [x] 分析项目依赖和运行环境要求
- [x] 研究 Docker 最佳实践和最新 Compose 规范
- [x] 确定基础镜像和 CUDA 支持需求
- [x] 文档化发现结果
- **Status:** complete

### Phase 2: Dockerfile 设计与实现
- [x] 创建多阶段构建 Dockerfile
- [x] 配置 Python 环境和 uv 包管理器
- [x] 安装系统依赖和 CUDA 工具包
- [x] 设置模型检查点目录结构
- **Status:** complete

### Phase 3: Docker Compose 配置
- [x] 创建 docker-compose.yml（最新版本）
- [x] 配置服务依赖和网络
- [x] 设置环境变量和卷挂载
- [x] 配置 WebUI 启动命令
- **Status:** complete

### Phase 4: 启动脚本与配置优化
- [x] 创建容器启动脚本
- [x] 配置健康检查和重启策略
- [x] 优化镜像大小和构建缓存
- [x] 添加 .dockerignore 文件
- **Status:** complete

### Phase 5: 测试与验证
- [x] 构建 Docker 镜像
- [x] 测试容器启动和 WebUI 访问
- [x] 验证模型加载和推理功能
- [x] 文档化使用说明
- **Status:** complete

## Key Questions
1. 是否需要 GPU 支持（CUDA）？
2. 模型检查点如何提供（挂载卷或内置）？
3. 是否需要支持 DeepSpeed 加速？
4. 容器资源限制和端口配置？

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| 使用 uv 包管理器 | 项目已有 uv.lock，依赖管理一致 |
| 多阶段构建 | 减小最终镜像大小，分离构建和运行环境 |
| NVIDIA CUDA 基础镜像 | 支持 GPU 加速推理 |
| 最新 Compose 规范 | 用户明确要求最新版本 |
| 使用启动脚本 | 支持环境变量配置，更灵活 |
| 非 root 用户运行 | 提高容器安全性 |
| 只读挂载模型目录 | 防止模型文件被意外修改 |
| 持久化输出目录 | 保存生成的音频文件 |

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| 无 | - | 所有阶段顺利完成 |

## Notes
- 模型检查点需要从 HuggingFace 下载或挂载本地目录
- WebUI 默认端口为 7860
- 需要 NVIDIA Container Toolkit 支持 GPU
- 使用非 root 用户运行容器提高安全性
- 模型目录以只读方式挂载防止意外修改
- 输出目录持久化保存生成的音频文件