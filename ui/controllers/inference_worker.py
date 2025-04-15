"""推理工作线程控制器
提供TTS推理的后台处理功能。
"""

import os
import time

from PySide6.QtCore import QObject, Signal


class InferenceWorker(QObject):
    """推理工作线程类，用于执行语音生成任务"""
    # 定义信号
    finished = Signal(str)  # 推理完成信号，返回输出文件路径
    progress = Signal(str)  # 进度信号，发送处理状态信息
    error = Signal(str)     # 错误信号

    def __init__(self, tts, voice_path, text, output_path=None):
        super().__init__()
        self.tts = tts
        self.voice_path = voice_path
        self.text = text
        self.output_path = output_path

    def run(self):
        try:
            if not self.output_path:
                self.output_path = os.path.join("outputs", f"spk_{int(time.time())}.wav")
            
            # 按空行分割文本
            self.progress.emit("按段落分割文本...")
            paragraphs = self.split_text_by_newlines(self.text)
            
            if len(paragraphs) > 1:
                self.progress.emit(f"共分为 {len(paragraphs)} 个段落进行处理...")
                temp_outputs = []
                
                for i, para in enumerate(paragraphs):
                    if not para.strip():  # 跳过空段落
                        continue
                    temp_path = os.path.join("outputs", f"temp_{int(time.time())}_{i}.wav")
                    self.progress.emit(f"处理第 {i+1}/{len(paragraphs)} 段...")
                    self.tts.infer(self.voice_path, para, temp_path)
                    temp_outputs.append(temp_path)
                
                # 合并所有音频片段，并在段落间添加静音
                self.progress.emit("合并音频片段，添加段落间静音...")
                self.merge_audio_files_with_silence(temp_outputs, self.output_path, paragraphs)
                
                # 清理临时文件
                for temp_file in temp_outputs:
                    try:
                        os.remove(temp_file)
                    except:
                        pass
            else:
                self.progress.emit("开始语音生成...")
                self.tts.infer(self.voice_path, self.text, self.output_path)
            
            self.progress.emit("语音生成完成！")
            self.finished.emit(self.output_path)
        except Exception as e:
            self.error.emit(f"处理过程中出错: {str(e)}")
    
    def split_text_by_newlines(self, text):
        """按空行分割文本成多个段落"""
        # 首先将文本按行分割
        lines = text.split('\n')
        paragraphs = []
        current_para = []
        
        # 逐行处理
        for line in lines:
            if line:  # 非空行
                current_para.append(line)
            else:  # 空行
                if current_para:  # 如果当前已有段落内容
                    paragraphs.append('\n'.join(current_para))
                    current_para = []
                paragraphs.append('')  # 添加空段落标记，用于后续添加静音
        
        # 处理最后一个段落
        if current_para:
            paragraphs.append('\n'.join(current_para))
        
        return paragraphs
    
    def create_silence(self, duration, sample_rate):
        """创建指定时长的静音"""
        import torch
        # 计算样本数
        num_samples = int(duration * sample_rate)
        # 创建静音波形 (通道数, 样本数)
        silence = torch.zeros(1, num_samples)
        return silence
    
    def merge_audio_files_with_silence(self, input_files, output_file, paragraphs):
        """合并多个音频文件成一个，并在段落间添加静音"""
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
        non_empty_indices = [i for i, para in enumerate(paragraphs) if para.strip()]
        print(f"非空段落索引: {non_empty_indices}")
        
        # 初始化音频文件索引
        file_index = 0
        
        # 处理第一个非空段落
        if non_empty_indices and file_index < len(input_files):
            waveform, sr = torchaudio.load(input_files[file_index])
            if sr != sample_rate:
                waveform = torchaudio.transforms.Resample(sr, sample_rate)(waveform)
            output_waveforms.append(waveform)
            file_index += 1
            print(f"添加音频: 段落 {non_empty_indices[0]+1}")
        
        # 处理剩余的非空段落
        for i in range(1, len(non_empty_indices)):
            # 计算当前非空段落和前一个非空段落之间的空段落数量
            prev_index = non_empty_indices[i-1]
            current_index = non_empty_indices[i]
            empty_paragraphs_between = current_index - prev_index - 1
            
            # 添加静音（每个空段落0.3秒）
            if empty_paragraphs_between > 0:
                silence_duration = 0.3 * empty_paragraphs_between
                silence = self.create_silence(silence_duration, sample_rate)
                output_waveforms.append(silence)
                print(f"添加静音: {silence_duration}秒 (段落 {prev_index+1} 和 {current_index+1} 之间)")
            
            # 添加当前段落的音频
            if file_index < len(input_files):
                waveform, sr = torchaudio.load(input_files[file_index])
                if sr != sample_rate:
                    waveform = torchaudio.transforms.Resample(sr, sample_rate)(waveform)
                output_waveforms.append(waveform)
                file_index += 1
                print(f"添加音频: 段落 {current_index+1}")
        
        # 检查是否有波形需要合并
        if not output_waveforms:
            raise ValueError("没有可合并的音频片段")
        
        # 合并所有波形
        merged_waveform = torch.cat(output_waveforms, dim=1)
        
        # 保存合并后的音频
        torchaudio.save(output_file, merged_waveform, sample_rate)
        print(f"合并完成: 共 {len(output_waveforms)} 个音频片段") 