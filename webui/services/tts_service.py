import gradio as gr
import numpy as np
import torch
import torchaudio
import random

from indextts.infer import IndexTTS
from webui.utils.text_processor import TextProcessor
from webui.services.prompt_service import PromptService
from webui.utils.logger import debug, error, info


class TTS_Service:
    def __init__(self, progress=gr.Progress(), config_service=None):
        self.progress = progress
        self.text_processor = TextProcessor()
        self.prompt_service = PromptService()
        self.config_service = config_service
        self.tts = None
        self.current_tts_version = None

    def __del__(self):
        """确保在对象销毁时释放资源"""
        try:
            if self.tts is not None:
                debug("TTS_Service 析构：清理TTS模型显存")
                self.tts.torch_empty_cache()
                self.tts = None
                # 清理CUDA缓存
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
        except Exception as e:
            error(f"释放TTS模型资源时出错: {str(e)}")

    def _set_progress(self, value, desc):
        if self.progress is not None:
            self.progress(value, desc=desc)

    def save_wav(self, wav_data, sampling_rate, file_path):
        if isinstance(wav_data, np.ndarray):
            wav_data = wav_data.T
            wav_tensor = torch.from_numpy(wav_data).type(torch.int16)
        else:
            wav_tensor = wav_data
        torchaudio.save(file_path, wav_tensor, sampling_rate)

    def gen_wavdata(
        self, prompt_path, text, infer_mode, silence_duration=0.3,  tts_version=1, max_text_tokens_per_sentence=80
    ):
        """根据选择的参考音频名称和文本生成音频数据"""

        # 仅在初次使用或版本变更时实例化TTS模型
        if self.tts is None or self.current_tts_version != tts_version:
            debug(f"初始化或更新TTS模型，版本：{tts_version}")

            # 如果存在旧模型，先清理其占用的显存
            if self.tts is not None:
                debug(f"清理旧版本({self.current_tts_version})TTS模型的显存")

                # 使用IndexTTS自带的方法清理显存
                self.tts.torch_empty_cache()

                # 先将引用设为None，帮助垃圾回收
                self.tts = None

                # 强制执行一次垃圾回收
                import gc

                gc.collect()

                # 再次清理CUDA缓存
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    debug("显存已清理")

            # 初始化新的TTS模型
            if tts_version == 1:
                self.tts = IndexTTS(
                    model_dir="checkpoints/1.0", cfg_path="checkpoints/1.0/config.yaml"
                )
            else:
                self.tts = IndexTTS(
                    model_dir="checkpoints/1.5", cfg_path="checkpoints/1.5/config.yaml"
                )
            self.current_tts_version = tts_version

            if torch.cuda.is_available():
                debug(f"当前显存占用: {torch.cuda.memory_allocated() / 1024**2:.2f} MB")

        debug(f"tts_version: {tts_version}, model_dir: {self.tts.model_dir}")

        if infer_mode == "普通推理":
            sampling_rate, wav_data = self.tts.infer(
                prompt_path,
                text,
                None,
                verbose=True,
                max_text_tokens_per_sentence=max_text_tokens_per_sentence,
                silence_duration=silence_duration,
            )  # 普通推理
        else:
            sampling_rate, wav_data = self.tts.infer_fast(
                prompt_path,
                text,
                None,
                verbose=False,
            )  # 批次推理
        return sampling_rate, wav_data

    def _set_all_seeds(self, seed):
        """Sets the seed for reproducibility across different libraries."""
        random.seed(seed)
        np.random.seed(seed)
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed(seed)
            torch.cuda.manual_seed_all(seed)

        return seed

    def gen_wavdata_togr(
        self,
        speaker,
        prompt_path,
        text,
        infer_mode,
        silence_duration=0.3,
        seed=0,
        tts_version=1,
        max_text_tokens_per_sentence=80,
    ):
        # self.tts.gr_progress = progress

        # 设置cuda随机种子
        if seed != 0:
            debug(f"设置cuda随机种子: {seed}")
            self._set_all_seeds(seed)

        # 预处理文本
        text_segments = self.text_processor.preprocess_text(text, speaker)

        debug(f"text_segments: {text_segments}")

        if len(text_segments) <= 0:
            error("待推理文本段落数不能为空")
            # 返回空音频数据
            return gr.update(value=None, visible=True)

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

            _silence_duration = silence_duration
            _seed = seed
            _tts_version = tts_version

            if self.config_service and _speaker:
                settings = self.config_service.get_audio_settings(_speaker)
                _silence_duration = settings.get("silence_duration", silence_duration)
                _seed = settings.get("seed", seed)
                _tts_version = settings.get("tts_version", tts_version)

            debug(
                f"当前角色: {_speaker}, 当前文本: {_text}, 静音时长={_silence_duration}, 随机种子={_seed}, TTS版本={_tts_version}"
            )

            # 处理空行
            if _text == self.text_processor.BR_TAG and sampling_rate is not None:
                # 计算静音长度所需的采样点数
                silence_samples = int(sampling_rate * _silence_duration)
                if first_shape is not None and len(first_shape) > 1:  # 处理多通道音频
                    wav_data = np.zeros((silence_samples, first_shape[1]))
                else:
                    wav_data = np.zeros(silence_samples)

                debug(f"添加静音: {_silence_duration}秒")
                wav_datas.append(wav_data)
                continue

            # 更新进度条
            self._set_progress(
                current_step / total_step,
                f"合成中: {current_step}/{total_step}，文本: {_text[:30] + '...' if len(_text) > 30 else _text}",
            )
            current_step += 1

            sampling_rate, wav_data = self.gen_wavdata(
                _prompt_path, _text, infer_mode, _silence_duration, tts_version, max_text_tokens_per_sentence
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

        output_path = self.text_processor.generate_output_filename(
            speaker_str, text, seed
        )
        info(f"语音合成完成: {output_path}")

        # 确保音频数据保存前处于正确的状态
        self.save_wav(wav_data, sampling_rate, output_path)

        return gr.update(value=(sampling_rate, wav_data), visible=True)
