import gradio as gr
import numpy as np
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

    # 按照指定倍率缩放音频中的停顿
    def scale_silence(
        self,
        wav_data,
        sampling_rate,
        scale_rate=1.0,
        silence_threshold=0.1,
        min_silence_duration=0.05,
    ):
        """
        找出音频数据中的静音部分，按照指定倍率缩放这些静音部分

        参数:
            wav_data: 音频数据，numpy数组
            sampling_rate: 采样率
            scale_rate: 静音缩放倍率，>1表示延长静音，<1表示缩短静音
            silence_threshold: 判断为静音的振幅阈值
            min_silence_duration: 最小静音长度(秒)，小于此长度的静音不会被处理

        返回:
            sampling_rate: 原采样率
            new_wav_data: 处理后的音频数据
        """
        # 只处理形如(n, 1)的单通道音频，其他情况直接返回原始数据
        original_shape = wav_data.shape

        if len(original_shape) != 2 or original_shape[1] != 1:
            return sampling_rate, wav_data

        # 将(n, 1)数据扁平化为一维数组，便于处理
        wav_mono = wav_data.flatten()

        # 计算音频振幅包络
        amplitude = np.abs(wav_mono)

        # 确定静音片段
        min_samples = int(min_silence_duration * sampling_rate)
        is_silence = amplitude < silence_threshold

        # 找出所有静音段的起始和结束位置
        silence_regions = []
        in_silence = False
        silence_start = 0

        for i in range(len(is_silence)):
            if not in_silence and is_silence[i]:
                # 进入静音段
                silence_start = i
                in_silence = True
            elif in_silence and (not is_silence[i] or i == len(is_silence) - 1):
                # 离开静音段或到达末尾
                if i - silence_start >= min_samples:
                    silence_regions.append((silence_start, i))
                in_silence = False

        # 如果没有检测到静音段或不需要缩放，直接返回原始数据
        if not silence_regions or scale_rate == 1.0:
            return sampling_rate, wav_data

        # 创建新的音频数据，根据缩放比例调整静音部分长度
        new_wav_data = []
        last_end = 0

        for start, end in silence_regions:
            # 添加静音前的音频部分
            new_wav_data.append(wav_data[last_end:start])

            # 计算缩放后的静音长度
            silence_length = end - start
            new_silence_length = int(silence_length * scale_rate)
            print(
                f"silence_length: {silence_length}, new_silence_length: {new_silence_length}"
            )

            # 添加缩放后的静音部分 - 保持(n, 1)的形状
            new_wav_data.append(np.zeros((new_silence_length, 1)))

            last_end = end

        # 添加最后一个静音段后的部分
        if last_end < len(wav_data):
            new_wav_data.append(wav_data[last_end:])

        # 合并所有片段
        try:
            new_wav_data = np.concatenate(new_wav_data)
            return sampling_rate, new_wav_data
        except ValueError as e:
            # 如果连接出错，打印错误信息并返回原始数据
            print(f"连接错误: {str(e)}")
            return sampling_rate, wav_data

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
        self,
        speaker,
        prompt_path,
        text,
        infer_mode,
        silence_duration=0.3,
        scale_rate=1.0,
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

                # 缩放音频中的停顿
                if scale_rate != 1.0:
                    _, new_wav_data = self.scale_silence(
                        wav_data, sampling_rate, scale_rate=scale_rate
                    )
                else:
                    new_wav_data = wav_data

                wav_datas.append(new_wav_data)

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
