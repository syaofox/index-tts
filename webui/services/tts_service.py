import gradio as gr
import numpy as np
import soundfile as sf
import torch
import torchaudio

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
        # 将numpy数组转换为torch.Tensor
        if isinstance(wav_data, np.ndarray):
            # 确保数据是浮点类型以便正确转换
            if np.issubdtype(wav_data.dtype, np.integer):
                # 如果是整数类型，转换为浮点类型以便后续处理
                wav_data = wav_data.astype(np.float32) / 32768.0
            
            # 处理转置问题
            # torchaudio期望的张量形状为[channels, time]
            if wav_data.ndim == 2 and wav_data.shape[0] > wav_data.shape[1]:
                # 如果第一维大于第二维，假设是[time, channels]格式，需要转置
                wav_data = wav_data.T
            
            # 转换为torch.Tensor
            wav_tensor = torch.from_numpy(wav_data)
        elif isinstance(wav_data, torch.Tensor):
            wav_tensor = wav_data
        else:
            # 尝试转换其他类型
            wav_tensor = torch.tensor(wav_data)
        
        # 确保张量形状正确：[channels, time]
        if wav_tensor.ndim == 1:
            # 单通道音频，添加通道维度
            wav_tensor = wav_tensor.unsqueeze(0)
        
        # 确保数据类型是int16
        wav_tensor = wav_tensor.type(torch.float32)
        
        # 规范化数据范围到[-1, 1]
        with torch.no_grad():
            max_abs = torch.max(torch.abs(wav_tensor))
            if max_abs > 1.0:
                wav_tensor = wav_tensor / max_abs
        
        # 转换为int16类型用于保存
        wav_tensor = (wav_tensor * 32767).type(torch.int16)
        
        # 使用torchaudio保存
        torchaudio.save(file_path, wav_tensor, sampling_rate)

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
