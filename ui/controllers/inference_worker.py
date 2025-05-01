"""推理工作线程控制器
提供TTS推理的后台处理功能。
"""

import os
import time
import re
from pathlib import Path
import tempfile
import uuid
import wave
import numpy as np

from PySide6.QtCore import QObject, Signal, QMutex, QWaitCondition
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
                self.error.emit("语音生成失败")
                
        except Exception as e:
            import traceback
            error_msg = f"推理出错: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            self.error.emit(error_msg)

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
        """
        按换行符分割文本，并将空行替换为<br>标记
        
        Args:
            text (str): 输入文本
            
        Returns:
            list: 分割后的段落列表，空行被替换为<br>标记
        """
        if not text:
            return []
            
        # 分割行
        lines = text.split('\n')
        
        # 处理段落和空行
        paragraphs = []
        current_paragraph = []
        
        for line in lines:
            line = line.strip()
            if line:
                # 非空行，添加到当前段落
                current_paragraph.append(line)
            else:
                # 空行，结束当前段落
                if current_paragraph:
                    # 将当前段落合并为一个字符串
                    paragraphs.append(' '.join(current_paragraph))
                    current_paragraph = []
                
                # 添加<br>标记表示空行
                if not paragraphs or paragraphs[-1] != self.BR_TAG:
                    paragraphs.append(self.BR_TAG)
        
        # 处理最后一个段落
        if current_paragraph:
            paragraphs.append(' '.join(current_paragraph))
        
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
            if not os.path.exists(self.voice_path):
                self.error.emit(f"参考音频文件不存在: {self.voice_path}")
                return False, None
            
            # 检查文本是否为空
            if not self.text.strip():
                self.error.emit("推理文本不能为空")
                return False, None
            
            # 加载替换规则
            self.progress.emit("正在加载替换规则...")
            replace_rules = self.load_replace_rules()
            
            # 生成输出路径（如果未提供）
            if not self.output_path:
                # 创建输出目录（如果不存在）
                output_dir = "outputs"
                os.makedirs(output_dir, exist_ok=True)
                # 为输出文件生成一个带时间戳的文件名
                timestamp = time.strftime("%Y%m%d%H%M%S", time.localtime())
                self.output_path = os.path.join(output_dir, f"output_{timestamp}.wav")
            
            # 确保输出目录存在
            os.makedirs(os.path.dirname(self.output_path), exist_ok=True)
            
            # 预处理文本
            self.progress.emit("正在预处理文本...")
            preprocessed_segments = self.preprocess_text(self.text)
            
            # 根据段落数量决定处理方式
            if len(preprocessed_segments) > 1:
                return self.process_text_in_segments(preprocessed_segments)
            else:
                # 作为单个文本处理
                self.progress.emit("文本将作为整体处理...")
                return self.process_single_text(self.text, self.output_path)
            
        except Exception as e:
            import traceback
            error_msg = f"处理推理任务时出错: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            self.error.emit(error_msg)
            return False, None
    
    def load_replace_rules(self):
        """加载文本替换规则"""
        try:
            if os.path.exists(self.REPLACE_CONFIG_PATH):
                self.check_and_load_config()
                return self.replace_rules
            return []
        except Exception as e:
            print(f"加载替换规则出错: {str(e)}")
            return []
    
    def process_text_in_segments(self, preprocessed_segments=None):
        """按段落处理文本，返回(success, output_file_path)"""
        try:
            if preprocessed_segments is None:
                preprocessed_segments = self.preprocess_text(self.text)
            
            self.progress.emit(f"共分为 {len(preprocessed_segments)} 个片段进行处理...")
            temp_outputs = []
            silence_positions = []  # 记录需要添加静音的位置
            
            segment_index = 0
            for i, segment in enumerate(preprocessed_segments):
                # 检查是否请求停止
                if self._stop_requested:
                    # 尝试保存部分结果
                    if self.save_partial_output(temp_outputs, silence_positions, preprocessed_segments):
                        return True, self.output_path
                    
                    # 如果无法保存部分结果，则报告中断
                    self.error.emit("推理已被用户中断")
                    return False, None
                
                if segment == self.BR_TAG:  # 处理<br>标记
                    silence_positions.append(i)
                    continue
                
                if not segment.strip():  # 跳过空片段
                    continue
                    
                # 创建临时输出文件路径
                temp_path = os.path.join("outputs", f"temp_{int(time.time())}_{segment_index}.wav")
                
                self.progress.emit(f"处理第 {segment_index+1}/{len(preprocessed_segments) - len(silence_positions)} 段...")
                self.tts.infer(self.voice_path, segment, temp_path)
                temp_outputs.append((i, temp_path))  # 保存原始索引位置和文件路径
                segment_index += 1
            
            # 检查是否请求停止
            if self._stop_requested:
                # 尝试保存部分结果
                if self.save_partial_output(temp_outputs, silence_positions, preprocessed_segments):
                    return True, self.output_path
                
                # 如果无法保存部分结果，则报告中断
                self.error.emit("推理已被用户中断")
                return False, None
            
            # 合并所有音频片段，包括<br>标记处的静音
            self.progress.emit(f"合并音频片段，添加段落间静音 ({self.pause_time}秒)...")
            self.merge_audio_files_with_br(temp_outputs, silence_positions, preprocessed_segments, self.output_path)
            
            # 清理临时文件
            for _, temp_file in temp_outputs:
                try:
                    os.remove(temp_file)
                except:
                    pass
            
            return True, self.output_path
            
        except Exception as e:
            import traceback
            error_msg = f"按段落处理文本时出错: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            self.error.emit(error_msg)
            return False, None
    
    def process_single_text(self, text, output_path):
        """处理单个文本片段，返回(success, output_file_path)"""
        try:
            # 检查是否请求停止
            if self._stop_requested:
                self.error.emit("推理已被用户中断")
                return False, None
            
            self.progress.emit("开始语音生成...")
            
            # 应用文本替换规则（如果有）
            if self.replace_rules:
                text = self.replace_text_by_config(text)
            
            # 执行推理
            self.tts.infer(self.voice_path, text, output_path)
            
            # 最后检查一次是否请求停止
            if self._stop_requested:
                # 检查输出文件是否已经存在且有效
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    self.progress.emit("已保存生成结果")
                    return True, output_path
                else:
                    self.error.emit("推理已被用户中断")
                    return False, None
            
            self.progress.emit("语音生成完成！")
            return True, output_path
            
        except Exception as e:
            import traceback
            error_msg = f"处理单个文本片段时出错: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            self.error.emit(error_msg)
            return False, None

