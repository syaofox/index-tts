"""推理工作线程控制器
提供TTS推理的后台处理功能。
"""

import os
import time
import re

from PySide6.QtCore import QObject, Signal
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
    
    # 类级别的配置缓存
    _replace_rules_cache = []  # 缓存的替换规则
    _config_last_modified = 0  # 配置文件最后修改时间

    def __init__(self, tts, voice_path, text, output_path=None, 
                 punct_chars="。？！", pause_time=0.3):
        super().__init__()
        self.tts = tts
        self.voice_path = voice_path
        self.text = text
        self.output_path = output_path
        self.punct_chars = punct_chars    # 分割标点符号
        self.pause_time = pause_time      # 段落间停顿时间（秒）
        self.replace_rules = []           # 文本替换规则列表
        self._stop_requested = False      # 停止标志
        
        # 检查配置文件并加载（如果需要）
        self.check_and_load_config()

    def check_and_load_config(self):
        """检查配置文件是否存在并且需要重新加载"""
        if not os.path.exists(self.REPLACE_CONFIG_PATH):
            self.replace_rules = []
            return
            
        # 获取文件最后修改时间
        current_mtime = os.path.getmtime(self.REPLACE_CONFIG_PATH)
        
        # 检查是否需要重新加载
        if current_mtime > InferenceWorker._config_last_modified or not InferenceWorker._replace_rules_cache:
            self.load_text_replace_config()
            # 更新类级别的缓存
            InferenceWorker._replace_rules_cache = self.replace_rules.copy()
            InferenceWorker._config_last_modified = current_mtime
            print(f"配置文件已更新，重新加载 {len(self.replace_rules)} 条规则")
        else:
            # 使用缓存的规则
            self.replace_rules = InferenceWorker._replace_rules_cache.copy()
            print(f"使用缓存的 {len(self.replace_rules)} 条替换规则")

    def load_text_replace_config(self):
        """加载文本替换配置文件"""
        try:
            self.replace_rules = []
            with open(self.REPLACE_CONFIG_PATH, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    # 跳过空行和注释行
                    if not line or line.startswith('#'):
                        continue
                    
                    parts = line.split('|')  # 使用竖线分隔
                    if len(parts) == 3:
                        search_str, replace_from, replace_to = parts
                        self.replace_rules.append((search_str, replace_from, replace_to))
                    else:
                        print(f"警告：配置行格式不正确，已跳过: {line}")
            
            if self.replace_rules:
                print(f"已加载 {len(self.replace_rules)} 条文本替换规则")
        except Exception as e:
            print(f"加载文本替换配置文件出错: {str(e)}")
            self.error.emit(f"加载文本替换配置文件出错: {str(e)}")

    def replace_text_by_config(self, text):
        """根据配置规则替换文本"""
        if not self.replace_rules:
            return text
            
        result_text = text
        for search_str, replace_from, replace_to in self.replace_rules:
            # 在搜索字符串中查找需要修改的部分并替换
            if search_str in result_text:
                # 创建一个新字符串，将搜索字符串中的替换源替换为替换目标
                modified_search_str = search_str.replace(replace_from, replace_to)
                # 替换原文本中的搜索字符串为修改后的字符串
                result_text = result_text.replace(search_str, modified_search_str)
        
        return result_text

    def stop(self):
        """请求停止推理过程"""
        self._stop_requested = True
        self.progress.emit("正在停止推理过程...")
    
    def save_partial_output(self, temp_outputs, silence_positions, preprocessed_segments):
        """尝试保存部分处理结果，成功则返回True，失败返回False"""
        if not temp_outputs:
            return False
            
        self.progress.emit("正在合并已生成的部分内容...")
        try:
            # 获取基础文件名（如果有）
            base_output_path = self.output_path
            base_filename = os.path.splitext(os.path.basename(base_output_path))[0]
            # 添加部分输出标记，保持文件名格式一致
            partial_output_path = os.path.join("outputs", f"{base_filename}_部分.wav")
            
            self.progress.emit(f"正在合并 {len(temp_outputs)} 个已生成的片段...")
            self.merge_audio_files_with_br(temp_outputs, silence_positions, preprocessed_segments, partial_output_path)
            
            # 清理临时文件
            self.progress.emit("正在清理临时文件...")
            for _, temp_file in temp_outputs:
                try:
                    os.remove(temp_file)
                except:
                    pass
                    
            self.progress.emit(f"已成功保存部分结果到: {os.path.basename(partial_output_path)}")
            self.finished.emit(partial_output_path)
            return True
        except Exception as e:
            print(f"合并部分结果出错: {str(e)}")
            # 如果合并失败，仍然尝试保留最后一个生成的片段
            if temp_outputs:
                last_file = temp_outputs[-1][1]
                # 获取基础文件名（如果有）
                base_output_path = self.output_path
                base_filename = os.path.splitext(os.path.basename(base_output_path))[0]
                # 添加部分输出标记，保持文件名格式一致
                partial_output_path = os.path.join("outputs", f"{base_filename}_最后片段.wav")
                
                try:
                    self.progress.emit("合并失败，尝试保存最后生成的片段...")
                    import shutil
                    shutil.copy(last_file, partial_output_path)
                    
                    # 清理临时文件(除了最后一个)
                    self.progress.emit("正在清理临时文件...")
                    for _, temp_file in temp_outputs:
                        if temp_file != last_file:  # 不删除最后一个文件
                            try:
                                os.remove(temp_file)
                            except:
                                pass
                    
                    self.progress.emit(f"已保存部分结果: {os.path.basename(partial_output_path)}")
                    self.finished.emit(partial_output_path)
                    return True
                except Exception as e2:
                    print(f"保存最后一个片段出错: {str(e2)}")
        
        return False

    def run(self):
        try:
            # 确保输出路径已设置
            if not self.output_path:
                # 如果未设置输出路径，使用默认格式（使用当前时间戳）
                self.output_path = os.path.join("outputs", f"未命名_{int(time.time())}.wav")
            
            # 预处理文本
            self.progress.emit("预处理文本...")
            preprocessed_segments = self.preprocess_text(self.text)

            print(preprocessed_segments)
            
            # 检查是否请求停止
            if self._stop_requested:
                self.error.emit("推理已被用户中断")
                return
            
            if len(preprocessed_segments) > 1:
                self.progress.emit(f"共分为 {len(preprocessed_segments)} 个片段进行处理...")
                temp_outputs = []
                silence_positions = []  # 记录需要添加静音的位置
                
                segment_index = 0
                for i, segment in enumerate(preprocessed_segments):
                    # 检查是否请求停止
                    if self._stop_requested:
                        # 尝试保存部分结果
                        if self.save_partial_output(temp_outputs, silence_positions, preprocessed_segments):
                            return
                        
                        # 如果无法保存部分结果，则报告中断
                        self.error.emit("推理已被用户中断")
                        return
                    
                    if segment == self.BR_TAG:  # 处理<br>标记
                        silence_positions.append(i)
                        continue
                    
                    if not segment.strip():  # 跳过空片段
                        continue
                        
                    temp_path = os.path.join("outputs", f"temp_{int(time.time())}_{segment_index}.wav")
                    self.progress.emit(f"处理第 {segment_index+1}/{len(preprocessed_segments) - len(silence_positions)} 段...")
                    self.tts.infer(self.voice_path, segment, temp_path)
                    temp_outputs.append((i, temp_path))  # 保存原始索引位置和文件路径
                    segment_index += 1
                
                # 检查是否请求停止
                if self._stop_requested:
                    # 尝试保存部分结果
                    if self.save_partial_output(temp_outputs, silence_positions, preprocessed_segments):
                        return
                    
                    # 如果无法保存部分结果，则报告中断
                    self.error.emit("推理已被用户中断")
                    return
                
                # 合并所有音频片段，包括<br>标记处的静音
                self.progress.emit(f"合并音频片段，添加段落间静音 ({self.pause_time}秒)...")
                self.merge_audio_files_with_br(temp_outputs, silence_positions, preprocessed_segments, self.output_path)
                
                # 清理临时文件
                for _, temp_file in temp_outputs:
                    try:
                        os.remove(temp_file)
                    except:
                        pass
            else:
                # 检查是否请求停止
                if self._stop_requested:
                    self.error.emit("推理已被用户中断")
                    return
                
                self.progress.emit("开始语音生成...")
                # 如果只有一个片段且不是<br>标记，直接处理
                if preprocessed_segments and preprocessed_segments[0] != self.BR_TAG:
                    self.tts.infer(self.voice_path, preprocessed_segments[0], self.output_path)
                else:
                    # 如果是<br>标记或没有内容，创建静音文件
                    import torchaudio
                    silence = self.create_silence(self.pause_time, 44100)  # 使用默认采样率
                    torchaudio.save(self.output_path, silence, 44100)
            
            # 最后检查一次是否请求停止
            if self._stop_requested:
                # 检查输出文件是否已经存在且有效
                if os.path.exists(self.output_path) and os.path.getsize(self.output_path) > 0:
                    self.progress.emit("已保存部分结果")
                    self.finished.emit(self.output_path)
                else:
                    self.error.emit("推理已被用户中断")
                return
            
            self.progress.emit("语音生成完成！")
            self.finished.emit(self.output_path)
        except Exception as e:
            self.error.emit(f"处理过程中出错: {str(e)}")
    
    def preprocess_text(self, text):
        """
        文本预处理，包括：
        1. 应用文本替换规则（如果有）
        2. 按段落分割
        3. 将空行替换为<br>标记
        4. 对非<br>段落按标点符号分割
        """
        # 应用文本替换规则
        if self.replace_rules:
            self.progress.emit("应用文本替换规则...")
            text = self.replace_text_by_config(text)
        
        self.progress.emit("分割段落并处理空行...")
        paragraphs = self.split_text_by_newlines_with_br(text)
        
        # 对每个段落，如果不是<br>标记，则按标点分割
        segments = []
        for para in paragraphs:
            if para == self.BR_TAG:
                segments.append(para)
            else:
                # 对非空且非<br>的段落按标点分割
                if para.strip():
                    para_segments = self.split_text_by_punctuation(para, self.punct_chars)
                    segments.extend(para_segments)
        
        return segments
    
    def split_text_by_punctuation(self, text, punct_chars):
        """按指定的标点符号分割文本"""
        if not text:
            return []
            
        # 构建用于分割的正则表达式
        pattern = f"([{re.escape(punct_chars)}])"
        
        # 分割文本
        parts = re.split(pattern, text)
        
        # 将标点符号与前面的文本合并
        segments = []
        i = 0
        while i < len(parts):
            if i + 1 < len(parts) and parts[i+1] in punct_chars:
                # 当前文本加上后面的标点
                segments.append(parts[i] + parts[i+1])
                i += 2
            else:
                # 没有标点的文本
                if parts[i]:  # 不添加空文本
                    segments.append(parts[i])
                i += 1
        
        return segments
    
    def split_text_by_newlines_with_br(self, text):
        """按空行分割文本成多个段落，并将空行替换为<br>标记"""
        # 首先将文本按行分割
        lines = text.split('\n')
        paragraphs = []
        current_para = []
        consecutive_empty_lines = 0
        
        # 逐行处理
        for line in lines:
            if line.strip():  # 非空行
                # 如果之前有累积的空行，添加<br>标记
                if consecutive_empty_lines > 0:
                    # 每个空行对应一个<br>标记
                    for _ in range(consecutive_empty_lines):
                        paragraphs.append(self.BR_TAG)
                    consecutive_empty_lines = 0
                
                current_para.append(line)
            else:  # 空行
                if current_para:  # 如果当前已有段落内容
                    paragraphs.append('\n'.join(current_para))
                    current_para = []
                # 累计空行计数
                consecutive_empty_lines += 1
        
        # 处理最后一个段落
        if current_para:
            paragraphs.append('\n'.join(current_para))
        
        # 处理末尾的空行
        for _ in range(consecutive_empty_lines):
            paragraphs.append(self.BR_TAG)
        
        return paragraphs
    
    def create_silence(self, duration, sample_rate):
        """创建指定时长的静音"""
        import torch
        # 计算样本数
        num_samples = int(duration * sample_rate)
        # 创建静音波形 (通道数, 样本数)
        silence = torch.zeros(1, num_samples)
        return silence
    
    def merge_audio_files_with_br(self, temp_outputs, silence_positions, segments, output_file):
        """合并多个音频文件成一个，考虑<br>标记位置添加静音"""
        import torch
        import torchaudio
        
        # 检查是否有音频文件
        if not temp_outputs:
            raise ValueError("没有音频文件可合并")
        
        # 先确定采样率
        _, first_file = temp_outputs[0]
        waveform, sample_rate = torchaudio.load(first_file)
        
        # 创建输出波形列表
        output_waveforms = []
        
        # 按照原始段落索引排序音频文件
        sorted_outputs = sorted(temp_outputs, key=lambda x: x[0])
        
        # 处理所有片段，包括添加<br>对应的静音
        last_index = -1
        for segment_index, audio_file in sorted_outputs:
            # 处理中间的<br>标记
            for silence_pos in silence_positions:
                if last_index < silence_pos < segment_index:
                    # 为每个<br>添加一个静音
                    silence = self.create_silence(self.pause_time, sample_rate)
                    output_waveforms.append(silence)
            
            # 添加当前段落的音频
            waveform, sr = torchaudio.load(audio_file)
            if sr != sample_rate:
                waveform = torchaudio.transforms.Resample(sr, sample_rate)(waveform)
            output_waveforms.append(waveform)
            
            # 添加静音
            silence = self.create_silence(self.pause_time, sample_rate)
            output_waveforms.append(silence)
            

            # 更新最后处理的索引
            last_index = segment_index
        
        # 处理末尾的<br>标记
        for silence_pos in silence_positions:
            if silence_pos > last_index:
                silence = self.create_silence(self.pause_time, sample_rate)
                output_waveforms.append(silence)
        
        # 检查是否有波形需要合并
        if not output_waveforms:
            raise ValueError("没有可合并的音频片段")
        
        # 合并所有波形
        merged_waveform = torch.cat(output_waveforms, dim=1)
        
        # 保存合并后的音频
        torchaudio.save(output_file, merged_waveform, sample_rate)
    
    def merge_audio_files_with_silence(self, input_files, output_file, segments):
        """合并多个音频文件成一个，并在片段间添加静音"""
        import torch
        import torchaudio
        import numpy as np
        
        # 读取所有音频以获取采样率
        if not input_files:
            raise ValueError("没有音频文件可合并")
        
        # 先确定采样率
        waveform, sample_rate = torchaudio.load(input_files[0])
        
        # 创建输出波形列表
        output_waveforms = []
        
        # 确定非空段落的索引
        non_empty_indices = [i for i, segment in enumerate(segments) if segment.strip()]
        
        # 初始化音频文件索引
        file_index = 0
        
        # 处理第一个非空段落
        if non_empty_indices and file_index < len(input_files):
            waveform, sr = torchaudio.load(input_files[file_index])
            if sr != sample_rate:
                waveform = torchaudio.transforms.Resample(sr, sample_rate)(waveform)
            output_waveforms.append(waveform)
            file_index += 1
        
        # 处理剩余的非空段落
        for i in range(1, len(non_empty_indices)):
            # 添加静音
            silence = self.create_silence(self.pause_time, sample_rate)
            output_waveforms.append(silence)
            
            # 添加当前段落的音频
            if file_index < len(input_files):
                waveform, sr = torchaudio.load(input_files[file_index])
                if sr != sample_rate:
                    waveform = torchaudio.transforms.Resample(sr, sample_rate)(waveform)
                output_waveforms.append(waveform)
                file_index += 1
        
        # 检查是否有波形需要合并
        if not output_waveforms:
            raise ValueError("没有可合并的音频片段")
        
        # 合并所有波形
        merged_waveform = torch.cat(output_waveforms, dim=1)
        
        # 保存合并后的音频
        torchaudio.save(output_file, merged_waveform, sample_rate) 