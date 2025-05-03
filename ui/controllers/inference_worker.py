"""推理工作线程控制器
提供TTS推理的后台处理功能。
"""

import os
import time
import re
from pathlib import Path
import tempfile
import uuid
import wave
import numpy as np
import contextlib
import torch
from typing import List, Tuple, Dict, Optional, Any

from PySide6.QtCore import QObject, Signal, QMutex, QWaitCondition
from ui.controllers.inference_base import InferenceBase
from ui.controllers.multi_role_inference import MultiRoleInference
from ui.utils.text_processor import TextProcessor
from ui.config import REPLACE_RULES_CONFIG_PATH


class ConfigManager:
    """配置管理器类
    负责处理配置文件的加载和缓存
    """
    # 类级别的配置缓存
    _replace_rules_cache = []  # 缓存的替换规则
    _config_last_modified = 0  # 配置文件最后修改时间
    
    @classmethod
    def load_replace_rules(cls, config_path):
        """加载文本替换规则，根据文件修改时间决定是否使用缓存"""
        if not os.path.exists(config_path):
            return []
            
        # 获取文件最后修改时间
        current_mtime = os.path.getmtime(config_path)
        
        # 检查是否需要重新加载
        if current_mtime > cls._config_last_modified or not cls._replace_rules_cache:
            rules = TextProcessor.load_replace_rules_from_file(config_path)
            # 更新类级别的缓存
            cls._replace_rules_cache = rules.copy()
            cls._config_last_modified = current_mtime
            print(f"配置文件已更新，重新加载 {len(rules)} 条规则")
            return rules
        else:
            # 使用缓存的规则
            print(f"使用缓存的 {len(cls._replace_rules_cache)} 条替换规则")
            return cls._replace_rules_cache.copy()


