import gradio as gr

from utils.logger import debug, info


class EventHandlers:
    def __init__(self, tts_service, prompt_service, config_service=None):
        self.tts = tts_service
        self.prompt_service = prompt_service
        self.config_service = config_service

    @property
    def prompt_files(self):
        return self.prompt_service.get_prompt_files()

    def update_prompt_audio(self):
        return gr.update(interactive=True)

    def refresh_prompt_files(self):
        return gr.update(choices=self.prompt_service.refresh_prompt_datas())

    def dropdown_change(self, selected_prompt):
        prompt_path = self.prompt_service.get_prompt_file_path(selected_prompt)
        debug(f"prompt_path: {prompt_path}")
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

    def load_audio_settings(self):
        """加载音频设置"""
        if self.config_service:
            settings = self.config_service.get_audio_settings()
            silence_duration = settings.get("silence_duration", 0.3)
            scale_rate = settings.get("scale_rate", 1.0)
            info(f"已加载音频设置: 静音时长={silence_duration}, 缩放倍率={scale_rate}")
            return gr.update(value=silence_duration), gr.update(value=scale_rate)
        return gr.update(), gr.update()

    def save_audio_settings(self, silence_duration, scale_rate):
        """保存音频设置"""
        if self.config_service:
            self.config_service.save_audio_settings(silence_duration, scale_rate)
            info(f"已保存音频设置: 静音时长={silence_duration}, 缩放倍率={scale_rate}")
        return None
