"""单角色推理模块
提供单一角色的TTS推理功能。
"""

import os
import time
from typing import Tuple, List, Optional

from ui.controllers.inference_base import InferenceBase, InferenceStrategyFactory
from ui.utils.text_processor import TextProcessor


class SingleRoleInference(InferenceBase):
    """单角色推理类，处理单一角色的语音生成"""
    
    def __init__(self, tts, voice_path, text, output_path=None, 
                 punct_chars="。？！", pause_time=0.3, replace_rules=None, infer_mode="normal"):
        """
        初始化单角色推理器
        
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
    
    def process_inference(self) -> Tuple[bool, Optional[str]]:
        """
        处理推理任务
        
        Returns:
            tuple: (success, output_file_path)
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
                self.output_path = self.generate_output_path()
            
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
            error_msg = self.handle_exception(e, "处理推理任务")
            return False, None
    
    def _process_text_in_segments(self, segments: List[str]) -> Tuple[bool, Optional[str]]:
        """
        按段落处理文本
        
        Args:
            segments (list): 文本段落列表
            
        Returns:
            tuple: (success, output_file_path)
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
                    # 处理部分结果
                    partial_result = self.save_partial_output(temp_outputs, silence_positions, segments)
                    if partial_result:
                        return True, partial_result
                    else:
                        return False, None
                
                if segment == self.BR_TAG:  # 处理<br>标记
                    self.progress.emit(f"检测到空行，将在此处添加 {self.pause_time} 秒静音")
                    silence_positions.append(i)
                    continue
                
                if not segment.strip():  # 跳过空片段
                    continue
                    
                # 创建临时输出文件路径
                temp_path = self.create_temp_file_path(segment_index)
                
                self.progress.emit(f"处理第 {segment_index+1}/{len(actual_segments)} 段: {segment[:20]}...")
                
                # 进行推理
                try:
                    # 使用策略模式执行推理
                    if self.strategy.infer(self.tts, self.voice_path, segment, temp_path):
                        temp_outputs.append((i, temp_path))  # 保存原始索引位置和文件路径
                    else:
                        self.progress.emit(f"警告: 段落 {segment_index+1} 未生成有效音频")
                except Exception as segment_error:
                    self.progress.emit(f"处理段落 {segment_index+1} 时出错: {str(segment_error)}")
                
                segment_index += 1
            
            # 检查是否请求停止
            if self.is_stop_requested():
                # 处理部分结果
                partial_result = self.save_partial_output(temp_outputs, silence_positions, segments)
                if partial_result:
                    return True, partial_result
                else:
                    return False, None
            
            # 检查是否有有效输出
            if not temp_outputs:
                self.error.emit("没有生成任何有效的音频片段")
                return False, None
            
            # 合并所有音频片段，包括<br>标记处的静音
            self.progress.emit(f"合并音频片段，添加段落间静音 ({self.pause_time}秒)...")
            self.merge_audio_files_with_silence(temp_outputs, silence_positions, self.output_path)
            
            # 清理临时文件
            self.cleanup_temp_files()
            
            if os.path.exists(self.output_path) and os.path.getsize(self.output_path) > 0:
                return True, self.output_path
            else:
                self.error.emit("合并音频文件失败")
                return False, None
            
        except Exception as e:
            error_msg = self.handle_exception(e, "按段落处理文本")
            return False, None
    
    def _process_single_text(self, text: str) -> Tuple[bool, Optional[str]]:
        """
        处理单个文本片段
        
        Args:
            text (str): 要处理的文本
            
        Returns:
            tuple: (success, output_file_path)
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
            
            # 使用策略模式执行推理
            if self.strategy.infer(self.tts, self.voice_path, text, self.output_path):
                # 最后检查一次是否请求停止
                if self.is_stop_requested():
                    self.progress.emit("已保存生成结果")
                    return True, self.output_path
                
                self.progress.emit("语音生成完成！")
                return True, self.output_path
            else:
                self.error.emit("语音生成失败")
                return False, None
            
        except Exception as e:
            error_msg = self.handle_exception(e, "处理单个文本片段")
            return False, None 