class AudioProcessor:
    """音频处理器类
    负责所有与音频处理相关的操作，如合并、创建静音等
    """
    @staticmethod
    def create_silence(duration, sample_rate):
        """创建指定时长的静音"""
        import torch
        # 计算样本数
        num_samples = int(duration * sample_rate)
        # 创建静音波形 (通道数, 样本数)
        silence = torch.zeros(1, num_samples, dtype=torch.int16)
        return silence
    
    @staticmethod
    def normalize_audio_data(audio_data, sample_rate):
        """规范化音频数据为(通道数, 样本数)格式的torch.Tensor"""
        import torch
        import numpy as np
        
        try:
            if isinstance(audio_data, np.ndarray):
                # 如果是numpy数组
                if len(audio_data.shape) == 1:
                    # 单声道，形状为(样本数,)
                    # 转换为(1, 样本数)的格式
                    audio_tensor = torch.from_numpy(audio_data).unsqueeze(0)
                elif len(audio_data.shape) > 1:
                    # 多声道，检查是否需要转置
                    if audio_data.shape[1] > audio_data.shape[0] or audio_data.shape[1] <= 8:
                        # 很可能是(样本数, 通道数)格式，需要转置为(通道数, 样本数)
                        audio_tensor = torch.from_numpy(audio_data.T)
                    else:
                        # 可能已经是(通道数, 样本数)格式
                        audio_tensor = torch.from_numpy(audio_data)
            elif isinstance(audio_data, torch.Tensor):
                # 如果是torch.Tensor
                if len(audio_data.shape) == 1:
                    # 单声道，形状为(样本数,)
                    # 转换为(1, 样本数)的格式
                    audio_tensor = audio_data.unsqueeze(0)
                else:
                    # 已经是多维tensor，假设格式正确
                    audio_tensor = audio_data
            else:
                # 不支持的类型
                raise ValueError(f"不支持的音频数据类型: {type(audio_data)}")
            
            # 确保数据类型为int16
            if audio_tensor.dtype != torch.int16:
                # 如果是浮点类型且范围在[-1, 1]，缩放到int16范围
                if audio_tensor.dtype in [torch.float32, torch.float64] and audio_tensor.abs().max() <= 1.0:
                    audio_tensor = (audio_tensor * 32767).to(torch.int16)
                else:
                    audio_tensor = audio_tensor.to(torch.int16)
            
            return audio_tensor, sample_rate
            
        except Exception as e:
            import traceback
            error_msg = f"规范化音频数据时出错: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            return None, None
    
    @staticmethod
    def merge_audio_data_with_br(audio_segments, silence_positions, pause_time, sample_rate):
        """在内存中合并音频数据，在<br>标记处添加静音"""
        import torch
        
        # 检查是否有音频数据
        if not audio_segments:
            raise ValueError("没有音频数据可合并")
        
        # 创建输出波形列表
        output_waveforms = []
        
        # 按照原始段落索引排序音频片段
        sorted_outputs = sorted(audio_segments, key=lambda x: x[0])
        
        # 处理所有片段，包括添加<br>对应的静音
        last_index = -1
        for segment_index, wave_data in sorted_outputs:
            # 处理中间的<br>标记
            for silence_pos in silence_positions:
                if last_index < silence_pos < segment_index:
                    # 为每个<br>添加一个静音
                    silence = AudioProcessor.create_silence(pause_time, sample_rate)
                    output_waveforms.append(silence)
            
            # 规范化当前段落的音频
            norm_wave, _ = AudioProcessor.normalize_audio_data(wave_data, sample_rate)
            if norm_wave is not None:
                # 添加当前段落的音频
                output_waveforms.append(norm_wave)
            
            # 添加静音
            silence = AudioProcessor.create_silence(pause_time/2, sample_rate)
            output_waveforms.append(silence)
            
            # 更新最后处理的索引
            last_index = segment_index
        
        # 处理末尾的<br>标记
        for silence_pos in silence_positions:
            if silence_pos > last_index:
                silence = AudioProcessor.create_silence(pause_time, sample_rate)
                output_waveforms.append(silence)
        
        # 检查是否有波形需要合并
        if not output_waveforms:
            raise ValueError("没有可合并的音频片段")
        
        # 合并所有波形
        merged_waveform = torch.cat(output_waveforms, dim=1)
        
        return merged_waveform, sample_rate
    
    @staticmethod
    def merge_audio_data(audio_segments, sample_rate):
        """在内存中合并多个音频数据"""
        import torch
        
        if not audio_segments:
            return None, None
        
        try:
            # 规范化所有音频片段
            normalized_segments = []
            for audio_data in audio_segments:
                norm_data, _ = AudioProcessor.normalize_audio_data(audio_data, sample_rate)
                if norm_data is not None:
                    normalized_segments.append(norm_data)
            
            if not normalized_segments:
                print("错误: 没有可合并的有效音频数据")
                return None, None
            
            # 确保所有波形具有相同的通道数
            num_channels = normalized_segments[0].shape[0]
            
            # 创建一个列表用于存储所有处理后的音频片段
            processed_waveforms = []
            
            # 依次处理每个波形
            for waveform in normalized_segments:
                # 确保声道数一致
                if waveform.shape[0] != num_channels:
                    if waveform.shape[0] < num_channels:
                        # 如果声道数少，复制声道
                        waveform = waveform.repeat(num_channels, 1)
                    else:
                        # 如果声道数多，只保留需要的声道数
                        waveform = waveform[:num_channels, :]
                
                # 添加到列表
                processed_waveforms.append(waveform)
            
            # 使用torch.cat沿时间维度合并所有波形
            merged_waveform = torch.cat(processed_waveforms, dim=1)
            
            return merged_waveform, sample_rate
            
        except Exception as e:
            import traceback
            error_msg = f"合并音频数据时出错: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            return None, None
    
    @staticmethod
    def save_audio_to_file(waveform, sample_rate, output_path):
        """将内存中的音频保存到文件"""
        try:
            # 确保输出目录存在
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # 规范化音频数据
            normalized_wave, _ = AudioProcessor.normalize_audio_data(waveform, sample_rate)
            if normalized_wave is None:
                return None
            
            # 保存合并后的文件
            import torchaudio
            torchaudio.save(output_path, normalized_wave, sample_rate)
            
            return output_path
        
        except Exception as e:
            import traceback
            error_msg = f"保存音频文件时出错: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            return None


