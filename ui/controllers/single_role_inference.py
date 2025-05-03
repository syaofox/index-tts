"""单角色推理控制器
提供单一角色的TTS推理流程控制。
"""

import os
from typing import Tuple, List, Optional

from PySide6.QtCore import QObject, Signal

from ui.controllers.inference_base import InferenceBase
from ui.models.audio_processor import AudioProcessor
from ui.models.file_manager import FileManager
from ui.models.text_processor import TextProcessor
from ui.models.inference_strategy import InferenceStrategyFactory


class SingleRoleInference(InferenceBase):
    """单角色推理控制器，处理单一角色的语音生成流程"""
    
    def __init__(self, tts, voice_path, text, output_path=None, 
                 punct_chars="。？！", pause_time=0.3, replace_rules=None, infer_mode="normal"):
        """
        初始化单角色推理控制器
        
        Args:
            tts: TTS模型对象
            voice_path: 参考音频路径
            text: 推理文本
            output_path: 输出音频路径，如果为None则使用默认路径
            punct_chars: 分割文本的标点符号
            pause_time: 停顿时间(秒)
            replace_rules: 文本替换规则列表
            infer_mode: 推理模式，"normal"或"fast"
        """
        super().__init__(tts, output_path, punct_chars, pause_time)
        self.voice_path = voice_path
        self.text = text
        self.replace_rules = replace_rules or []
        # 创建推理策略
        self.strategy = InferenceStrategyFactory.create_strategy(infer_mode)
        self.infer_mode = infer_mode
    
    def process_inference(self) -> Tuple[bool, Optional[Tuple]]:
        """
        处理推理任务
        
        Returns:
            tuple: (success, (sample_rate, wave_data))
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
            
            # 预处理文本
            self.progress.emit("正在预处理文本...")
            segments = TextProcessor.preprocess_text(
                self.text, self.punct_chars, self.replace_rules
            )
            
            # 根据段落数量决定处理方式
            if len(segments) > 1:
                return self._process_text_in_segments(segments)
            else:
                # 作为单个文本处理
                self.progress.emit("文本将作为整体处理...")
                return self._process_single_text(self.text)
            
        except Exception as e:
            import traceback
            error_msg = f"处理推理任务时出错: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            self.error.emit(error_msg)
            return False, None
    
    def _process_text_in_segments(self, segments: List[str]) -> Tuple[bool, Optional[Tuple]]:
        """
        按段落处理文本
        
        Args:
            segments (list): 文本段落列表
            
        Returns:
            tuple: (success, (sample_rate, wave_data))
        """
        try:
            # 计算实际处理的片段数（不包括<br>标记）
            actual_segments = [s for s in segments if s != self.BR_TAG and s.strip()]
            
            self.progress.emit(f"共分为 {len(actual_segments)} 个片段进行处理...({self.infer_mode}模式)")
            temp_outputs = []
            silence_positions = []  # 记录需要添加静音的位置
            
            segment_index = 0
            for i, segment in enumerate(segments):
                # 检查是否请求停止
                if self.is_stop_requested():
                    self.error.emit("推理已被用户中断")
                    return False, None
                
                if segment == self.BR_TAG:  # 处理<br>标记
                    self.progress.emit(f"检测到空行，将在此处添加 {self.pause_time} 秒静音")
                    silence_positions.append(i)
                    continue
                
                if not segment.strip():  # 跳过空片段
                    continue
                
                self.progress.emit(f"处理第 {segment_index+1}/{len(actual_segments)} 段: {segment[:20]}...")
                
                # 进行推理
                try:
                    # 使用内存模式调用推理策略
                    result = self.strategy.infer(self.tts, self.voice_path, segment, None)
                    if isinstance(result, tuple) and len(result) == 2:
                        # 成功获取内存数据
                        sample_rate, wave_data = result
                        if sample_rate is not None and wave_data is not None:
                            # 添加到临时输出列表
                            temp_outputs.append((i, wave_data))
                        else:
                            self.progress.emit(f"警告: 段落 {segment_index+1} 未生成有效音频")
                    else:
                        self.progress.emit(f"警告: 段落 {segment_index+1} 的推理返回格式不正确")
                except Exception as segment_error:
                    import traceback
                    error_msg = f"处理段落 {segment_index+1} 时出错: {str(segment_error)}\n{traceback.format_exc()}"
                    self.progress.emit(error_msg)
                
                segment_index += 1
            
            # 检查是否请求停止
            if self.is_stop_requested():
                self.error.emit("推理已被用户中断")
                return False, None
            
            # 检查是否有有效输出
            if not temp_outputs:
                self.error.emit("没有生成任何有效的音频片段")
                return False, None
            
            # 合并所有音频片段，包括<br>标记处的静音
            self.progress.emit(f"合并音频片段，添加段落间静音 ({self.pause_time}秒)...")
            
            # 使用内存模式合并音频
            sample_rate = 24000  # 假设使用默认采样率
            merged_wave, sr = AudioProcessor.merge_audio_with_silence(
                temp_outputs, silence_positions, self.pause_time, sample_rate
            )
            
            if merged_wave is None:
                self.error.emit("合并音频数据失败")
                return False, None

            # 返回内存音频数据
            self.progress.emit("音频数据合并完成，返回内存数据")
            return True, (sr, merged_wave)
            
        except Exception as e:
            import traceback
            error_msg = f"按段落处理文本时出错: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            self.error.emit(error_msg)
            return False, None
    
    def _process_single_text(self, text: str) -> Tuple[bool, Optional[Tuple]]:
        """
        处理单个文本片段
        
        Args:
            text (str): 要处理的文本
            
        Returns:
            tuple: (success, (sample_rate, wave_data))
        """
        try:
            # 检查是否请求停止
            if self.is_stop_requested():
                self.error.emit("推理已被用户中断")
                return False, None
            
            self.progress.emit(f"开始语音生成...({self.infer_mode}模式)")
            
            # 应用文本替换规则（如果有）
            if self.replace_rules:
                text = TextProcessor.apply_replace_rules(text, self.replace_rules)
            
            # 使用内存模式进行推理
            result = self.strategy.infer(self.tts, self.voice_path, text, None)
            
            if isinstance(result, tuple) and len(result) == 2:
                # 成功获取内存数据
                sample_rate, wave_data = result
                if sample_rate is not None and wave_data is not None:
                    # 内存模式，直接返回数据
                    self.progress.emit("音频生成完成，返回内存数据")
                    return True, (sample_rate, wave_data)
                else:
                    self.error.emit("推理未返回有效的音频数据")
                    return False, None
            else:
                self.error.emit("推理返回格式不正确")
                return False, None
            
        except Exception as e:
            import traceback
            error_msg = f"处理单个文本片段时出错: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            self.error.emit(error_msg)
            return False, None 