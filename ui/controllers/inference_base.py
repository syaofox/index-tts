"""推理工作基类
提供TTS推理的基础抽象类及公共功能。
"""

import os
import time
import torch
import torchaudio
import tempfile
import uuid
from abc import abstractmethod
from typing import List, Tuple, Optional, Dict, Any

from PySide6.QtCore import QObject, Signal, QMutex, QWaitCondition


# 解决方案：创建一个自定义元类来解决冲突
class InferenceBase(QObject):
    """推理工作基类，提供统一的接口和公共方法"""
    
    # 定义信号
    finished = Signal(str)   # 推理完成信号，返回输出文件路径
    progress = Signal(str)   # 进度信号
    error = Signal(str)      # 错误信号
    
    # 特殊标记
    BR_TAG = "<br>"  # 空行标记
    
    def __init__(self, tts, output_path=None, punct_chars="。？！", pause_time=0.3):
        """
        初始化推理基类
        
        Args:
            tts: TTS模型对象
            output_path: 输出音频文件路径，如果为None则自动生成
            punct_chars: 分割文本的标点符号
            pause_time: 段落间停顿时间(秒)
        """
        super().__init__()
        self.tts = tts
        self.output_path = output_path
        self.punct_chars = punct_chars
        self.pause_time = pause_time
        
        # 停止标志及同步控制
        self._stop_requested = False
        self._mutex = QMutex()
        self._condition = QWaitCondition()
    
    def stop(self):
        """请求停止推理过程"""
        self._mutex.lock()
        self._stop_requested = True
        self._mutex.unlock()
        self._condition.wakeAll()
        self.progress.emit("正在停止推理过程...")
    
    def is_stop_requested(self):
        """检查是否请求停止推理"""
        self._mutex.lock()
        result = self._stop_requested
        self._mutex.unlock()
        return result
    
    def run(self):
        """
        执行推理任务，在单独线程中运行
        此方法会被QThread调用
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
    
    def generate_output_path(self):
        """生成默认输出路径"""
        if not self.output_path:
            # 创建输出目录（如果不存在）
            output_dir = "outputs"
            self.ensure_dir_exists(output_dir)
            
            # 生成带时间戳的文件名
            timestamp = time.strftime("%Y%m%d%H%M%S", time.localtime())
            self.output_path = os.path.join(output_dir, f"output_{timestamp}.wav")
        
        # 确保输出目录存在
        self.ensure_dir_exists(os.path.dirname(self.output_path))
        return self.output_path
    
    @abstractmethod
    def process_inference(self):
        """
        处理推理任务，需要被子类实现
        
        Returns:
            tuple: (success, output_file_path)
                success (bool): 是否成功完成推理
                output_file_path (str): 输出音频文件路径，如果处理失败则为None
        """
        pass
    
    def ensure_dir_exists(self, dir_path):
        """确保目录存在，如果不存在则创建"""
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
    
    @staticmethod
    def merge_audio_files(audio_files, output_path, channels=1):
        """
        合并多个WAV音频文件
        
        Args:
            audio_files (list): 要合并的WAV文件路径列表
            output_path (str): 合并后的输出文件路径
            channels (int): 音频通道数
            
        Returns:
            str: 合并后的文件路径，如果失败则返回None
        """
        if not audio_files:
            return None
        
        try:
            # 如果只有一个文件，直接复制
            if len(audio_files) == 1:
                from shutil import copy2
                copy2(audio_files[0], output_path)
                return output_path
            
            # 读取第一个文件以获取采样率
            waveform, sample_rate = torchaudio.load(audio_files[0])
            
            # 创建一个列表用于存储所有音频片段
            waveforms = []
            
            # 依次读取每个文件并添加到列表
            for file_path in audio_files:
                # 检查文件是否存在且有效
                if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
                    print(f"警告: 跳过不存在或空的文件 {file_path}")
                    continue
                    
                # 加载音频文件
                try:
                    current_waveform, current_sr = torchaudio.load(file_path)
                    
                    # 如果采样率不一致，则进行重采样
                    if current_sr != sample_rate:
                        resampler = torchaudio.transforms.Resample(current_sr, sample_rate)
                        current_waveform = resampler(current_waveform)
                    
                    # 确保声道数一致
                    if current_waveform.shape[0] != channels:
                        if current_waveform.shape[0] < channels:
                            # 如果声道数少，复制声道
                            current_waveform = current_waveform.repeat(channels, 1)
                        else:
                            # 如果声道数多，只保留需要的声道数
                            current_waveform = current_waveform[:channels, :]
                    
                    # 添加到列表
                    waveforms.append(current_waveform)
                except Exception as e:
                    print(f"警告: 加载文件 {file_path} 出错: {e}")
                    continue
            
            # 检查是否有可合并的波形
            if not waveforms:
                print("错误: 没有可合并的有效音频文件")
                return None
                
            # 使用torch.cat沿时间维度合并所有波形
            merged_waveform = torch.cat(waveforms, dim=1)
            
            # 确保输出目录存在
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # 保存合并后的文件
            torchaudio.save(output_path, merged_waveform, sample_rate)
            
            return output_path
        
        except Exception as e:
            import traceback
            error_msg = f"合并音频文件时出错: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            return None
    
    @staticmethod
    def create_silence(duration, sample_rate=44100, channels=1):
        """
        创建指定时长的静音
        
        Args:
            duration (float): 静音时长，以秒为单位
            sample_rate (int): 采样率
            channels (int): 音频通道数
            
        Returns:
            torch.Tensor: 静音波形
        """
        # 计算样本数
        num_samples = int(duration * sample_rate)
        # 创建静音波形 (通道数, 样本数)
        silence = torch.zeros(channels, num_samples)
        return silence 