class InferenceWorker(QObject):
    """推理工作线程类，用于执行语音生成任务"""
    # 定义信号
    finished = Signal(str)  # 推理完成信号，返回输出文件路径
    progress = Signal(str)  # 进度信号，发送处理状态信息
    error = Signal(str)     # 错误信号
    
    # 特殊标记
    BR_TAG = "<br>"  # 空行标记
    # 固定的配置文件路径
    REPLACE_CONFIG_PATH = REPLACE_RULES_CONFIG_PATH

    def __init__(self, tts, voice_path, text, output_path=None, 
                 punct_chars="。？！", pause_time=0.3):
        super().__init__()
        self.tts = tts
        self.voice_path = voice_path
        self.text = text
        self.output_path = output_path
        self.punct_chars = punct_chars    # 分割标点符号
        self.pause_time = pause_time      # 段落间停顿时间（秒）
        self._stop_requested = False      # 停止标志
        
        # 加载配置
        self.replace_rules = ConfigManager.load_replace_rules(self.REPLACE_CONFIG_PATH)
        
        # 使用内存模式标志
        self.in_memory_mode = True

    def stop(self):
        """请求停止推理过程"""
        self._stop_requested = True
        self.progress.emit("正在停止推理过程...")
    
    def is_stop_requested(self):
        """检查是否请求停止推理"""
        return self._stop_requested

    def run(self):
        """
        执行推理任务
        该方法在单独的线程中运行
        """
        try:
            success, output_file = self.process_inference()
            
            # 发送完成信号
            if success and output_file:
                self.finished.emit(output_file)
            else:
                if self.is_stop_requested():
                    self.error.emit("推理已被用户中断")
                else:
                    self.error.emit("语音生成失败")
                
        except Exception as e:
            import traceback
            error_msg = f"推理出错: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            self.error.emit(error_msg)

    def process_inference(self):
        """
        处理推理任务，可被同步调用
        
        Returns:
            tuple: (success, output_file_path)
                success (bool): 是否成功完成推理
                output_file_path (str): 输出音频文件路径，如果处理失败则为None
        """
        try:
            # 检查参考音频是否存在
            if not os.path.exists(self.voice_path):
                self.error.emit(f"参考音频文件不存在: {self.voice_path}")
                return False, None
            
            # 检查文本是否为空
            if not self.text.strip():
                self.error.emit("推理文本不能为空")
                return False, None
            
            # 生成输出路径（如果未提供）
            if not self.output_path:
                # 创建输出目录（如果不存在）
                output_dir = "outputs"
                if not os.path.exists(output_dir):
                    os.makedirs(output_dir, exist_ok=True)
                # 为输出文件生成一个带时间戳的文件名
                timestamp = time.strftime("%Y%m%d%H%M%S", time.localtime())
                self.output_path = os.path.join(output_dir, f"output_{timestamp}.wav")
            
            # 确保输出目录存在
            os.makedirs(os.path.dirname(self.output_path), exist_ok=True)
            
            # 预处理文本
            self.progress.emit("正在预处理文本...")
            preprocessed_segments = TextProcessor.preprocess_text(
                self.text, self.punct_chars, self.replace_rules
            )
            
            # 根据段落数量决定处理方式
            if len(preprocessed_segments) > 1:
                return self._process_text_in_segments(preprocessed_segments)
            else:
                # 作为单个文本处理
                self.progress.emit("文本将作为整体处理...")
                return self._process_single_text(self.text, self.output_path)
            
        except Exception as e:
            import traceback
            error_msg = f"处理推理任务时出错: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            self.error.emit(error_msg)
            return False, None
    
    def _save_partial_output(self, temp_outputs, silence_positions, preprocessed_segments):
        """尝试保存部分处理结果，成功则返回True，失败返回False"""
        if not temp_outputs:
            return False
            
        self.progress.emit("正在合并已生成的部分内容...")
        try:
            # 获取基础文件名（如果有）
            base_output_path = self.output_path
            base_filename = os.path.splitext(os.path.basename(base_output_path))[0]
            # 添加部分输出标记，保持文件名格式一致
            partial_output_path = os.path.join("outputs", f"{base_filename}_部分.wav")
            
            self.progress.emit(f"正在合并 {len(temp_outputs)} 个已生成的片段...")
            
            # 使用内存模式合并音频
            merged_wave, sr = AudioProcessor.merge_audio_data_with_br(
                temp_outputs, silence_positions, self.pause_time, 24000
            )
            
            # 保存合并后的音频
            AudioProcessor.save_audio_to_file(merged_wave, sr, partial_output_path)
                    
            self.progress.emit(f"已成功保存部分结果到: {os.path.basename(partial_output_path)}")
            self.finished.emit(partial_output_path)
            return True
            
        except Exception as e:
            print(f"合并部分结果出错: {str(e)}")
            # 如果合并失败，仍然尝试保留最后一个生成的片段
            if temp_outputs:
                try:
                    _, last_wave = temp_outputs[-1]
                    # 获取基础文件名（如果有）
                    base_output_path = self.output_path
                    base_filename = os.path.splitext(os.path.basename(base_output_path))[0]
                    # 添加部分输出标记，保持文件名格式一致
                    partial_output_path = os.path.join("outputs", f"{base_filename}_最后片段.wav")
                    
                    self.progress.emit("合并失败，尝试保存最后生成的片段...")
                    import torchaudio
                    torchaudio.save(partial_output_path, last_wave, 24000)
                    
                    self.progress.emit(f"已保存部分结果: {os.path.basename(partial_output_path)}")
                    self.finished.emit(partial_output_path)
                    return True
                except Exception as e2:
                    print(f"保存最后一个片段出错: {str(e2)}")
        
        return False
    
    def _process_text_in_segments(self, preprocessed_segments=None):
        """按段落处理文本，返回(success, output_file_path)"""
        try:
            if preprocessed_segments is None:
                preprocessed_segments = TextProcessor.preprocess_text(
                    self.text, self.punct_chars, self.replace_rules
                )
            
            self.progress.emit(f"共分为 {len(preprocessed_segments)} 个片段进行处理...")
            temp_outputs = []
            silence_positions = []  # 记录需要添加静音的位置
            
            segment_index = 0
            for i, segment in enumerate(preprocessed_segments):
                # 检查是否请求停止
                if self.is_stop_requested():
                    # 尝试保存部分结果
                    if self._save_partial_output(temp_outputs, silence_positions, preprocessed_segments):
                        return True, self.output_path
                    
                    # 如果无法保存部分结果，则报告中断
                    self.error.emit("推理已被用户中断")
                    return False, None
                
                if segment == self.BR_TAG:  # 处理<br>标记
                    silence_positions.append(i)
                    continue
                
                if not segment.strip():  # 跳过空片段
                    continue
                
                self.progress.emit(f"处理第 {segment_index+1}/{len(preprocessed_segments) - len(silence_positions)} 段...")
                
                # 使用内存模式进行推理
                result = self.tts.infer(self.voice_path, segment, None)
                
                if isinstance(result, tuple) and len(result) == 2:
                    # 返回的是内存数据格式 (采样率, 波形数据)
                    sample_rate, wave_data = result
                    
                    # 添加到临时输出列表，不在这里转换格式
                    temp_outputs.append((i, wave_data))
                else:
                    self.progress.emit(f"警告: 段落 {segment_index+1} 推理结果格式不正确")
                
                segment_index += 1
            
            # 检查是否请求停止
            if self.is_stop_requested():
                # 尝试保存部分结果
                if self._save_partial_output(temp_outputs, silence_positions, preprocessed_segments):
                    return True, self.output_path
                
                # 如果无法保存部分结果，则报告中断
                self.error.emit("推理已被用户中断")
                return False, None
            
            # 检查是否有有效输出
            if not temp_outputs:
                self.error.emit("没有生成任何有效的音频片段")
                return False, None
            
            # 合并所有音频片段，包括<br>标记处的静音
            self.progress.emit(f"合并音频片段，添加段落间静音 ({self.pause_time}秒)...")
            
            # 使用内存模式合并音频
            merged_wave, sr = AudioProcessor.merge_audio_data_with_br(
                temp_outputs, silence_positions, self.pause_time, 24000
            )
            
            if merged_wave is None:
                self.error.emit("合并音频数据失败")
                return False, None
            
            # 保存最终输出
            self.progress.emit("正在保存最终音频文件...")
            output_file = AudioProcessor.save_audio_to_file(merged_wave, sr, self.output_path)
            
            if output_file and os.path.exists(output_file):
                return True, output_file
            else:
                self.error.emit("保存音频文件失败")
                return False, None
            
        except Exception as e:
            import traceback
            error_msg = f"按段落处理文本时出错: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            self.error.emit(error_msg)
            return False, None
    
    def _process_single_text(self, text, output_path):
        """处理单个文本片段，返回(success, output_file_path)"""
        try:
            # 检查是否请求停止
            if self.is_stop_requested():
                self.error.emit("推理已被用户中断")
                return False, None
            
            self.progress.emit("开始语音生成...")
            
            # 应用文本替换规则（如果有）
            if self.replace_rules:
                text = TextProcessor.apply_replace_rules(text, self.replace_rules)
            
            if self.in_memory_mode:
                # 使用内存模式进行推理
                result = self.tts.infer(self.voice_path, text, None)
                
                if isinstance(result, tuple) and len(result) == 2:
                    # 返回的是内存数据格式 (采样率, 波形数据)
                    sample_rate, wave_data = result
                    
                    # 最后检查一次是否请求停止
                    if self.is_stop_requested():
                        # 仍然保存结果
                        self.progress.emit("推理已完成，正在保存...")
                    
                    # 保存到文件，不在这里转换格式
                    self.progress.emit("正在保存音频文件...")
                    output_file = AudioProcessor.save_audio_to_file(wave_data, sample_rate, output_path)
                    
                    if output_file and os.path.exists(output_file):
                        self.progress.emit("语音生成完成！")
                        return True, output_file
                    else:
                        self.error.emit("保存音频文件失败")
                        return False, None
                else:
                    self.error.emit("推理返回格式不正确")
                    return False, None
            else:
                # 兼容模式：直接使用文件模式
                self.tts.infer(self.voice_path, text, output_path)
                
                # 最后检查一次是否请求停止
                if self.is_stop_requested():
                    # 检查输出文件是否已经存在且有效
                    if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                        self.progress.emit("已保存生成结果")
                        return True, output_path
                    else:
                        self.error.emit("推理已被用户中断")
                        return False, None
                
                # 检查输出文件是否存在且有效
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    self.progress.emit("语音生成完成！")
                    return True, output_path
                else:
                    self.error.emit("语音生成失败")
                    return False, None
            
        except Exception as e:
            import traceback
            error_msg = f"处理单个文本片段时出错: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            self.error.emit(error_msg)
            return False, None


class MultiRoleInferenceWorker(MultiRoleInference):
    """多角色推理工作器类
    
    注意：此类已被 ui.controllers.multi_role_inference.MultiRoleInference 取代，
    将在后续版本中移除。请直接使用 MultiRoleInference 类。
    """
    
    def __init__(self, *args, **kwargs):
        import warnings
        warnings.warn(
            "MultiRoleInferenceWorker 类已被弃用，请直接使用 MultiRoleInference 类",
            DeprecationWarning, stacklevel=2
        )
        super().__init__(*args, **kwargs) 