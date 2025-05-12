import gradio as gr


class MainUI:
    def __init__(self):
       pass

    def build(self,callback_fn):
        with gr.Blocks() as demo:               
            with gr.Tab("音频生成"):
                with gr.Row():                
                    prompt_audio = gr.Audio(label="请上传参考音频",key="prompt_audio",
                                            sources=["upload","microphone"],type="filepath")
                    
                    with gr.Column():
                       
                        prompt_dropdown = gr.Dropdown(
                            choices=callback_fn._get_prompt_files(),
                            label="选择参考音频",
                            value="无"
                        )
                        refresh_button = gr.Button("刷新")
                        
                        input_text_single = gr.TextArea(label="请输入目标文本",key="input_text_single")
                        infer_mode = gr.Radio(choices=["普通推理", "批次推理"], label="选择推理模式（批次推理：更适合长句，性能翻倍）",value="普通推理")
                        gen_button = gr.Button("生成语音",key="gen_button",interactive=True)
                    output_audio = gr.Audio(label="生成结果", visible=True,key="output_audio")


            # 参考音频上传事件
            prompt_audio.upload(callback_fn.update_prompt_audio,
                                inputs=[],
                                outputs=[gen_button])
            
            # 刷新按钮点击事件
            refresh_button.click(
                fn=callback_fn.refresh_prompt_files,
                inputs=[],
                outputs=[prompt_dropdown]
            )
            
            # 下拉框选择事件
            prompt_dropdown.change(
                fn=callback_fn.dropdown_change,
                inputs=[prompt_dropdown],
                outputs=[prompt_audio]
            )

            # 生成语音按钮点击事件
            gen_button.click(callback_fn.gen_single,
                            inputs=[prompt_audio, input_text_single, infer_mode],
                            outputs=[output_audio])
        
        return demo