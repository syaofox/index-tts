# Findings: WebUI Examples 管理功能

## 当前架构分析

### 示例加载流程
1. 启动时读取 `examples/cases.jsonl` (JSONL 格式)
2. 每行一个 JSON 对象，解析后转换为数组格式
3. 音频路径拼接: `os.path.join("examples", example["prompt_audio"])`
4. 存入全局变量 `example_cases`
5. `gr.Dataset` 渲染示例列表

### 问题点
- `example_cases` 是全局列表，运行时修改需要刷新 Dataset
- 音频文件引用的是 `examples/` 目录下的相对路径
- 用户上传的音频存储在 Gradio 临时目录，会话结束后丢失
- `gr.Dataset` 不支持内置的删除/编辑 UI，需要额外实现

### 关键组件映射
| 示例数组索引 | 对应组件 | 数据类型 |
|---|---|---|
| 0 | prompt_audio | 文件路径 |
| 1 | emo_control_method | 文本 (选项标签) |
| 2 | input_text_single | 文本 |
| 3 | emo_upload | 文件路径 |
| 4 | emo_weight | 浮点数 |
| 5 | emo_text | 文本 |
| 6-13 | vec1-vec8 | 浮点数 |
