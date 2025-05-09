#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
音频处理工具模块
提供音频格式转换、处理等功能
"""

import os
import tempfile
from typing import Optional, Tuple
import time
import traceback
import torch
import torchaudio
import numpy as np


def convert_audio_format(input_path: str, 
                        target_format: str = "wav", 
                        sample_rate: int = 44100) -> Optional[str]:
    """转换音频格式
    
    Args:
        input_path: 输入音频路径
        target_format: 目标格式
        sample_rate: 采样率
    
    Returns:
        转换后的音频文件路径
    """
    try:
        import soundfile as sf
        import librosa
        
        # 读取音频
        audio, sr = librosa.load(input_path, sr=sample_rate)
        
        # 创建临时文件
        fd, output_path = tempfile.mkstemp(suffix=f".{target_format}")
        os.close(fd)
        
        # 写入转换后的音频
        sf.write(output_path, audio, sr)
        
        return output_path
    except Exception as e:
        print(f"音频格式转换失败: {e}")
        return None


def get_audio_info(audio_path: str) -> Optional[dict]:
    """获取音频信息
    
    Args:
        audio_path: 音频文件路径
    
    Returns:
        音频信息字典
    """
    try:
        import soundfile as sf
        
        # 获取音频信息
        info = sf.info(audio_path)
        
        return {
            'duration': info.duration,
            'sample_rate': info.samplerate,
            'channels': info.channels,
            'format': info.format,
            'subtype': info.subtype
        }
    except Exception as e:
        print(f"获取音频信息失败: {e}")
        return None


def trim_silence(audio_path: str, 
               output_path: Optional[str] = None,
               threshold_db: float = -40.0) -> Optional[str]:
    """去除音频中的静音段
    
    Args:
        audio_path: 输入音频路径
        output_path: 输出音频路径，默认None则创建临时文件
        threshold_db: 阈值(dB)
    
    Returns:
        处理后的音频文件路径
    """
    try:
        import soundfile as sf
        import librosa
        import numpy as np
        
        # 读取音频
        audio, sr = librosa.load(audio_path, sr=None)
        
        # 去除静音
        intervals = librosa.effects.split(audio, top_db=-threshold_db)
        audio_trimmed = np.concatenate([audio[start:end] for start, end in intervals])
        
        # 创建输出路径
        if output_path is None:
            fd, output_path = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
        
        # 写入处理后的音频
        sf.write(output_path, audio_trimmed, sr)
        
        return output_path
    except Exception as e:
        print(f"去除静音失败: {e}")
        return None 


class AudioUtils:
    """音频处理工具类"""
    
    @staticmethod
    def create_silence(duration, sample_rate, num_channels=1):
        """
        创建指定时长的静音音频数据
        
        Args:
            duration: 静音时长(秒)
            sample_rate: 采样率
            num_channels: 声道数
            
        Returns:
            torch.Tensor: 静音音频数据，形状为 (声道数, 样本数)
        """
        # 计算样本数
        num_samples = int(duration * sample_rate)
        # 创建静音波形 (通道数, 样本数)
        silence = torch.zeros(num_channels, num_samples, dtype=torch.int16)
        return silence
    
    @staticmethod
    def normalize_audio_data(audio_data, sample_rate=24000):
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
                    if audio_data.shape[0] > 10:  # 正常音频通道数不超过10
                        # 几乎肯定是(样本数, 通道数)格式，需要转置为(通道数, 样本数)
                        print(f"检测到音频维度可能颠倒 - 原始形状: {audio_data.shape}，执行转置")
                        audio_tensor = torch.from_numpy(audio_data.T)
                        print(f"转置后形状: {audio_tensor.shape}")
                    elif audio_data.shape[1] > audio_data.shape[0] * 10:
                        # 长宽比严重不平衡，可能是(样本数, 通道数)格式
                        print(f"检测到音频维度可能颠倒 - 原始形状: {audio_data.shape}，执行转置")
                        audio_tensor = torch.from_numpy(audio_data.T)
                        print(f"转置后形状: {audio_tensor.shape}")
                    else:
                        # 可能已经是(通道数, 样本数)格式
                        audio_tensor = torch.from_numpy(audio_data)
                        
                    # 额外检查：如果通道数仍然超过10，可能是格式问题
                    if audio_tensor.shape[0] > 10:
                        print(f"警告: 通道数异常大 ({audio_tensor.shape[0]})，截取为单通道")
                        # 仅保留第一个通道，或创建单通道数据
                        if audio_tensor.shape[1] > 1:
                            # 将第一列数据作为单通道
                            audio_tensor = audio_tensor[0:1, :]  # 保留第一个通道
                        else:
                            # 如果第二维度太小，可能整个格式都反了
                            audio_tensor = audio_tensor[:1]  # 只保留一小部分作为单通道
            elif isinstance(audio_data, torch.Tensor):
                # 如果是torch.Tensor
                if len(audio_data.shape) == 1:
                    # 单声道，形状为(样本数,)
                    # 转换为(1, 样本数)的格式
                    audio_tensor = audio_data.unsqueeze(0)
                elif len(audio_data.shape) == 3:
                    # 3D张量，通常是批处理形式，取第一个
                    print(f"检测到3D张量，取第一个: {audio_data.shape}")
                    audio_tensor = audio_data[0]
                    # 再次检查维度顺序
                    if audio_tensor.shape[0] > 10:
                        print(f"警告: 3D张量处理后通道数异常 ({audio_tensor.shape[0]})，尝试转置")
                        audio_tensor = audio_tensor.transpose(0, 1)
                else:
                    # 2D张量，检查维度顺序
                    if audio_data.shape[0] > 10:
                        print(f"检测到音频维度可能颠倒 - 原始形状: {audio_data.shape}，执行转置")
                        audio_tensor = audio_data.transpose(0, 1)
                        print(f"转置后形状: {audio_tensor.shape}")
                    else:
                        # 已经是正确形式的多维tensor
                        audio_tensor = audio_data
                
                # 额外检查：如果通道数仍然超过10，可能是格式问题
                if len(audio_tensor.shape) >= 2 and audio_tensor.shape[0] > 10:
                    print(f"警告: 通道数异常大 ({audio_tensor.shape[0]})，截取为单通道")
                    # 仅保留第一个通道
                    audio_tensor = audio_tensor[0:1, :]
            else:
                # 不支持的类型
                raise ValueError(f"不支持的音频数据类型: {type(audio_data)}")
            
            # 最终检查：确保形状正确，至少是2D张量
            if len(audio_tensor.shape) == 1:
                audio_tensor = audio_tensor.unsqueeze(0)
            elif len(audio_tensor.shape) > 2:
                print(f"警告: 张量维度过高 {audio_tensor.shape}，降维为2D")
                if audio_tensor.shape[0] <= 10:
                    # 如果第一维看起来像通道数，保留前两维
                    audio_tensor = audio_tensor[:, :, 0]
                else:
                    # 不确定的情况，创建单通道
                    audio_tensor = audio_tensor[0:1, :]
            
            # 确保数据类型为int16
            if audio_tensor.dtype != torch.int16:
                # 如果是浮点类型且范围在[-1, 1]，缩放到int16范围
                if audio_tensor.dtype in [torch.float32, torch.float64] and audio_tensor.abs().max() <= 1.0:
                    audio_tensor = (audio_tensor * 32767).to(torch.int16)
                else:
                    audio_tensor = audio_tensor.to(torch.int16)
            
            print(f"最终规范化后的音频形状: {audio_tensor.shape}, 类型: {audio_tensor.dtype}")
            return audio_tensor, sample_rate
            
        except Exception as e:
            error_msg = f"规范化音频数据时出错: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            return None, None
    
    @staticmethod
    def merge_audio_data(audio_segments, sample_rate=24000):
        """
        在内存中合并多个音频数据段
        
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
                norm_data, _ = AudioUtils.normalize_audio_data(audio_data, sample_rate)
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
    def merge_audio_with_silence(audio_segments, silence_positions, pause_time, sample_rate=24000):
        """
        在内存中合并音频数据，并在指定位置插入静音
        
        Args:
            audio_segments: 音频数据列表，每个元素为元组 (索引, 波形数据)
            silence_positions: 需要插入静音的位置列表（索引）
            pause_time: 静音时长(秒)
            sample_rate: 采样率
            
        Returns:
            tuple: (合并后的波形, 采样率)
        """
        if not audio_segments:
            return None, None
        
        try:
            print(f"合并音频片段，共 {len(audio_segments)} 个，静音位置 {len(silence_positions)} 个")
            
            # 对音频段按照索引排序
            audio_segments = sorted(audio_segments, key=lambda x: x[0])
            
            # 整理音频数据，仅保留波形数据
            wave_segments = [segment[1] for segment in audio_segments]
            
            # 使用规范化函数处理所有片段，确保格式一致
            normalized_segments = []
            for i, wave_data in enumerate(wave_segments):
                try:
                    norm_data, _ = AudioUtils.normalize_audio_data(wave_data, sample_rate)
                    if norm_data is not None:
                        print(f"片段 {i} 规范化后形状: {norm_data.shape}")
                        normalized_segments.append(norm_data)
                    else:
                        print(f"警告: 片段 {i} 规范化失败，跳过")
                except Exception as e:
                    print(f"处理片段 {i} 时出错: {e}")
                    traceback.print_exc()
            
            if not normalized_segments:
                print("错误: 所有音频片段均无法规范化")
                return None, None
            
            # 确保所有波形具有相同的通道数（使用第一个有效片段的通道数）
            first_shape = normalized_segments[0].shape
            num_channels = min(first_shape[0], 2)  # 限制最大通道数为2
            print(f"使用 {num_channels} 个通道进行音频合并")
            
            # 创建静音片段
            silence_duration = int(pause_time * sample_rate)
            silence = torch.zeros(num_channels, silence_duration, dtype=torch.int16)
            print(f"创建静音片段，形状: {silence.shape}")
            
            # 准备所有需要合并的片段
            final_segments = []
            segment_indices = set(segment[0] for segment in audio_segments)
            
            # 顺序处理每个位置
            current_index = 0
            while True:
                # 如果是静音位置，添加静音
                if current_index in silence_positions:
                    final_segments.append(silence)
                    print(f"位置 {current_index}: 添加静音")
                
                # 如果是音频段位置，添加音频
                if current_index in segment_indices:
                    # 找到对应的规范化后的音频数据
                    segment_position = next(i for i, (idx, _) in enumerate(audio_segments) if idx == current_index)
                    if segment_position < len(normalized_segments):
                        audio_data = normalized_segments[segment_position]
                        
                        # 确保通道数一致
                        if audio_data.shape[0] != num_channels:
                            print(f"调整片段 {current_index} 的通道数从 {audio_data.shape[0]} 到 {num_channels}")
                            if audio_data.shape[0] < num_channels:
                                # 如果通道数少，复制通道（单通道转立体声）
                                audio_data = audio_data.repeat(num_channels, 1)[:num_channels]
                            else:
                                # 如果通道数多，只保留需要的通道
                                audio_data = audio_data[:num_channels]
                        
                        final_segments.append(audio_data)
                        print(f"位置 {current_index}: 添加音频，形状: {audio_data.shape}")
                
                # 更新索引
                current_index += 1
                
                # 如果已经处理完所有位置，退出循环
                if current_index > max(max(segment_indices, default=-1), max(silence_positions, default=-1)):
                    break
            
            # 检查是否有有效的片段
            if not final_segments:
                print("错误: 没有有效的音频片段可合并")
                return None, None
            
            # 确保所有片段形状一致
            for i, segment in enumerate(final_segments):
                if segment.shape[0] != num_channels:
                    print(f"警告: 片段 {i} 通道数不一致，从 {segment.shape[0]} 调整为 {num_channels}")
                    if segment.shape[0] < num_channels:
                        # 通道数少，复制
                        final_segments[i] = segment.repeat(num_channels, 1)[:num_channels]
                    else:
                        # 通道数多，截取
                        final_segments[i] = segment[:num_channels]
            
            # 输出最终所有片段的形状，用于调试
            shapes = [segment.shape for segment in final_segments]
            print(f"最终合并的片段形状: {shapes}")
            
            try:
                # 使用torch.cat合并所有片段
                merged_waveform = torch.cat(final_segments, dim=1)
                print(f"合并后的音频形状: {merged_waveform.shape}")
                return merged_waveform, sample_rate
            except Exception as e:
                print(f"合并音频片段失败: {e}")
                traceback.print_exc()
                
                # 检查是否存在形状不一致的问题
                channels = [s.shape[0] for s in final_segments]
                if len(set(channels)) > 1:
                    print(f"错误: 通道数不一致: {channels}")
                
                return None, None
                
        except Exception as e:
            print(f"处理音频片段时出错: {e}")
            traceback.print_exc()
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
            normalized_wave, _ = AudioUtils.normalize_audio_data(waveform, sample_rate)
            if normalized_wave is None:
                return None
            
            # 保存音频文件
            torchaudio.save(output_path, normalized_wave, sample_rate)
            
            return output_path
            
        except Exception as e:
            error_msg = f"保存音频文件时出错: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            return None 