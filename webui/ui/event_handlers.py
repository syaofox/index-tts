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
        """下拉框选择事件，同时加载所选角色的音频设置"""
        prompt_path = self.prompt_service.get_prompt_file_path(selected_prompt)
        debug(f"prompt_path: {prompt_path}")

        # 加载角色的音频设置
        silence_duration, tts_version, max_text_tokens_per_sentence = 0.3, 1, 80
        if self.config_service and selected_prompt:
            settings = self.config_service.get_audio_settings(selected_prompt)
            silence_duration = settings.get("silence_duration", 0.3)    
            tts_version = settings.get("tts_version", 1)
            max_text_tokens_per_sentence = settings.get("max_text_tokens_per_sentence", 80)
            info(
                f"已加载角色 '{selected_prompt}' 的音频设置: 静音时长={silence_duration}, TTS版本={tts_version}，句子最大长度={max_text_tokens_per_sentence}"
            )

        return [
            gr.update(value=prompt_path),
            gr.update(value=silence_duration),          
            gr.update(value=tts_version),
            gr.update(value=max_text_tokens_per_sentence),
        ]

    def set_button_generating(self):
        """设置按钮为生成中状态（不可点击，文字改为生成中）"""
        info("语音生成中...")
        return gr.update(interactive=False, value="生成中...")

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
        tts_version=1,
        max_text_tokens_per_sentence=80,
        split_mode="sentence",
    ):
        """根据选择的参考音频名称和文本生成音频数据"""

        result = self.tts.gen_wavdata_togr(
            speaker, prompt_path, text, infer_mode, silence_duration, tts_version, max_text_tokens_per_sentence, split_mode
        )
        # 返回生成的音频和恢复的按钮状态
        return result, gr.update(interactive=True, value="生成语音")

    def load_audio_settings(self, speaker=None):
        """加载音频设置，如果提供了speaker则加载该角色的设置"""
        if self.config_service:
            settings = self.config_service.get_audio_settings(speaker)
            silence_duration = settings.get("silence_duration", 0.3)
            tts_version = settings.get("tts_version", 1)
            max_text_tokens_per_sentence = settings.get("max_text_tokens_per_sentence", 80)
            if speaker:
                info(
                    f"已加载角色 '{speaker}' 的音频设置: 静音时长={silence_duration}, TTS版本={tts_version}，句子最大长度={max_text_tokens_per_sentence}"
                )
            else:
                info(
                    f"已加载全局音频设置: 静音时长={silence_duration}, TTS版本={tts_version}，句子最大长度={max_text_tokens_per_sentence}"
                )
            return gr.update(value=silence_duration), gr.update(value=tts_version), gr.update(value=max_text_tokens_per_sentence)
        return gr.update(), gr.update(), gr.update()

    def save_audio_settings(self, speaker, silence_duration, tts_version=1, max_text_tokens_per_sentence=80):
        """保存音频设置到当前选中的角色"""
        if self.config_service:
            self.config_service.save_audio_settings(
                speaker, silence_duration, tts_version, max_text_tokens_per_sentence
            )
            if speaker and speaker != "无":
                info(
                    f"已保存角色 '{speaker}' 的音频设置: 静音时长={silence_duration}, TTS版本={tts_version}，句子最大长度={max_text_tokens_per_sentence}"
                )
            else:
                info(
                    f"已保存全局音频设置: 静音时长={silence_duration}, TTS版本={tts_version}，句子最大长度={max_text_tokens_per_sentence}"
                )
        return None
