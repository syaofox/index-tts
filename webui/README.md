# IndexTTS WebUI

基于Gradio的IndexTTS Web用户界面，采用模块化设计，高内聚低耦合架构。

## 简介

IndexTTS WebUI是一个独立运行的Web界面，用于与IndexTTS模型进行交互。它允许用户上传参考音频或选择预设提示，输入文本，然后生成相应的语音。

本模块完全独立于原有的UI系统，但共享相同的资源（如prompts目录和模型）。

## 特点

- **模块化设计**：各功能模块独立封装，便于维护和扩展
- **高内聚低耦合**：模块间通过接口交互，降低依赖
- **共享资源**：与主项目共享prompts和模型资源
- **易于使用**：简洁直观的用户界面
- **配置灵活**：支持通过配置文件自定义

## 系统需求

- Python 3.8+
- IndexTTS及其依赖项
- Gradio 3.x

## 快速开始

1. 安装依赖
```bash
pip install -r requirements.txt
```

2. 启动WebUI
```bash
# 使用批处理文件启动（Windows）
启动WebUI.bat

# 或者使用Python启动
python -m webui.app
```

3. 在浏览器中访问
```
http://127.0.0.1:7860
```

## 使用方法

1. 在"音频生成"选项卡中，上传参考音频或从下拉列表中选择预设提示
2. 在文本区域输入要转换为语音的文本
3. 选择推理模式（普通推理或批次推理）
4. 点击"生成语音"按钮
5. 等待处理完成后，播放或下载生成的音频

## 配置

WebUI的配置位于`webui/config/config.json`，支持以下设置：

```json
{
    "server_host": "127.0.0.1",
    "server_port": 7860,
    "prompts_dir": "prompts",
    "outputs_dir": "outputs",
    "model_dir": "checkpoints",
    "config_path": "checkpoints/config.yaml"
}
```

## 项目结构

```
webui/
├── app.py                 # 应用入口点
├── components/            # UI组件模块
│   ├── audio_player.py    # 音频播放器组件
│   ├── prompt_selector.py # 提示选择器组件  
│   └── text_input.py      # 文本输入组件
├── services/              # 服务层
│   ├── tts_service.py     # TTS服务接口
│   └── file_service.py    # 文件管理服务
├── utils/                 # 工具函数
│   ├── audio_utils.py     # 音频处理工具
│   └── config_utils.py    # 配置工具
└── config/                # 配置文件
    └── settings.py        # 应用设置
```

## 高级功能

- **批量处理**：支持批量文本处理（开发中）
- **参数调整**：支持调整模型参数（开发中）
- **历史记录**：保存和加载历史记录（计划中） 