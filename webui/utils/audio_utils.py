#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
音频处理工具模块
提供音频格式转换、处理等功能
"""

import os
import tempfile
from typing import Optional, Tuple


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