"""单角色推理工作器模块
提供单一角色的TTS推理功能。
"""

import os
import time
import uuid
import traceback
from typing import Tuple, List, Optional

import torch
import torchaudio

from ui.controllers.inference_base import InferenceBase
from ui.utils.text_processor import TextProcessor
from ui.config import REPLACE_RULES_CONFIG_PATH


class SingleRoleInferenceWorker(InferenceBase):
    """单角色推理工作器类，处理单一角色的语音生成"""
    
    def __init__(self, tts, voice_path, text, output_path=None, 
                 punct_chars="。？！", pause_time=0.3, replace_rules=None):
        """
        初始化单角色推理工作器
        
        Args:
            tts: TTS模型对象
            voice_path: 参考音频路径
            text: 推理文本
            output_path: 输出音频路径，如果为None则使用默认路径
            punct_chars: 分割文本的标点符号
            pause_time: 停顿时间(秒)
            replace_rules: 文本替换规则列表
        """
        super().__init__(tts, output_path, punct_chars, pause_time)
        self.voice_path = voice_path
        self.text = text
        self.replace_rules = replace_rules or []
        
        # 创建临时目录
        self.temp_dir = os.path.join("outputs", "temp")
        self.ensure_dir_exists(self.temp_dir)
        
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
            
            # 预处理文本
            self.progress.emit("正在预处理文本...")
            segments = TextProcessor.preprocess_text(
                self.text, self.punct_chars, self.replace_rules
            )
            
            # 根据段落数量决定处理方式
            if len(segments) > 1:
                return self.process_text_in_segments(segments)
            else:
                # 作为单个文本处理
                self.progress.emit("文本将作为整体处理...")
                return self.process_single_text(self.text)
            
        except Exception as e:
            error_msg = f"处理推理任务时出错: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            self.error.emit(error_msg)
            return False, None
    
    def process_text_in_segments(self, segments: List[str]) -> Tuple[bool, Optional[str]]:
        """
        按段落处理文本
        
        Args:
            segments (list): 文本段落列表
            
        Returns:
            tuple: (success, output_file_path)
        """
        try:
            # 确保临时目录存在
            if not self.temp_dir or not os.path.exists(self.temp_dir):
                self.temp_dir = os.path.join("outputs", "temp")
                self.ensure_dir_exists(self.temp_dir)
            
            # 计算实际处理的片段数（不包括<br>标记）
            actual_segments = [s for s in segments if s != TextProcessor.BR_TAG and s.strip()]
            
            self.progress.emit(f"共分为 {len(actual_segments)} 个片段进行处理...")
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
                
                if segment == TextProcessor.BR_TAG:  # 处理<br>标记
                    self.progress.emit(f"检测到空行，将在此处添加 {self.pause_time} 秒静音")
                    silence_positions.append(i)
                    continue
                
                if not segment.strip():  # 跳过空片段
                    continue
                    
                # 创建临时输出文件路径（使用时间戳和UUID确保唯一）
                temp_file_name = f"temp_{int(time.time())}_{uuid.uuid4().hex[:8]}_{segment_index}.wav"
                temp_path = os.path.join(self.temp_dir, temp_file_name)
                
                self.progress.emit(f"处理第 {segment_index+1}/{len(actual_segments)} 段: {segment[:20]}...")
                
                # 进行推理
                try:
                    self.tts.infer(self.voice_path, segment, temp_path)
                    if os.path.exists(temp_path) and os.path.getsize(temp_path) > 0:
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
            self.progress.emit("清理临时文件...")
            for _, temp_file in temp_outputs:
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                except Exception as e:
                    print(f"删除临时文件时出错: {str(e)}")
            
            if os.path.exists(self.output_path) and os.path.getsize(self.output_path) > 0:
                return True, self.output_path
            else:
                self.error.emit("合并音频文件失败")
                return False, None
            
        except Exception as e:
            error_msg = f"按段落处理文本时出错: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            self.error.emit(error_msg)
            return False, None
    
    def process_single_text(self, text: str) -> Tuple[bool, Optional[str]]:
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
            
            self.progress.emit("开始语音生成...")
            
            # 应用文本替换规则（如果有）
            if self.replace_rules:
                text = TextProcessor.apply_replace_rules(text, self.replace_rules)
            
            # 执行推理
            self.tts.infer(self.voice_path, text, self.output_path)
            
            # 最后检查一次是否请求停止
            if self.is_stop_requested():
                # 检查输出文件是否已经存在且有效
                if os.path.exists(self.output_path) and os.path.getsize(self.output_path) > 0:
                    self.progress.emit("已保存生成结果")
                    return True, self.output_path
                else:
                    self.error.emit("推理已被用户中断")
                    return False, None
            
            self.progress.emit("语音生成完成！")
            return True, self.output_path
            
        except Exception as e:
            error_msg = f"处理单个文本片段时出错: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            self.error.emit(error_msg)
            return False, None
            
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
        
    def merge_audio_files_with_silence(self, temp_outputs, silence_positions, output_path):
        """
        合并多个音频文件，在段落间添加静音
        
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