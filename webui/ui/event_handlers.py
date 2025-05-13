import gradio as gr


class EventHandlers:
    def __init__(self, tts_service, prompt_service):
        self.tts = tts_service
        self.prompt_service = prompt_service

    @property
    def prompt_files(self):
        return self.prompt_service.get_prompt_files()

    def update_prompt_audio(self):
        return gr.update(interactive=True)

    def refresh_prompt_files(self):
        return gr.update(choices=self.prompt_service.refresh_prompt_datas())

    def dropdown_change(self, selected_prompt):
        prompt_path = self.prompt_service.get_prompt_file_path(selected_prompt)
        print(f"prompt_path: {prompt_path}")
        return gr.update(value=prompt_path)

    def clear_audio(self):
        """清空音频输出"""
        return gr.update(value=None, visible=True)

    def gen_wavdata_togr(
        self,
        speaker,
        prompt_path,
        text,
        infer_mode,
        silence_duration=0.3,
        scale_rate=1.0,
    ):
        """根据选择的参考音频名称和文本生成音频数据"""

        result = self.tts.gen_wavdata_togr(
            speaker, prompt_path, text, infer_mode, silence_duration, scale_rate
        )
        return result
