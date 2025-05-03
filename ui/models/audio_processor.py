"""音频处理模型
负责所有音频相关的处理逻辑，包括音频合并、格式转换、静音生成等。
"""

import os
import traceback
from typing import Tuple, List, Optional, Any

import numpy as np
import torch
import torchaudio


class AudioProcessor:
    """音频处理器类
    负责所有与音频处理相关的操作，如合并、创建静音等
    """
    
    @staticmethod
    def create_silence(duration, sample_rate, num_channels=1):
        """
        创建指定时长的静音
        
        Args:
            duration: 静音时长(秒)
            sample_rate: 采样率
            num_channels: 声道数
            
        Returns:
            torch.Tensor: 静音波形
        """
        # 计算样本数
        num_samples = int(duration * sample_rate)
        # 创建静音波形 (通道数, 样本数)
        silence = torch.zeros(num_channels, num_samples, dtype=torch.int16)
        return silence
    
    @staticmethod
    def normalize_audio_data(audio_data, sample_rate):
        """
        规范化音频数据为(通道数, 样本数)格式的torch.Tensor
        
        Args:
            audio_data: 音频数据，可能是numpy数组或torch.Tensor
            sample_rate: 采样率
            
        Returns:
            tuple: (规范化的波形数据tensor, 采样率)
        """
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
            error_msg = f"规范化音频数据时出错: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            return None, None
    
    @staticmethod
    def merge_audio_data(audio_segments, sample_rate):
        """
        在内存中合并多个音频数据
        
        Args:
            audio_segments: 音频数据列表，每个元素为波形数据
            sample_rate: 采样率
            
        Returns:
            tuple: (合并后的波形, 采样率)
        """
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
                return None, None
            
            # 确保所有波形具有相同的通道数
            num_channels = normalized_segments[0].shape[0]
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
            error_msg = f"合并音频数据时出错: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            return None, None
    
    @staticmethod
    def merge_audio_with_silence(audio_segments, silence_positions, pause_time, sample_rate):
        """
        在内存中合并音频，在指定位置添加静音
        
        Args:
            audio_segments: [(index, waveform), ...] 格式的列表，每个waveform为音频数据
            silence_positions: 需要添加静音的位置列表
            pause_time: 停顿时间（秒）
            sample_rate: 采样率
            
        Returns:
            tuple: (合并后的波形, 采样率)
        """
        if not audio_segments:
            return None, None
        
        try:
            # 获取规范化的第一个波形来确定格式
            _, first_wave = audio_segments[0]
            norm_wave, _ = AudioProcessor.normalize_audio_data(first_wave, sample_rate)
            if norm_wave is None:
                return None, None
                
            num_channels = norm_wave.shape[0]
            
            # 创建输出波形列表
            output_waveforms = []
            
            # 按照原始段落索引排序音频片段
            sorted_outputs = sorted(audio_segments, key=lambda x: x[0])
            
            # 处理所有片段，包括添加<br>对应的静音
            last_index = -1
            
            # 为每个段落添加对应的音频
            for i, (segment_index, wave) in enumerate(sorted_outputs):
                # 先检查是否需要在两个段落之间添加静音
                if i > 0:  # 不是第一个音频片段
                    # 添加段落间静音
                    short_silence = AudioProcessor.create_silence(pause_time / 2, sample_rate, num_channels)
                    output_waveforms.append(short_silence)
                
                # 处理<br>标记的长静音（处理当前段落之前的所有<br>）
                for silence_pos in silence_positions:
                    if last_index < silence_pos < segment_index:
                        # 为每个<br>添加一个完整静音
                        silence = AudioProcessor.create_silence(pause_time, sample_rate, num_channels)
                        output_waveforms.append(silence)
                
                # 添加当前段落的音频（规范化后）
                norm_wave, _ = AudioProcessor.normalize_audio_data(wave, sample_rate)
                if norm_wave is not None:
                    output_waveforms.append(norm_wave)
                
                # 更新最后处理的索引
                last_index = segment_index
            
            # 处理末尾的<br>标记
            for silence_pos in silence_positions:
                if silence_pos > last_index:
                    silence = AudioProcessor.create_silence(pause_time, sample_rate, num_channels)
                    output_waveforms.append(silence)
            
            # 检查是否有波形需要合并
            if not output_waveforms:
                return None, None
            
            # 合并所有波形
            merged_waveform = torch.cat(output_waveforms, dim=1)
            
            return merged_waveform, sample_rate
            
        except Exception as e:
            error_msg = f"合并音频数据并添加静音时出错: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            return None, None
    
    @staticmethod
    def save_audio_to_file(waveform, sample_rate, output_path):
        """
        将内存中的音频保存到文件
        
        Args:
            waveform: 波形数据
            sample_rate: 采样率
            output_path: 输出文件路径
            
        Returns:
            str: 保存的文件路径
        """
        try:
            # 确保输出路径不为空
            if output_path is None:
                error_msg = "保存音频文件时出错: 输出路径为None"
                print(error_msg)
                return None
                
            # 确保输出目录存在
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # 规范化音频数据
            normalized_wave, _ = AudioProcessor.normalize_audio_data(waveform, sample_rate)
            if normalized_wave is None:
                return None
            
            # 保存音频文件
            torchaudio.save(output_path, normalized_wave, sample_rate)
            
            return output_path
            
        except Exception as e:
            error_msg = f"保存音频文件时出错: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            return None 