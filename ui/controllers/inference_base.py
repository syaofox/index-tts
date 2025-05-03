"""推理工作线程基类
为各种推理工作器提供基础功能和通用方法。
"""

import os
import time
import uuid
import traceback
from typing import List, Tuple, Dict, Optional, Any

import torch
import torchaudio
from PySide6.QtCore import QObject, Signal

from ui.utils.text_processor import TextProcessor


class InferenceBase(QObject):
    """所有推理工作器的基类，提供共用功能"""
    
    # 定义信号
    finished = Signal(str)  # 推理完成信号，返回输出文件路径
    progress = Signal(str)  # 进度信号，发送处理状态信息
    error = Signal(str)     # 错误信号
    
    # 特殊标记
    BR_TAG = "<br>"  # 空行标记
    
    def __init__(self, tts, output_path=None, punct_chars="。？！", pause_time=0.3):
        """
        初始化推理基类
        
        Args:
            tts: TTS模型对象
            output_path: 输出音频路径，如果为None则使用默认路径
            punct_chars: 分割文本的标点符号
            pause_time: 段落间停顿时间(秒)
        """
        super().__init__()
        self.tts = tts
        self.output_path = output_path
        self.punct_chars = punct_chars
        self.pause_time = pause_time
        
        # 停止标志
        self._stop_requested = False
        
        # 创建唯一的临时目录
        self.temp_dir = os.path.join("outputs", "temp", str(uuid.uuid4()))
        self.ensure_dir_exists(self.temp_dir)
    
    def stop(self):
        """请求停止推理过程"""
        self._stop_requested = True
        self.progress.emit("正在停止推理过程...")
    
    def is_stop_requested(self):
        """检查是否请求停止推理"""
        return self._stop_requested
    
    def generate_output_path(self) -> str:
        """
        生成默认输出路径
        
        Returns:
            str: 生成的输出文件路径
        """
        # 创建输出目录（如果不存在）
        output_dir = "outputs"
        self.ensure_dir_exists(output_dir)
        
        # 为输出文件生成一个带时间戳的文件名
        timestamp = time.strftime("%Y%m%d%H%M%S", time.localtime())
        return os.path.join(output_dir, f"output_{timestamp}.wav")
    
    def create_temp_file_path(self, suffix) -> str:
        """
        创建临时文件路径
        
        Args:
            suffix: 文件名后缀
            
        Returns:
            str: 临时文件路径
        """
        # 确保临时目录存在
        self.ensure_dir_exists(self.temp_dir)
        
        # 生成唯一的临时文件名
        file_name = f"temp_{int(time.time())}_{uuid.uuid4().hex[:8]}_{suffix}.wav"
        return os.path.join(self.temp_dir, file_name)
    
    def ensure_dir_exists(self, dir_path):
        """
        确保目录存在，如果不存在则创建
        
        Args:
            dir_path: 目录路径
        """
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
    
    def cleanup_temp_files(self):
        """清理临时文件和目录"""
        try:
            self.progress.emit("清理临时文件...")
            if os.path.exists(self.temp_dir):
                import shutil
                shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception as e:
            print(f"清理临时文件时出错: {str(e)}")
    
    def handle_exception(self, e, context="推理"):
        """
        统一处理异常
        
        Args:
            e: 异常对象
            context: 上下文描述
            
        Returns:
            str: 错误消息
        """
        error_msg = f"{context}时出错: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        self.error.emit(f"{context}失败: {str(e)}")
        return error_msg
    
    def create_silence(self, duration, sample_rate, num_channels=1):
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
        silence = torch.zeros(num_channels, num_samples)
        return silence
    
    def merge_audio_files(self, input_files, output_path):
        """
        合并多个音频文件成一个
        
        Args:
            input_files: 输入音频文件路径列表
            output_path: 输出音频文件路径
            
        Returns:
            str: 合并后的文件路径，如果失败则返回None
        """
        if not input_files:
            return None
        
        try:
            # 如果只有一个文件，直接复制
            if len(input_files) == 1:
                from shutil import copy2
                copy2(input_files[0], output_path)
                return output_path
            
            # 读取第一个文件以获取采样率
            waveform, sample_rate = torchaudio.load(input_files[0])
            
            # 创建一个列表用于存储所有音频片段
            waveforms = []
            
            # 依次读取每个文件并添加到列表
            for file_path in input_files:
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
                    if current_waveform.shape[0] != waveform.shape[0]:
                        if current_waveform.shape[0] < waveform.shape[0]:
                            # 如果声道数少，复制声道
                            current_waveform = current_waveform.repeat(waveform.shape[0], 1)
                        else:
                            # 如果声道数多，只保留需要的声道数
                            current_waveform = current_waveform[:waveform.shape[0], :]
                    
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
            error_msg = f"合并音频文件时出错: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            return None
    
    def merge_audio_files_with_silence(self, temp_outputs, silence_positions, output_path):
        """
        合并多个音频文件，在段落间添加静音
        
        Args:
            temp_outputs: 临时输出文件列表，格式为[(index, file_path), ...]
            silence_positions: 静音位置列表
            output_path: 输出文件路径
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
            for silence_pos in silence_positions:
                if last_index < silence_pos < segment_index:
                    # 为每个<br>添加一个完整静音
                    silence = self.create_silence(self.pause_time, sample_rate, waveform.shape[0])
                    output_waveforms.append(silence)
            
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
            except Exception as e:
                print(f"加载音频文件出错: {str(e)}")
                continue
            
            # 更新最后处理的索引
            last_index = segment_index
        
        # 处理末尾的<br>标记
        for silence_pos in silence_positions:
            if silence_pos > last_index:
                silence = self.create_silence(self.pause_time, sample_rate, waveform.shape[0])
                output_waveforms.append(silence)
        
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
            temp_outputs: 临时输出文件列表，格式为[(index, file_path), ...]
            silence_positions: 静音位置列表
            segments: 文本段落列表
            
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
    
    # 模板方法，定义了整体推理流程，子类需要实现具体推理方法
    def run(self):
        """
        执行推理任务，该方法在单独的线程中运行
        使用模板方法模式，定义整体流程
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
            self.handle_exception(e, "执行推理任务")
    
    def process_inference(self) -> Tuple[bool, Optional[str]]:
        """
        处理推理任务，子类必须实现此方法
        
        Returns:
            tuple: (success, output_file_path)
        """
        raise NotImplementedError("子类必须实现process_inference方法")


