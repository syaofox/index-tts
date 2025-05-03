"""推理工作基类
提供TTS推理的基础抽象类及公共功能。
"""

import os
import time
import torch
import torchaudio
import tempfile
import uuid
import shutil
import traceback
from abc import abstractmethod
from typing import List, Tuple, Optional, Dict, Any, Union

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
        
        # 创建临时目录
        self.temp_dir = os.path.join("outputs", "temp", str(uuid.uuid4()))
    
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
        
    def merge_audio_files_with_silence(self, temp_outputs, silence_positions, output_path):
        """
        合并音频文件，在指定位置添加静音
        
        Args:
            temp_outputs (list): 临时输出文件列表，格式为[(index, file_path), ...]
            silence_positions (list): 静音位置列表
            output_path (str): 输出文件路径
        """
        # 检查是否有音频文件
        if not temp_outputs:
            raise ValueError("没有音频文件可合并")
        
        # 读取第一个文件以获取采样率
        _, first_file = temp_outputs[0]
        if not os.path.exists(first_file):
            raise ValueError(f"文件不存在: {first_file}")
            
        waveform, sample_rate = torchaudio.load(first_file)
        
        # 创建输出波形列表
        output_waveforms = []
        
        # 按照原始段落索引排序音频文件
        sorted_outputs = sorted(temp_outputs, key=lambda x: x[0])
        
        # 添加额外的调试信息
        print(f"处理 {len(sorted_outputs)} 个音频片段和 {len(silence_positions)} 个空行位置")
        print(f"音频索引: {[idx for idx, _ in sorted_outputs]}")
        print(f"静音位置: {silence_positions}")
        
        # 处理所有片段，包括添加<br>对应的静音
        last_index = -1
        
        # 为每个段落添加对应的音频
        for i, (segment_index, audio_file) in enumerate(sorted_outputs):
            # 先检查是否需要在两个段落之间添加静音
            if i > 0:  # 不是第一个音频片段
                # 添加段落间静音
                short_silence = self.create_silence(self.pause_time / 2, sample_rate, waveform.shape[0])
                output_waveforms.append(short_silence)
            
            # 处理<br>标记的长静音（处理当前段落之前的所有<br>）
            br_count = 0
            for silence_pos in silence_positions:
                if last_index < silence_pos < segment_index:
                    br_count += 1
                    # 为每个<br>添加一个完整静音
                    silence = self.create_silence(self.pause_time, sample_rate, waveform.shape[0])
                    output_waveforms.append(silence)
            
            if br_count > 0:
                print(f"在段落 {segment_index} 之前添加了 {br_count} 个空行静音")
            
            # 确保文件存在
            if not os.path.exists(audio_file):
                print(f"警告: 跳过不存在的文件 {audio_file}")
                continue
                
            # 添加当前段落的音频
            try:
                audio_waveform, sr = torchaudio.load(audio_file)
                if sr != sample_rate:
                    audio_waveform = torchaudio.transforms.Resample(sr, sample_rate)(audio_waveform)
                    
                # 确保声道数匹配
                if audio_waveform.shape[0] != waveform.shape[0]:
                    if audio_waveform.shape[0] < waveform.shape[0]:
                        audio_waveform = audio_waveform.repeat(waveform.shape[0], 1)
                    else:
                        audio_waveform = audio_waveform[:waveform.shape[0], :]
                        
                output_waveforms.append(audio_waveform)
                silence = self.create_silence(self.pause_time, sample_rate, waveform.shape[0])
                output_waveforms.append(silence)
            except Exception as e:
                print(f"加载音频文件出错: {str(e)}")
                continue
            
            # 更新最后处理的索引
            last_index = segment_index
        
        # 处理末尾的<br>标记
        end_br_count = 0
        for silence_pos in silence_positions:
            if silence_pos > last_index:
                end_br_count += 1
                silence = self.create_silence(self.pause_time, sample_rate, waveform.shape[0])
                output_waveforms.append(silence)
        
        if end_br_count > 0:
            print(f"在最后添加了 {end_br_count} 个空行静音")
            
        # 检查是否有波形需要合并
        if not output_waveforms:
            raise ValueError("没有可合并的音频片段")
        
        # 合并所有波形
        merged_waveform = torch.cat(output_waveforms, dim=1)
        
        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # 保存合并后的音频
        torchaudio.save(output_path, merged_waveform, sample_rate)
        
    def save_partial_output(self, temp_outputs, silence_positions, segments) -> Optional[str]:
        """
        尝试保存部分处理结果
        
        Args:
            temp_outputs (list): 临时输出文件列表，格式为[(index, file_path), ...]
            silence_positions (list): 静音位置列表
            segments (list): 文本段落列表
            
        Returns:
            str: 保存的文件路径，如果失败则返回None
        """
        if not temp_outputs:
            return None
            
        self.progress.emit("正在合并已生成的部分内容...")
        try:
            # 创建部分输出路径
            base_filename = os.path.splitext(os.path.basename(self.output_path))[0]
            partial_output_path = os.path.join("outputs", f"{base_filename}_部分.wav")
            
            # 合并已生成的片段
            self.progress.emit(f"正在合并 {len(temp_outputs)} 个已生成的片段...")
            self.merge_audio_files_with_silence(temp_outputs, silence_positions, partial_output_path)
            
            # 清理临时文件
            self.progress.emit("正在清理临时文件...")
            for _, temp_file in temp_outputs:
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                except Exception as e:
                    print(f"删除临时文件时出错: {str(e)}")
                    
            self.progress.emit(f"已成功保存部分结果到: {os.path.basename(partial_output_path)}")
            return partial_output_path
            
        except Exception as e:
            print(f"合并部分结果出错: {str(e)}")
            
            # 如果合并失败，尝试保存最后一个生成的片段
            if temp_outputs:
                try:
                    last_file = temp_outputs[-1][1]
                    partial_output_path = os.path.join(
                        "outputs", f"{os.path.splitext(os.path.basename(self.output_path))[0]}_最后片段.wav"
                    )
                    
                    self.progress.emit("合并失败，尝试保存最后生成的片段...")
                    import shutil
                    if os.path.exists(last_file) and os.path.getsize(last_file) > 0:
                        shutil.copy(last_file, partial_output_path)
                        
                        # 清理临时文件(除了最后一个)
                        self.progress.emit("正在清理临时文件...")
                        for _, temp_file in temp_outputs:
                            if temp_file != last_file:  # 不删除最后一个文件
                                try:
                                    if os.path.exists(temp_file):
                                        os.remove(temp_file)
                                except:
                                    pass
                    
                    self.progress.emit(f"已保存部分结果: {os.path.basename(partial_output_path)}")
                    return partial_output_path
                    
                except Exception as e2:
                    print(f"保存最后一个片段出错: {str(e2)}")
        
        return None
    
    def cleanup_temp_files(self, temp_dir=None):
        """
        清理临时文件和目录
        
        Args:
            temp_dir (str, optional): 要清理的临时目录，如果为None则使用self.temp_dir
        """
        try:
            self.progress.emit("清理临时文件...")
            dir_to_clean = temp_dir or self.temp_dir
            if os.path.exists(dir_to_clean):
                shutil.rmtree(dir_to_clean, ignore_errors=True)
        except Exception as e:
            print(f"清理临时文件时出错: {str(e)}")
            # 不抛出异常，因为这只是清理操作
    
    def create_temp_file_path(self, segment_index=None):
        """
        创建临时文件路径
        
        Args:
            segment_index (int, optional): 段落索引，如果提供则添加到文件名中
            
        Returns:
            str: 临时文件路径
        """
        # 确保临时目录存在
        self.ensure_dir_exists(self.temp_dir)
        
        # 生成文件名
        unique_id = uuid.uuid4().hex[:8]
        timestamp = int(time.time())
        
        if segment_index is not None:
            filename = f"temp_{timestamp}_{unique_id}_{segment_index}.wav"
        else:
            filename = f"temp_{timestamp}_{unique_id}.wav"
            
        return os.path.join(self.temp_dir, filename)
        
    def handle_exception(self, e, context="操作"):
        """
        处理异常并发送错误信号
        
        Args:
            e (Exception): 异常对象
            context (str): 上下文描述，说明发生异常的操作
            
        Returns:
            str: 格式化的错误消息
        """
        error_msg = f"{context}时出错: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        self.error.emit(f"{context}时出错: {str(e)}")
        return error_msg 