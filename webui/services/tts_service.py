import gradio as gr
import numpy as np
import soundfile as sf

from indextts.infer import IndexTTS
from webui.utils.text_processor import TextProcessor
from webui.services.prompt_service import PromptService


class TTS_Service:
    def __init__(self, progress=gr.Progress()):
        self.tts = IndexTTS(model_dir="checkpoints", cfg_path="checkpoints/config.yaml")
        self.progress = progress
        self.text_processor = TextProcessor()
        self.prompt_service = PromptService()

    def _set_progress(self, value, desc):
        if self.progress is not None:
            self.progress(value, desc=desc)

    def save_wav(self, wav_data, sampling_rate, file_path):
        """保存音频数据到文件"""
        # 检查输入数据类型和形状，确保数据格式正确
        if isinstance(wav_data, np.ndarray):
            # 如果wav_data已经是转置后的NumPy数组（从infer方法返回的格式），需要转置回来
            # IndexTTS返回的是(sampling_rate, wav_data.numpy().T)
            # 而sf.write期望的是未转置的数据
            if wav_data.ndim == 2 and wav_data.shape[0] < wav_data.shape[1]:
                # 如果是多通道转置格式，转置回来
                wav_data = wav_data.T

        # 确保数据类型正确（soundfile期望int16或float32）
        if not np.issubdtype(wav_data.dtype, np.integer):
            # 如果不是整数类型，对数据进行缩放和转换
            wav_data = np.clip(wav_data * 32767, -32767, 32767).astype(np.int16)

        # 保存到文件
        sf.write(file_path, wav_data, sampling_rate)

    def gen_wavdata(self, prompt_path, text, infer_mode, silence_duration=0.3):
        """根据选择的参考音频名称和文本生成音频数据"""

        if infer_mode == "普通推理":
            sampling_rate, wav_data = self.tts.infer(
                prompt_path,
                text,
                None,
                verbose=False,
                silence_duration=silence_duration,
            )  # 普通推理
        else:
            sampling_rate, wav_data = self.tts.infer_fast(
                prompt_path,
                text,
                None,
                verbose=False,
                silence_duration=silence_duration,
            )  # 批次推理
        return sampling_rate, wav_data

    def gen_wavdata_togr(
        self, speaker, prompt_path, text, infer_mode, silence_duration=0.3
    ):
        # self.tts.gr_progress = progress

        # 预处理文本
        text_segments = self.text_processor.preprocess_text(text, speaker)

        print(f"text_segments: {text_segments}")

        assert len(text_segments) > 0, "待推理文本段落数不能为空"

        # 生成音频数据
        wav_datas = []
        first_shape = None
        sampling_rate = None

        # 进度条信息
        progress_segments = [
            segment
            for segment in text_segments
            if segment["text"] != self.text_processor.BR_TAG
        ]
        total_step = len(progress_segments)
        current_step = 0

        for text_segment in text_segments:
            _speaker = text_segment["speaker"]
            _text = text_segment["text"]
            _prompt_path = self.prompt_service.get_prompt_file_path(_speaker)
            if _prompt_path is None:
                _prompt_path = prompt_path

            if _text == self.text_processor.BR_TAG and sampling_rate is not None:
                # 计算静音长度所需的采样点数
                silence_samples = int(sampling_rate * silence_duration)
                if first_shape is not None and len(first_shape) > 1:  # 处理多通道音频
                    wav_data = np.zeros((silence_samples, first_shape[1]))
                else:
                    wav_data = np.zeros(silence_samples)
                wav_datas.append(wav_data)
            else:
                self._set_progress(
                    current_step / total_step,
                    f"合成中: {current_step}/{total_step}，文本: {_text[:30] + '...' if len(_text) > 30 else _text}",
                )
                current_step += 1

                sampling_rate, wav_data = self.gen_wavdata(
                    _prompt_path,
                    _text,
                    infer_mode,
                    silence_duration,
                )
                if first_shape is None:
                    first_shape = wav_data.shape
                wav_datas.append(wav_data)

        # 合并音频数据
        wav_data = np.concatenate(wav_datas)
        speakers = list(
            set([text_segment["speaker"] for text_segment in text_segments])
        )

        speaker_str = speakers[0] if len(speakers) == 1 else f"{speakers[0]}等多角色"

        output_path = self.text_processor.generate_output_filename(speaker_str, text)
        print(f"output_path: {output_path}")

        # 确保音频数据保存前处于正确的状态
        self.save_wav(wav_data, sampling_rate, output_path)

        return gr.update(value=(sampling_rate, wav_data), visible=True)