class MultiRoleInferenceWorker(QObject):
    """多角色推理工作器类"""
    
    # 定义信号
    finished = Signal(str)  # 参数为输出音频路径
    progress = Signal(str)  # 参数为进度消息
    error = Signal(str)     # 参数为错误消息
    
    def __init__(self, tts, character_manager, role_text_pairs, punct_chars="。？！", pause_time=0.3):
        """
        初始化多角色推理工作器
        
        Args:
            tts: TTS模型对象
            character_manager: 角色管理器对象
            role_text_pairs: [(角色名, 文本内容), ...] 格式的列表
            punct_chars: 分割文本的标点符号
            pause_time: 停顿时间(秒)
        """
        super().__init__()
        self.tts = tts
        self.character_manager = character_manager
        self.role_text_pairs = role_text_pairs
        self.punct_chars = punct_chars
        self.pause_time = pause_time
        
        # 创建一个唯一的临时目录用于存放中间文件
        self.temp_dir = os.path.join(character_manager.prompt_dir, "temp", str(uuid.uuid4()))
        os.makedirs(self.temp_dir, exist_ok=True)
        
        # 停止标志
        self.stop_requested = False
        self.mutex = QMutex()
        self.condition = QWaitCondition()
    
    def stop(self):
        """请求停止推理过程"""
        self.mutex.lock()
        self.stop_requested = True
        self.mutex.unlock()
        self.condition.wakeAll()
    
    def run(self):
        """执行多角色推理任务"""
        try:
            # 检查是否有有效的角色-文本对
            if not self.role_text_pairs:
                self.error.emit("没有有效的角色-文本对")
                return
            
            # 用于存储每个角色生成的音频文件路径
            audio_files = []
            
            # 对每个角色-文本对进行推理
            for i, (role_name, text) in enumerate(self.role_text_pairs):
                # 检查是否请求停止
                self.mutex.lock()
                if self.stop_requested:
                    self.mutex.unlock()
                    self.error.emit("推理已被用户中断")
                    return
                self.mutex.unlock()
                
                # 发送进度消息
                self.progress.emit(f"正在处理角色 '{role_name}' 的文本 ({i+1}/{len(self.role_text_pairs)})")
                
                # 加载角色数据
                character_data = self.character_manager.load_character(role_name)
                if not character_data or "voice_path" not in character_data:
                    self.error.emit(f"无法加载角色 '{role_name}' 或角色数据不完整")
                    return
                
                voice_path = character_data["voice_path"]
                if not os.path.exists(voice_path):
                    self.error.emit(f"角色 '{role_name}' 的参考音频不存在: {voice_path}")
                    return
                
                # 为当前角色生成一个临时输出文件
                temp_output_path = os.path.join(self.temp_dir, f"{role_name}_{i}.wav")
                
                # 创建一个推理工作器来处理当前角色的文本
                worker = InferenceWorker(
                    self.tts,
                    voice_path,
                    text,
                    output_path=temp_output_path,
                    punct_chars=self.punct_chars,
                    pause_time=self.pause_time
                )
                
                # 连接信号（使用lambda闭包保留角色名）
                role_name_capture = role_name  # 捕获当前迭代的角色名
                worker.progress.connect(lambda msg, name=role_name_capture: self.progress.emit(f"[{name}] {msg}"))
                
                # 运行推理（同步）
                success, output_file = worker.process_inference()
                
                if not success or not output_file or not os.path.exists(output_file):
                    self.error.emit(f"处理角色 '{role_name}' 的文本时出错")
                    return
                
                # 添加到音频文件列表
                audio_files.append(output_file)
            
            # 检查是否至少有一个音频文件
            if not audio_files:
                self.error.emit("没有生成任何有效的音频文件")
                return
                
            # 合并所有角色的音频文件
            self.progress.emit("正在合并所有角色的音频文件...")
            
            # 生成最终输出文件名
            # 使用第一个角色名和最后一个角色名组合
            first_role = self.role_text_pairs[0][0]
            last_role = self.role_text_pairs[-1][0]
            combined_name = f"{first_role}"
            if len(self.role_text_pairs) > 1:
                combined_name += f"等{len(self.role_text_pairs)}人对话"
            
            timestamp = time.strftime("%Y%m%d%H%M%S", time.localtime())
            output_filename = f"[多角色][{timestamp}]{combined_name}"
            output_path = os.path.join("outputs", f"{output_filename}.wav")
            
            # 确保输出目录存在
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # 尝试合并音频
            try:
                merged_file = self.merge_audio_files(audio_files, output_path)
                
                if not merged_file or not os.path.exists(merged_file):
                    # 如果合并失败但至少有一个音频文件，可以保存第一个音频文件作为最终输出
                    if audio_files and os.path.exists(audio_files[0]):
                        self.progress.emit("合并失败，保存第一个角色的音频作为输出...")
                        import shutil
                        shutil.copy2(audio_files[0], output_path)
                        merged_file = output_path
                    else:
                        raise ValueError("合并音频文件失败且没有可用的备选音频")
            except Exception as e:
                import traceback
                error_msg = f"合并音频文件时出错: {str(e)}\n{traceback.format_exc()}"
                self.progress.emit("尝试保存单个角色音频文件...")
                
                # 保存第一个角色的音频作为输出
                if audio_files and os.path.exists(audio_files[0]):
                    try:
                        self.progress.emit("合并失败，保存第一个角色的音频作为输出...")
                        import shutil
                        shutil.copy2(audio_files[0], output_path)
                        merged_file = output_path
                    except Exception as copy_error:
                        self.error.emit(f"保存单个角色音频失败: {str(copy_error)}")
                        return
                else:
                    self.error.emit(f"合并音频失败且没有可用的备选音频")
                    return
            
            # 清理临时目录
            self.cleanup_temp_files()
            
            # 发送完成信号
            self.finished.emit(merged_file)
            
        except Exception as e:
            import traceback
            error_msg = f"多角色推理出错: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            self.error.emit(error_msg)
            
            # 尝试清理临时文件
            self.cleanup_temp_files()
    
    def merge_audio_files(self, audio_files, output_path):
        """
        合并多个WAV音频文件
        
        Args:
            audio_files (list): 要合并的WAV文件路径列表
            output_path (str): 合并后的输出文件路径
            
        Returns:
            str: 合并后的文件路径，如果失败则返回None
        """
        if not audio_files:
            return None
        
        try:
            # 如果只有一个文件，直接复制
            if len(audio_files) == 1:
                from shutil import copy2
                copy2(audio_files[0], output_path)
                return output_path
            
            # 使用torchaudio合并音频文件
            import torch
            import torchaudio
            
            # 读取第一个文件以获取采样率
            waveform, sample_rate = torchaudio.load(audio_files[0])
            
            # 创建一个列表用于存储所有音频片段
            waveforms = []
            
            # 依次读取每个文件并添加到列表
            for file_path in audio_files:
                # 加载音频文件
                current_waveform, current_sr = torchaudio.load(file_path)
                
                # 如果采样率不一致，则进行重采样
                if current_sr != sample_rate:
                    resampler = torchaudio.transforms.Resample(current_sr, sample_rate)
                    current_waveform = resampler(current_waveform)
                
                # 确保声道数一致（使用第一个文件的声道数）
                if current_waveform.shape[0] != waveform.shape[0]:
                    # 如果当前文件声道数少于第一个文件，复制声道
                    if current_waveform.shape[0] < waveform.shape[0]:
                        current_waveform = current_waveform.repeat(waveform.shape[0], 1)
                    # 如果当前文件声道数多于第一个文件，只保留需要的声道数
                    else:
                        current_waveform = current_waveform[:waveform.shape[0], :]
                
                # 添加到列表
                waveforms.append(current_waveform)
            
            # 使用torch.cat沿时间维度合并所有波形
            merged_waveform = torch.cat(waveforms, dim=1)
            
            # 保存合并后的文件
            torchaudio.save(output_path, merged_waveform, sample_rate)
            
            return output_path
        
        except Exception as e:
            import traceback
            error_msg = f"合并音频文件时出错: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            self.error.emit(f"合并音频文件时出错: {str(e)}")
            return None
    
    def cleanup_temp_files(self):
        """清理临时文件和目录"""
        try:
            import shutil
            if os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception as e:
            print(f"清理临时文件时出错: {str(e)}") 