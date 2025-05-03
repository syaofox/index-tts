# IndexTTS WebUI开发计划

## 1. 项目概述

使用Gradio框架复刻IndexTTS的UI界面，实现一个独立运行的Web用户界面，与原始UI共享prompts资源，但完全独立于现有的UI模块。

## 2. 设计原则

- **模块化设计**：将功能划分为独立模块，便于维护和扩展
- **高内聚低耦合**：每个模块专注于单一职责，模块间通过明确接口交互
- **共享资源**：与主项目共享prompts和模型资源
- **独立运行**：可完全脱离主UI独立运行

## 3. 系统架构

### 3.1 核心模块

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

### 3.2 模块职责

#### 3.2.1 UI组件层
- **音频播放器组件**：负责音频的上传、预览和播放
- **提示选择器组件**：提供对prompts目录中模板的浏览和选择
- **文本输入组件**：处理用户输入的目标文本

#### 3.2.2 服务层
- **TTS服务**：封装与IndexTTS核心功能的交互
- **文件服务**：处理文件的读写、保存和加载

#### 3.2.3 工具函数
- **音频工具**：音频格式转换、处理等功能
- **配置工具**：加载和保存配置

## 4. 数据流

1. 用户上传参考音频或从prompts中选择模板
2. 用户输入目标文本
3. 服务层调用IndexTTS进行推理
4. 生成的结果返回给UI展示

## 5. 接口设计

### 5.1 与IndexTTS的接口

```python
# TTS服务示例接口
class TTSService:
    def __init__(self, model_dir, config_path):
        self.tts = IndexTTS(model_dir=model_dir, cfg_path=config_path)
    
    def generate(self, prompt, text, output_path=None, mode="normal"):
        if mode == "normal":
            return self.tts.infer(prompt, text, output_path)
        else:
            return self.tts.infer_fast(prompt, text, output_path)
```

## 6. 实现计划

1. **阶段一**：搭建基本架构和UI组件
2. **阶段二**：实现服务层与IndexTTS的集成
3. **阶段三**：优化用户体验和性能
4. **阶段四**：增加高级功能（批量处理、参数调整）

## 7. 注意事项

- WebUI独立于原UI运行，但共享项目资源
- 确保webui.py模块与此模块完全无关联
- 代码结构应遵循高内聚低耦合原则，避免模块间紧耦合
- 所有配置应可外部化，便于用户调整





