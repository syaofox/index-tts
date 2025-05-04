"""推理控制器基类
为各种推理控制器提供基础功能和通用方法。
"""

import os
import traceback
from typing import List, Tuple, Dict, Optional, Any

from PySide6.QtCore import QObject, Signal

from ui.models.file_manager import FileManager
from ui.models.audio_processor import AudioProcessor
from ui.models.text_processor import TextProcessor


class InferenceBase(QObject):
    """所有推理控制器的基类，提供共用功能"""
    
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
        
        # 创建唯一的临时ID
        self.temp_id = FileManager.generate_temp_id()
        
        # 内存缓存变量
        self.in_memory_mode = True  # 默认使用内存模式
    
    def stop(self):
        """请求停止推理过程"""
        self._stop_requested = True
        self.progress.emit("正在停止推理过程...")
    
    def is_stop_requested(self):
        """检查是否请求停止推理"""
        return self._stop_requested
    
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
    
    def save_partial_output(self, temp_outputs, silence_positions, segments) -> Optional[str]:
        """
        尝试保存部分处理结果
        
        Args:
            temp_outputs: 临时输出列表，格式为[(index, wave_data), ...]
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
            if not self.output_path:
                self.output_path = FileManager.generate_output_path("output")
                
            partial_output_path = FileManager.get_partial_output_path(self.output_path, "_部分")
            
            # 合并已生成的片段
            self.progress.emit(f"正在合并 {len(temp_outputs)} 个已生成的片段...")
            
            # 内存模式 - 合并波形数据
            merged_wave, sample_rate = AudioProcessor.merge_audio_with_silence(
                temp_outputs, silence_positions, self.pause_time, 24000
            )
            
            if merged_wave is not None and sample_rate is not None:
                # 保存合并后的音频
                output_file = AudioProcessor.save_audio_to_file(merged_wave, sample_rate, partial_output_path)
                
                if output_file and os.path.exists(output_file):
                    self.progress.emit(f"已成功保存部分结果到: {os.path.basename(partial_output_path)}")
                    return partial_output_path
            else:
                self.progress.emit("合并音频失败，尝试保存最后一个片段...")
            
            # 如果合并失败，尝试保存最后一个片段
            if temp_outputs:
                try:
                    # 获取最后一个片段
                    last_output_path = FileManager.get_partial_output_path(self.output_path, "_最后片段")
                    
                    self.progress.emit("合并失败，尝试保存最后生成的片段...")
                    
                    # 获取最后一个片段
                    _, last_wave = temp_outputs[-1]
                    
                    # 保存最后一个片段
                    last_file = AudioProcessor.save_audio_to_file(last_wave, 24000, last_output_path)
                    
                    if last_file and os.path.exists(last_file):
                        self.progress.emit(f"已保存部分结果: {os.path.basename(last_output_path)}")
                        return last_output_path
                        
                except Exception as e2:
                    print(f"保存最后一个片段出错: {str(e2)}")
        
        except Exception as e:
            print(f"合并部分结果出错: {str(e)}")
            traceback.print_exc()
            
        return None
    
    # 模板方法，定义了整体推理流程，子类需要实现具体推理方法
    def run(self):
        """
        执行推理任务，该方法在单独的线程中运行
        使用模板方法模式，定义整体流程
        """
        try:
            success, result = self.process_inference()
            
            if success:
                # 检查返回值类型
                if isinstance(result, tuple) and len(result) == 2:
                    # 内存模式返回的是 (sample_rate, wave_data)
                    sample_rate, wave_data = result
                    
                    # 生成输出路径（如果未提供）
                    if not self.output_path:
                        self.output_path = FileManager.generate_output_path("output")
                    
                    # 保存到文件
                    self.progress.emit("正在保存最终音频文件...")
                    output_file = AudioProcessor.save_audio_to_file(wave_data, sample_rate, self.output_path)
                    
                    if output_file and os.path.exists(output_file):
                        self.progress.emit("音频保存完成！")
                        self.finished.emit(output_file)
                    else:
                        self.error.emit("保存音频文件失败")
                elif isinstance(result, str) and os.path.exists(result):
                    # 兼容旧代码，直接返回文件路径
                    self.finished.emit(result)
                else:
                    self.error.emit("推理结果格式不正确")
            else:
                if self.is_stop_requested():
                    self.error.emit("推理已被用户中断")
                else:
                    self.error.emit("语音生成失败")
                
        except Exception as e:
            self.handle_exception(e, "执行推理任务")
    
    def process_inference(self) -> Tuple[bool, Optional[Tuple]]:
        """
        处理推理任务，子类必须实现此方法
        
        Returns:
            tuple: (success, (sample_rate, wave_data))
        """
        raise NotImplementedError("子类必须实现process_inference方法")


# 推理策略类，用于不同的推理模式
class InferenceStrategy:
    """推理策略接口"""
    
    def infer(self, tts, voice_path, text, output_path=None):
        """
        执行推理
        
        Args:
            tts: TTS模型对象
            voice_path: 参考音频路径
            text: 推理文本
            output_path: 输出音频路径，如果为None则返回波形数据
            
        Returns:
            bool 或 (波形, 采样率): 推理是否成功，或者波形数据和采样率
        """
        raise NotImplementedError("子类必须实现infer方法")


class NormalInferenceStrategy(InferenceStrategy):
    """普通推理策略"""
    
    def infer(self, tts, voice_path, text, output_path=None):
        """使用普通模式执行推理"""
        try:
            result = tts.infer(voice_path, text, output_path)
            if output_path is None:
                # 内存模式，返回波形数据和采样率
                return result  # (采样率, 波形数据)
            else:
                # 文件模式，返回是否成功
                return os.path.exists(output_path) and os.path.getsize(output_path) > 0
        except Exception as e:
            print(f"普通推理出错: {str(e)}")
            return False if output_path else (None, None)


class FastInferenceStrategy(InferenceStrategy):
    """快速推理策略"""
    
    def infer(self, tts, voice_path, text, output_path=None):
        """使用快速模式执行推理"""
        try:
            result = tts.infer_fast(voice_path, text, output_path)
            if output_path is None:
                # 内存模式，返回波形数据和采样率
                return result  # (采样率, 波形数据)
            else:
                # 文件模式，返回是否成功
                return os.path.exists(output_path) and os.path.getsize(output_path) > 0
        except Exception as e:
            print(f"快速推理出错: {str(e)}")
            return False if output_path else (None, None)


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