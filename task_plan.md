# Task Plan: WebUI Examples 管理功能增强

## 目标
为 IndexTTS WebUI 增加 Examples 管理功能，支持保存、删除、修改示例项目。

## 当前状态分析

### 现有架构
- 示例数据来源: `examples/cases.jsonl` (JSONL 格式)
- 音频文件位置: `examples/` 目录
- UI 组件: `gr.Dataset` 显示示例列表
- 点击示例通过 `on_example_click` 加载到表单

### 示例数据结构
```json
{
  "prompt_audio": "voice_01.wav",     // 音色参考音频 (相对 examples/ 目录)
  "text": "合成文本",
  "emo_mode": 0,                       // 情感控制模式 (0-3)
  "emo_audio": "emo_sad.wav",          // 可选: 情感参考音频
  "emo_weight": 0.65,                  // 可选: 情感权重
  "emo_text": "情感描述",              // 可选: 情感文本
  "emo_vec_1": 0.0 ... "emo_vec_8": 0.0  // 可选: 情感向量
}
```

### 痛点
1. 无法从 UI 保存当前设置为新示例
2. 无法删除已有示例
3. 无法编辑示例内容
4. 用户上传的音频存储在临时路径，无法持久化

---

## 实现方案

### Phase 1: 数据管理层
创建 `examples/manager.py` 模块处理 CRUD 操作:

1. `load_examples()` - 从 JSONL 读取示例
2. `save_example(example_data, audio_files)` - 保存新示例 (复制音频到 examples/)
3. `delete_example(index)` - 删除指定示例
4. `update_example(index, example_data)` - 更新示例
5. `get_example_path()` - 获取 JSONL 文件路径

### Phase 2: UI 增强

#### 2.1 保存功能
- 在功能设置区添加 "保存为示例" 按钮
- 收集当前表单所有状态
- 处理音频文件: 如果是用户上传，复制到 `examples/user/` 目录
- 写入 JSONL 并刷新 Dataset

#### 2.2 删除功能
- 为每个示例添加删除按钮 (使用 `gr.Dataset` 的交互方式)
- 或: 添加下拉选择 + 删除按钮的管理面板
- 确认删除 (防止误操作)

#### 2.3 编辑功能
- 点击示例后，"保存" 按钮变为 "更新"
- 修改后点击更新，覆盖原示例

### Phase 3: UI 布局调整
在 Examples 区下方添加管理工具栏:
```
[保存当前设置为示例] [删除示例 ▼下拉选择] [编辑示例 ▼下拉选择 → 加载到表单 → 更新按钮]
```

---

## 文件变更

| 文件 | 操作 | 说明 |
|------|------|------|
| `examples/manager.py` | 新增 | CRUD 数据管理 |
| `webui.py` | 修改 | 添加 UI 组件和事件处理 |
| `examples/cases.jsonl` | 读写 | 示例数据存储 |
| `examples/user/` | 新增目录 | 用户上传音频存储 |

---

## 实现完成

### 已完成的功能
1. ✅ `examples/manager.py` - CRUD 管理模块
   - `load_examples()` - 从 JSONL 加载
   - `add_example()` - 添加新示例
   - `delete_example()` - 删除示例
   - `update_example()` - 更新示例
   - `copy_audio_to_user_dir()` - 复制音频到持久目录
   - `get_example_display_list()` - 获取下拉选择列表

2. ✅ `webui.py` - UI 功能增强
   - 保存当前设置为示例按钮
   - 下拉选择示例 + 删除按钮
   - 下拉选择示例 + 加载到编辑按钮
   - 更新示例按钮（编辑模式显示）
   - `get_example_cases()` 改为动态加载

### 文件变更
| 文件 | 操作 | 说明 |
|------|------|------|
| `examples/manager.py` | 新增 | CRUD 数据管理 |
| `webui.py` | 修改 | 添加 UI 组件和事件处理 |

## Errors Encountered
(无)
