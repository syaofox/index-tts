"""推理工作线程控制器
提供TTS推理的后台处理功能。
"""

import os
import time
from typing import List, Tuple, Dict, Optional, Any

from PySide6.QtCore import QObject, Signal
from ui.controllers.inference_base import InferenceBase
from ui.controllers.multi_role_inference import MultiRoleInference
from ui.models.text_processor import TextProcessor
from ui.models.audio_processor import AudioProcessor
from ui.models.file_manager import FileManager
from ui.models.config_manager import ConfigManager
from ui.config import REPLACE_RULES_CONFIG_PATH


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
            if not FileManager.is_valid_audio_file(self.voice_path):
                self.error.emit(f"参考音频文件不存在或无效: {self.voice_path}")
                return False, None
            
            # 检查文本是否为空
            if not self.text.strip():
                self.error.emit("推理文本不能为空")
                return False, None
            
            # 生成输出路径（如果未提供）
            if not self.output_path:
                self.output_path = FileManager.generate_output_path()
            
            # 确保输出目录存在
            FileManager.ensure_dir_exists(os.path.dirname(self.output_path))
            
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
            # 创建部分输出路径
            partial_output_path = FileManager.get_partial_output_path(self.output_path, "_部分")
            
            self.progress.emit(f"正在合并 {len(temp_outputs)} 个已生成的片段...")
            
            # 使用内存模式合并音频
            merged_wave, sr = AudioProcessor.merge_audio_with_silence(
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
                    # 创建最后片段输出路径
                    last_output_path = FileManager.get_partial_output_path(self.output_path, "_最后片段")
                    
                    self.progress.emit("合并失败，尝试保存最后生成的片段...")
                    AudioProcessor.save_audio_to_file(last_wave, 24000, last_output_path)
                    
                    self.progress.emit(f"已保存部分结果: {os.path.basename(last_output_path)}")
                    self.finished.emit(last_output_path)
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
            merged_wave, sr = AudioProcessor.merge_audio_with_silence(
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