# 推理策略类，用于不同的推理模式
class InferenceStrategy:
    """推理策略接口"""
    
    def infer(self, tts, voice_path, text, output_path) -> bool:
        """
        执行推理
        
        Args:
            tts: TTS模型对象
            voice_path: 参考音频路径
            text: 推理文本
            output_path: 输出音频路径
            
        Returns:
            bool: 推理是否成功
        """
        raise NotImplementedError("子类必须实现infer方法")


class NormalInferenceStrategy(InferenceStrategy):
    """普通推理策略"""
    
    def infer(self, tts, voice_path, text, output_path) -> bool:
        """使用普通模式执行推理"""
        try:
            tts.infer(voice_path, text, output_path)
            return os.path.exists(output_path) and os.path.getsize(output_path) > 0
        except Exception as e:
            print(f"普通推理出错: {str(e)}")
            return False


class FastInferenceStrategy(InferenceStrategy):
    """快速推理策略"""
    
    def infer(self, tts, voice_path, text, output_path) -> bool:
        """使用快速模式执行推理"""
        try:
            tts.infer_fast(voice_path, text, output_path)
            return os.path.exists(output_path) and os.path.getsize(output_path) > 0
        except Exception as e:
            print(f"快速推理出错: {str(e)}")
            return False


# 创建策略工厂
class InferenceStrategyFactory:
    """推理策略工厂类"""
    
    @staticmethod
    def create_strategy(mode: str) -> InferenceStrategy:
        """
        创建推理策略
        
        Args:
            mode: 推理模式，"normal"或"fast"
            
        Returns:
            InferenceStrategy: 推理策略对象
        """
        if mode == "fast":
            return FastInferenceStrategy()
        else:
            return NormalInferenceStrategy() 