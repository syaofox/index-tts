"""推理工作线程控制器
提供TTS推理的后台处理功能。
"""

import os
import time
import re

from PySide6.QtCore import QObject, Signal


class InferenceWorker(QObject):
    """推理工作线程类，用于执行语音生成任务"""
    # 定义信号
    finished = Signal(str)  # 推理完成信号，返回输出文件路径
    progress = Signal(str)  # 进度信号，发送处理状态信息
    error = Signal(str)     # 错误信号
    
    # 特殊标记
    BR_TAG = "<br>"  # 空行标记

    def __init__(self, tts, voice_path, text, output_path=None, 
                 split_method="paragraph", punct_chars="。？！", pause_time=0.3):
        super().__init__()
        self.tts = tts
        self.voice_path = voice_path
        self.text = text
        self.output_path = output_path
        self.split_method = split_method  # "paragraph" 或 "punctuation"
        self.punct_chars = punct_chars    # 分割标点符号
        self.pause_time = pause_time      # 段落间停顿时间（秒）

    def run(self):
        try:
            if not self.output_path:
                self.output_path = os.path.join("outputs", f"spk_{int(time.time())}.wav")
            
            # 预处理文本
            self.progress.emit("预处理文本...")
            preprocessed_segments = self.preprocess_text(self.text)

            print(preprocessed_segments)
            
            if len(preprocessed_segments) > 1:
                self.progress.emit(f"共分为 {len(preprocessed_segments)} 个片段进行处理...")
                temp_outputs = []
                silence_positions = []  # 记录需要添加静音的位置
                
                segment_index = 0
                for i, segment in enumerate(preprocessed_segments):
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
                self.progress.emit("开始语音生成...")
                # 如果只有一个片段且不是<br>标记，直接处理
                if preprocessed_segments and preprocessed_segments[0] != self.BR_TAG:
                    self.tts.infer(self.voice_path, preprocessed_segments[0], self.output_path)
                else:
                    # 如果是<br>标记或没有内容，创建静音文件
                    import torchaudio
                    silence = self.create_silence(self.pause_time, 44100)  # 使用默认采样率
                    torchaudio.save(self.output_path, silence, 44100)
            
            self.progress.emit("语音生成完成！")
            self.finished.emit(self.output_path)
        except Exception as e:
            self.error.emit(f"处理过程中出错: {str(e)}")
    
    def preprocess_text(self, text):
        """
        文本预处理，包括：
        1. 按段落分割
        2. 将空行替换为<br>标记
        3. 对非<br>段落按标点符号分割
        """
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