"""推理处理器模型
提供文本推理处理的业务逻辑，包括分段处理、单文本处理等。
"""

import os
from typing import List, Tuple, Dict, Optional, Any, Callable

from ui.models.audio_processor import AudioProcessor
from ui.models.text_processor import TextProcessor
from ui.models.file_manager import FileManager


class InferenceProcessor:
    """推理处理器类
    负责处理文本推理的业务逻辑，包括分段处理、单文本处理等
    """
    
    # 特殊标记
    BR_TAG = "<br>"  # 空行标记
    
    @staticmethod
    def process_text_in_segments(
            tts, voice_path, segments, output_path, 
            pause_time=0.3, replace_rules=None,
            progress_callback=None, stop_check_callback=None):
        """
        按段落处理文本
        
        Args:
            tts: TTS模型对象
            voice_path: 参考音频路径
            segments: 文本段落列表
            output_path: 输出文件路径
            pause_time: 段落间停顿时间(秒)
            replace_rules: 文本替换规则
            progress_callback: 进度回调函数，接收字符串参数
            stop_check_callback: 停止检查回调函数，返回布尔值
            
        Returns:
            tuple: (success, output_file_path) 或 (success, (sample_rate, wave_data))
        """
        # 默认空回调函数
        if progress_callback is None:
            progress_callback = lambda msg: None
        if stop_check_callback is None:
            stop_check_callback = lambda: False
            
        try:
            # 处理进度回调
            progress_callback(f"共分为 {len(segments)} 个片段进行处理...")
            
            # 用于存储音频输出和静音位置
            temp_outputs = []
            silence_positions = []  # 记录需要添加静音的位置
            
            segment_index = 0
            for i, segment in enumerate(segments):
                # 检查是否请求停止
                if stop_check_callback():
                    # 尝试保存部分结果
                    if output_path:
                        return InferenceProcessor.save_partial_output(
                            temp_outputs, silence_positions, segments, output_path, 
                            pause_time, progress_callback
                        )
                    
                    # 在内存模式下无法停止，返回失败
                    return False, None
                
                if segment == InferenceProcessor.BR_TAG:  # 处理<br>标记
                    silence_positions.append(i)
                    continue
                
                if not segment.strip():  # 跳过空片段
                    continue
                
                progress_callback(f"处理第 {segment_index+1}/{len(segments) - len(silence_positions)} 段...")
                
                # 使用内存模式进行推理
                result = tts.infer(voice_path, segment, None)
                
                if isinstance(result, tuple) and len(result) == 2:
                    # 返回的是内存数据格式 (采样率, 波形数据)
                    sample_rate, wave_data = result
                    
                    # 添加到临时输出列表
                    temp_outputs.append((i, wave_data))
                else:
                    progress_callback(f"警告: 段落 {segment_index+1} 推理结果格式不正确")
                
                segment_index += 1
            
            # 最后检查是否请求停止
            if stop_check_callback():
                # 尝试保存部分结果
                if output_path:
                    return InferenceProcessor.save_partial_output(
                        temp_outputs, silence_positions, segments, output_path,
                        pause_time, progress_callback
                    )
                
                # 在内存模式下无法停止，返回失败
                return False, None
            
            # 检查是否有有效输出
            if not temp_outputs:
                return False, None
            
            # 合并所有音频片段，包括<br>标记处的静音
            progress_callback(f"合并音频片段，添加段落间静音 ({pause_time}秒)...")
            
            # 使用内存模式合并音频
            merged_wave, sr = AudioProcessor.merge_audio_with_silence(
                temp_outputs, silence_positions, pause_time, 24000
            )
            
            if merged_wave is None:
                return False, None
            
            # 如果提供了输出路径，保存到文件并返回文件路径
            if output_path:
                # 保存最终输出
                progress_callback("正在保存最终音频文件...")
                output_file = AudioProcessor.save_audio_to_file(merged_wave, sr, output_path)
                
                if output_file and os.path.exists(output_file):
                    return True, output_file
                else:
                    return False, None
            else:
                # 如果没有输出路径，返回内存数据
                return True, (sr, merged_wave)
            
        except Exception as e:
            import traceback
            error_msg = f"按段落处理文本时出错: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            return False, None
    
    @staticmethod
    def process_single_text(
            tts, voice_path, text, output_path=None, 
            replace_rules=None, progress_callback=None, stop_check_callback=None):
        """
        处理单个文本片段
        
        Args:
            tts: TTS模型对象
            voice_path: 参考音频路径
            text: 文本内容
            output_path: 输出文件路径，如果为None则返回内存数据
            replace_rules: 文本替换规则
            progress_callback: 进度回调函数，接收字符串参数
            stop_check_callback: 停止检查回调函数，返回布尔值
            
        Returns:
            tuple: (success, output_file_path) 或 (success, (sample_rate, wave_data))
        """
        # 默认空回调函数
        if progress_callback is None:
            progress_callback = lambda msg: None
        if stop_check_callback is None:
            stop_check_callback = lambda: False
            
        try:
            # 检查是否请求停止
            if stop_check_callback():
                return False, None
            
            progress_callback("开始语音生成...")
            
            # 应用文本替换规则（如果有）
            if replace_rules:
                text = TextProcessor.apply_replace_rules(text, replace_rules)
            
            # 使用内存模式进行推理
            result = tts.infer(voice_path, text, None)
            
            # 最后检查一次是否请求停止
            if stop_check_callback():
                # 仍然继续保存结果
                progress_callback("推理已完成，正在保存...")
            
            if isinstance(result, tuple) and len(result) == 2:
                # 返回的是内存数据格式 (采样率, 波形数据)
                sample_rate, wave_data = result
                
                # 如果需要保存到文件
                if output_path:
                    # 保存到文件
                    progress_callback("正在保存音频文件...")
                    output_file = AudioProcessor.save_audio_to_file(wave_data, sample_rate, output_path)
                    
                    if output_file and os.path.exists(output_file):
                        progress_callback("语音生成完成！")
                        return True, output_file
                    else:
                        return False, None
                else:
                    # 返回内存数据
                    progress_callback("音频生成完成，返回内存数据")
                    return True, (sample_rate, wave_data)
            else:
                return False, None
            
        except Exception as e:
            import traceback
            error_msg = f"处理单个文本片段时出错: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            return False, None
    
    @staticmethod
    def save_partial_output(temp_outputs, silence_positions, segments, output_path, 
                            pause_time=0.3, progress_callback=None):
        """
        保存部分处理结果
        
        Args:
            temp_outputs: 临时输出列表 [(index, wave_data), ...]
            silence_positions: 静音位置列表
            segments: 文本段落列表
            output_path: 输出文件路径
            pause_time: 段落间停顿时间(秒)
            progress_callback: 进度回调函数
            
        Returns:
            tuple: (success, output_file_path)
        """
        if progress_callback is None:
            progress_callback = lambda msg: None
            
        if not temp_outputs:
            return False, None
            
        progress_callback("正在合并已生成的部分内容...")
        try:
            # 创建部分输出路径
            partial_output_path = FileManager.get_partial_output_path(output_path, "_部分")
            
            progress_callback(f"正在合并 {len(temp_outputs)} 个已生成的片段...")
            
            # 使用内存模式合并音频
            merged_wave, sr = AudioProcessor.merge_audio_with_silence(
                temp_outputs, silence_positions, pause_time, 24000
            )
            
            # 保存合并后的音频
            output_file = AudioProcessor.save_audio_to_file(merged_wave, sr, partial_output_path)
            
            if output_file and os.path.exists(output_file):
                progress_callback(f"已成功保存部分结果到: {os.path.basename(partial_output_path)}")
                return True, output_file
            else:
                # 如果合并失败，尝试保存最后一个片段
                last_output_path = FileManager.get_partial_output_path(output_path, "_最后片段")
                
                progress_callback("合并失败，尝试保存最后生成的片段...")
                
                # 获取最后一个片段
                _, last_wave = temp_outputs[-1]
                
                # 保存最后一个片段
                last_file = AudioProcessor.save_audio_to_file(last_wave, 24000, last_output_path)
                
                if last_file and os.path.exists(last_file):
                    progress_callback(f"已保存部分结果: {os.path.basename(last_output_path)}")
                    return True, last_file
                
                return False, None
                
        except Exception as e:
            import traceback
            error_msg = f"保存部分结果时出错: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            return False, None
    
    @staticmethod
    def preprocess_and_infer(tts, voice_path, text, output_path=None, 
                             punct_chars="。？！", pause_time=0.3, replace_rules=None,
                             progress_callback=None, stop_check_callback=None):
        """
        预处理文本并执行推理
        
        Args:
            tts: TTS模型对象
            voice_path: 参考音频路径
            text: 文本内容
            output_path: 输出文件路径
            punct_chars: 分割文本的标点符号
            pause_time: 段落间停顿时间
            replace_rules: 文本替换规则
            progress_callback: 进度回调函数
            stop_check_callback: 停止检查回调函数
        
        Returns:
            tuple: (success, output_file_path) 或 (success, (sample_rate, wave_data))
        """
        # 默认空回调函数
        if progress_callback is None:
            progress_callback = lambda msg: None
        if stop_check_callback is None:
            stop_check_callback = lambda: False
            
        try:
            # 检查参考音频是否存在
            if not FileManager.is_valid_audio_file(voice_path):
                return False, None
            
            # 检查文本是否为空
            if not text.strip():
                return False, None
            
            # 确保输出目录存在（如果提供了输出路径）
            if output_path:
                FileManager.ensure_dir_exists(os.path.dirname(output_path))
            
            # 预处理文本
            progress_callback("正在预处理文本...")
            preprocessed_segments = TextProcessor.preprocess_text(
                text, punct_chars, replace_rules
            )
            
            # 根据段落数量决定处理方式
            if len(preprocessed_segments) > 1:
                return InferenceProcessor.process_text_in_segments(
                    tts, voice_path, preprocessed_segments, output_path,
                    pause_time, replace_rules, progress_callback, stop_check_callback
                )
            else:
                # 作为单个文本处理
                progress_callback("文本将作为整体处理...")
                return InferenceProcessor.process_single_text(
                    tts, voice_path, text, output_path,
                    replace_rules, progress_callback, stop_check_callback
                )
            
        except Exception as e:
            import traceback
            error_msg = f"预处理并推理时出错: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            return False, None 