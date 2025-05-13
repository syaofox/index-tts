import gradio as gr

js_func = """
function set_dark_theme() {
    const url = new URL(window.location);
    if (url.searchParams.get('__theme') !== 'dark') {
        url.searchParams.set('__theme', 'dark');
        window.location.href = url.href;
    }
}
"""
PLACEHOLDER_TEXT = """请输入目标文本
支持多角色，选中的角色为默认角色，格式：

<角色名1>
文本内容段落1

<角色名2>
文本内容段落2
"""


class MainUI:
    CONFIG_FILE = "webui/config.json"

    def __init__(self):
        pass

    def build(self, event_handlers):
        with gr.Blocks(js=js_func) as demo:
            with gr.Tab("音频生成"):
                with gr.Row():
                    prompt_audio = gr.Audio(
                        label="请上传参考音频",
                        key="prompt_audio",
                        sources=["upload", "microphone"],
                        type="filepath",
                    )

                    with gr.Column():
                        prompt_dropdown = gr.Dropdown(
                            choices=event_handlers.prompt_files,
                            label="选择参考音频",
                            value="无",
                        )
                        refresh_button = gr.Button("刷新")

                        with gr.Row():
                            infer_mode = gr.Radio(
                                choices=["普通推理", "批次推理"],
                                label="选择推理模式（批次推理：更适合长句，性能翻倍）",
                                value="普通推理",
                            )
                            silence_duration = gr.Slider(
                                minimum=0,
                                maximum=100.0,
                                value=0.3,
                                step=0.1,
                                label="句子间静音时长(秒)",
                                info="设置句子之间的停顿时间",
                            )

                        scale_rate = gr.Slider(
                            minimum=0.1,
                            maximum=10.0,
                            value=1.0,
                            step=0.1,
                            label="静音缩放倍率",
                            info="调整音频中静音部分的长度，大于1表示延长，小于1表示缩短",
                        )

                input_text_single = gr.TextArea(
                    label="请输入目标文本",
                    key="input_text_single",
                    placeholder=PLACEHOLDER_TEXT,
                )

                gen_button = gr.Button(
                    "生成语音", key="gen_button", interactive=True, variant="primary"
                )
                output_audio = gr.Audio(
                    label="生成结果",
                    visible=True,
                    key="output_audio",
                    streaming=True,
                )

            # 参考音频上传事件
            prompt_audio.upload(
                event_handlers.update_prompt_audio, inputs=[], outputs=[gen_button]
            )

            # 刷新按钮点击事件
            refresh_button.click(
                fn=event_handlers.refresh_prompt_files,
                inputs=[],
                outputs=[prompt_dropdown],
            )

            # 下拉框选择事件（角色切换）- 同时加载该角色的设置
            prompt_dropdown.change(
                fn=event_handlers.dropdown_change,
                inputs=[prompt_dropdown],
                outputs=[prompt_audio, silence_duration, scale_rate],
            )

            # 生成语音按钮点击事件
            gen_button.click(
                fn=event_handlers.clear_audio,
                inputs=[],
                outputs=[output_audio],
            ).then(
                fn=event_handlers.save_audio_settings,
                inputs=[prompt_dropdown, silence_duration, scale_rate],
                outputs=[],
            ).then(
                fn=event_handlers.gen_wavdata_togr,
                inputs=[
                    prompt_dropdown,
                    prompt_audio,
                    input_text_single,
                    infer_mode,
                    silence_duration,
                    scale_rate,
                ],
                outputs=[output_audio],
            )

        return demo
