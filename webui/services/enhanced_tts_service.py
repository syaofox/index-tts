#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
增强的TTS服务模块
提供支持文本切分和多角色的TTS服务
"""

import os
import torch
import torchaudio
import time
import re
import numpy as np
import traceback

# 统一使用相对导入路径
from webui.models.character_manager import CharacterManager
from webui.utils.text_processor import TextProcessor
from webui.utils.audio_utils import AudioUtils


class EnhancedTTSService:
    """增强的TTS服务，支持文本切分和多角色"""
    
    def __init__(self, tts_service):
        """
        初始化增强的TTS服务
        
        Args:
            tts_service: 原始TTS服务
        """
        self.tts_service = tts_service
        
        # 从配置文件加载文本替换规则 - 使用固定的相对路径
        config_path = os.path.join("webui", "config", "text_replace_config.txt")
        
        self.replace_rules = TextProcessor.load_replace_rules(config_path)
        
        # 日志回调函数，默认为打印到控制台
        self.log_callback = print
        
        # 角色管理器
        self.character_manager = CharacterManager("prompts")
        
        # 默认采样率
        self.default_sample_rate = 24000
        
        # 段落分隔标记
        self.BR_TAG = TextProcessor.BR_TAG  # 使用TextProcessor定义的BR_TAG
        
    def set_log_callback(self, callback_func):
        """
        设置日志回调函数
        
        Args:
            callback_func: 回调函数，接收日志消息字符串
        """
        self.log_callback = callback_func
        
    def log(self, message):
        """
        记录日志消息
        
        Args:
            message: 日志消息
        """
        # 如果回调为None或等于print，则直接打印到控制台
        # 否则调用自定义回调函数
        if self.log_callback is None or self.log_callback == print:
            print(message)
        else:
            self.log_callback(message)        
   
    
    def generate(self, prompt_path, text, output_path, mode="normal", punct_chars="。？！.!?;；：:", pause_time=0.2):
        """
        生成语音，支持文本切分和多角色
        
        Args:
            prompt_path: 提示音频文件路径
            text: 输入文本
            output_path: 输出音频文件路径
            mode: 推理模式，"normal"或"fast"
            punct_chars: 分割标点符号
            pause_time: 停顿时间(秒)
            
        Returns:
            str: 生成的音频文件路径
        """
        try:
            # 检查文本是否为空
            if not text or not text.strip():
                self.log("错误: 输入文本为空")
                return None
                
            # 检查提示音频是否为空
            if not prompt_path:
                self.log("警告: 未提供提示音频，尝试检测多角色文本")
                # 尝试解析文本为多角色对话
                is_multi_character, character_text_segments = TextProcessor.parse_multi_role_text(text)
                
                if is_multi_character:
                    self.log(f"检测到多角色文本，共 {len(character_text_segments)} 个角色")
                    return self.generate_multi_role_from_segments(character_text_segments, output_path, mode, punct_chars, pause_time)
                else:
                    self.log("错误: 未提供提示音频且无法检测到多角色对话")
                    return None
                    
            # 自定义文件名（如果未提供有效的路径或是默认路径）
            if not output_path or output_path.endswith("output.wav"):
                output_path = self._generate_output_filename(prompt_path, text, False)
                
            # 生成单角色语音
            print(f"生成单角色语音: {prompt_path}, {text}, {output_path}, {mode}, {punct_chars}, {pause_time}")
            return self.generate_with_segments(prompt_path, text, output_path, mode, punct_chars, pause_time)
                
        except Exception as e:
            return self._handle_exception("生成语音出错", e)
            
    def _generate_output_filename(self, prompt_path, text, is_multi_role=False, role_text_pairs=None):
        """
        生成输出文件名
        
        Args:
            prompt_path: 提示音频文件路径
            text: 输入文本
            is_multi_role: 是否为多角色生成
            role_text_pairs: 角色文本对，仅在is_multi_role为True时使用
            
        Returns:
            str: 生成的输出文件路径
        """
        try:
            # 为多角色生成专门的文件名
            if is_multi_role and role_text_pairs:
                # 使用第一个角色名和总角色数
                first_role = role_text_pairs[0][0]
                combined_name = f"{first_role}"
                if len(role_text_pairs) > 1:
                    combined_name += f"等{len(role_text_pairs)}人对话"
                
                # 添加时间戳
                timestamp = time.strftime("%Y%m%d%H%M%S", time.localtime())
                output_filename = f"[多角色][{timestamp}]{combined_name}"
                output_path = os.path.join("outputs", f"{output_filename}.wav")
                
            else:
                # 单角色生成
                # 从提示音频路径中提取角色名（如果可能）
                prompt_filename = os.path.basename(prompt_path)
                full_name = os.path.splitext(prompt_filename)[0]
                
                # 提取第一个下划线之前的内容作为角色名
                if "_" in full_name:
                    speaker_name = full_name.split("_", 1)[0]
                else:
                    speaker_name = full_name
                
                # 清理文本内容（取前50个字符）
                text_sample = text.strip().replace("\n", "").replace("\r", "").replace(" ", "")
                # 替换Windows文件名中的非法字符
                for char in '\\/:"*?<>|':
                    text_sample = text_sample.replace(char, "_")
                text_sample = text_sample[:50]  # 限制长度
                
                # 添加时间戳
                timestamp = time.strftime("%Y%m%d%H%M%S", time.localtime())
                output_filename = f"[{speaker_name}][{timestamp}]{text_sample}"
                output_path = os.path.join("outputs", f"{output_filename}.wav")
            
            # 确保输出目录存在
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            self.log(f"已生成自定义输出文件名: {output_path}")
            
            return output_path
            
        except Exception as e:
            self.log(f"生成输出文件名出错: {e}")
            # 返回一个默认的输出路径
            timestamp = time.strftime("%Y%m%d%H%M%S", time.localtime())
            return os.path.join("outputs", f"audio_{timestamp}.wav")
    
    def _process_text_segment(self, prompt_path, segment, role_name=None, mode="normal"):
        """
        处理单个文本片段，生成音频数据
        
        Args:
            prompt_path: 提示音频文件路径
            segment: 文本片段
            role_name: 角色名称(可选，用于日志)
            mode: 推理模式，"normal"或"fast"
            
        Returns:
            tuple: (是否成功, 采样率, 波形数据)
        """
        try:
            result = self.tts_service.generate(prompt_path, segment, None, mode)
            
            # 验证生成的音频数据有效
            if isinstance(result, tuple) and len(result) == 2:
                sample_rate, wave_data = result

                return True, sample_rate, wave_data
            else:
                if role_name:
                    self.log(f"警告: 角色 {role_name} 的音频生成失败或格式不正确")
                else:
                    self.log(f"警告: 音频生成失败或格式不正确")
                return False, None, None
                
        except Exception as e:
            if role_name:
                self._handle_exception(f"处理角色 {role_name} 的音频片段出错", e, False)
            else:
                self._handle_exception(f"处理音频片段出错", e, False)
            return False, None, None
    
    def generate_with_segments(self, prompt_path, text, output_path, mode="normal", punct_chars="。？！.!?;；：:", pause_time=0.2):
        """
        按段落生成语音，直接在内存中处理音频流
        
        Args:
            prompt_path: 提示音频文件路径
            text: 输入文本
            output_path: 输出音频文件路径
            mode: 推理模式，"normal"或"fast"
            punct_chars: 分割标点符号
            pause_time: 停顿时间(秒)
            
        Returns:
            str: 生成的音频文件路径
        """
        # 分析文本并分段
        segments = TextProcessor.preprocess_text(text, punct_chars, self.replace_rules)
        
        if not segments:
            self.log("警告: 文本预处理后没有有效的片段")
            return None
            
        # 打印分割后的片段信息
        self.log(f"文本被分割为 {len(segments)} 个片段，其中BR标记 {segments.count(self.BR_TAG)} 个")
        
        if len(segments) == 1:
            # 只有一个片段，直接使用原始服务
            self.log("只有一个文本片段，直接进行处理")
            return self.tts_service.generate(prompt_path, segments[0], output_path, mode)
        
        # 有多个片段，逐一处理并在内存中合并
        segment_audios = []  # 用于存储元组 (索引, 波形数据)
        silence_positions = []  # 存储需要插入静音的位置
        
        for i, segment in enumerate(segments):
            if segment == self.BR_TAG:
                # 记录需要插入静音的位置
                silence_positions.append(i)
                continue
                
            if not segment.strip():
                # 跳过空片段
                continue
            
            # 打印当前处理的片段
            self.log(f"处理片段 {i+1}/{len(segments)}: {segment[:30]}{'...' if len(segment) > 30 else ''}")
            
            # 使用辅助方法处理文本片段
            success, sample_rate, wave_data = self._process_text_segment(prompt_path, segment, None, mode)
            
            if success:
                segment_audios.append((i, wave_data))
                self.log(f"片段 {i+1} 生成成功，波形长度: {len(wave_data)}")
        
        # 检查是否有有效的音频片段
        if not segment_audios:
            self.log("错误: 没有生成任何有效的音频片段")
            return None
        
        # 在内存中合并音频片段，添加静音间隔
        self.log(f"开始合并 {len(segment_audios)} 个音频片段，添加静音...")
        
        # 使用音频处理工具直接合并内存中的音频
        merged_audio, merged_sr = AudioUtils.merge_audio_with_silence(
            segment_audios, 
            silence_positions, 
            pause_time, 
            self.default_sample_rate
        )
        
        if merged_audio is None:
            self.log("错误: 合并音频片段失败")
            return None
        
        
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            torchaudio.save(output_path, merged_audio, merged_sr)
            
            return output_path
        except Exception as e:
            return self._handle_exception("保存音频文件出错", e)
    
    def generate_multi_role_from_segments(self, character_text_segments, output_path, mode="normal", punct_chars="。？！.!?;；：:", pause_time=0.2):
        """
        生成多角色语音，从段落直接生成
        
        Args:
            character_text_segments: 角色文本段落列表 [(角色名, 文本内容), ...]
            output_path: 输出音频文件路径
            mode: 推理模式，"normal"或"fast"
            punct_chars: 分割标点符号
            pause_time: 停顿时间(秒)
            
        Returns:
            str: 生成的音频文件路径
        """
        # 自定义文件名（如果未提供有效的路径或是默认路径）
        if not output_path or output_path.endswith("output.wav"):
            output_path = self._generate_output_filename(None, "", True, character_text_segments)
            
        # 逐个处理每个角色的文本
        role_audio_segments = []  # [(角色名, 波形数据, 采样率), ...]
        
        for i, (role_name, text) in enumerate(character_text_segments):
            self.log(f"处理角色 {role_name} 的文本 ({i+1}/{len(character_text_segments)})")
            
            # 查找角色的提示音频
            prompt_paths = self.character_manager.find_character_audios(role_name)
            
            # 选择第一个有效的提示音频
            prompt_path = None
            for path in prompt_paths:
                if os.path.exists(path) and os.path.isfile(path):
                    prompt_path = path
                    break
            
            if not prompt_path:
                self.log(f"警告: 未找到角色 {role_name} 的提示音频，跳过此角色")
                continue
            
            # 为此角色的文本应用相同的预处理逻辑，与单角色推理保持一致
            segments = TextProcessor.preprocess_text(text, punct_chars, self.replace_rules)
            
            if not segments:
                self.log(f"警告: 角色 {role_name} 的文本预处理后没有有效的片段，跳过此角色")
                continue
                
            self.log(f"角色 {role_name} 的文本被分割为 {len(segments)} 个片段，其中BR标记 {segments.count(self.BR_TAG)} 个")
            
            # 处理角色的每个文本片段并合并
            role_segment_audios = []  # 用于存储元组 (索引, 波形数据)
            role_silence_positions = []  # 存储需要插入静音的位置
            
            if len(segments) == 1:
                # 只有一个片段，直接使用原始服务
                self.log(f"角色 {role_name} 只有一个文本片段，直接进行处理")
                success, sample_rate, wave_data = self._process_text_segment(prompt_path, segments[0], role_name, mode)
                
                if success:
                    role_audio_segments.append((role_name, wave_data, sample_rate))
                    
            else:
                # 有多个片段，逐一处理并在内存中合并
                for j, segment in enumerate(segments):
                    if segment == self.BR_TAG:
                        # 记录需要插入静音的位置
                        role_silence_positions.append(j)
                        continue
                        
                    if not segment.strip():
                        # 跳过空片段
                        continue
                    
                    # 打印当前处理的片段
                    self.log(f"处理角色 {role_name} 的片段 {j+1}/{len(segments)}: {segment[:30]}{'...' if len(segment) > 30 else ''}")
                    
                    # 使用辅助方法处理文本片段
                    success, _, wave_data = self._process_text_segment(prompt_path, segment, role_name, mode)
                    
                    if success:
                        role_segment_audios.append((j, wave_data))
                
                # 检查是否有有效的音频片段
                if not role_segment_audios:
                    self.log(f"错误: 角色 {role_name} 没有生成任何有效的音频片段，跳过此角色")
                    continue
                
                # 在内存中合并音频片段，添加静音间隔
                self.log(f"开始合并角色 {role_name} 的 {len(role_segment_audios)} 个音频片段，添加静音...")
                
                # 使用音频处理工具直接合并内存中的音频
                merged_role_audio, merged_role_sr = AudioUtils.merge_audio_with_silence(
                    role_segment_audios, 
                    role_silence_positions, 
                    pause_time, 
                    self.default_sample_rate
                )
                
                if merged_role_audio is None:
                    self.log(f"错误: 合并角色 {role_name} 的音频片段失败，跳过此角色")
                    continue
                
                # 将合并后的角色音频添加到角色音频列表
                role_audio_segments.append((role_name, merged_role_audio, merged_role_sr))
                self.log(f"角色 {role_name} 的音频片段合并成功，波形长度: {merged_role_audio.shape[1]}")
        
        # 检查是否有有效的音频片段
        if not role_audio_segments:
            self.log("错误: 没有生成任何有效的角色音频片段")
            return None
        
        # 在内存中合并所有角色的音频
        self.log(f"开始合并 {len(role_audio_segments)} 个角色的音频...")
            
        # 确定最终使用的采样率（优先使用第一个角色的采样率，否则使用默认值）
        final_sr = self.default_sample_rate
        if role_audio_segments and role_audio_segments[0][2]:
            final_sr = role_audio_segments[0][2]
        
        # 使用音频处理工具直接合并内存中的音频，角色之间添加静音
        merged_audio = None
        
        try:
            # 规范化音频格式
            processed_segments = []
            # 记录第一个有效片段的形状，用于统一所有片段的形状
            first_segment_shape = None
            
            for i, (role_name, wave_data, sr) in enumerate(role_audio_segments):
                # 确保采样率一致（这里简化处理，仅打印警告）
                if sr != final_sr:
                    self.log(f"警告: 角色 {role_name} 的采样率 {sr} 与目标采样率 {final_sr} 不一致，可能导致质量问题")
                
                # 标准化音频数据
                normalized_wave_data, is_valid, updated_shape = self._normalize_audio_data(wave_data, role_name, first_segment_shape)
                
                if not is_valid:
                    self.log(f"警告: 角色 {role_name} 的音频数据标准化失败，跳过此角色")
                    continue
                
                processed_segments.append(normalized_wave_data)
                
                # 更新或使用通道数信息
                if first_segment_shape is None:
                    first_segment_shape = updated_shape
            
            # 检查是否有有效的处理片段
            if not processed_segments:
                self.log("错误: 所有音频片段处理后均无效")
                return None
            
            # 确保我们有一个有效的形状信息且合理
            if first_segment_shape is None:
                first_segment_shape = 1  # 默认单通道
            elif first_segment_shape > 2:
                self.log(f"警告: 通道数 {first_segment_shape} 异常大，重置为单通道")
                first_segment_shape = 1
            
            # 创建相应的静音片段，与音频片段的通道数保持一致
            silence_duration = int(pause_time * final_sr)
            silence = torch.zeros(first_segment_shape, silence_duration, dtype=torch.float32)
            
            # 合并所有片段，角色之间添加静音
            all_segments = []
            for i, seg in enumerate(processed_segments):
                if i > 0:  # 从第二个片段开始，在前面添加静音
                    all_segments.append(silence)
                all_segments.append(seg)
            
            # 输出每个片段的形状，用于调试
            for i, seg in enumerate(all_segments):
                self.log(f"片段 {i} 形状: {seg.shape}")
                
            # 合并所有片段
            merged_audio = torch.cat(all_segments, dim=1)
            
            # 保存到文件
            self.log(f"保存合并后的多角色音频到 {output_path}")
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # 转换为int16以供保存
            merged_audio_int16 = merged_audio.to(torch.int16)
            torchaudio.save(output_path, merged_audio_int16, final_sr)
            self.log(f"成功保存多角色音频到 {output_path}")
            return output_path
            
        except Exception as e:
            return self._handle_exception("合并多角色音频出错", e)

    def _normalize_audio_data(self, wave_data, role_name, first_segment_shape=None):
        """
        标准化音频数据格式，处理不同类型的输入
        
        Args:
            wave_data: 原始音频数据(numpy数组或torch张量)
            role_name: 角色名称(用于日志)
            first_segment_shape: 首个片段的通道数(用于保持一致性)
            
        Returns:
            tuple: (处理后的音频张量, 是否成功, 更新后的首个片段通道数)
        """
        try:
            # 尝试将数据转换为torch张量
            if isinstance(wave_data, np.ndarray):
                tensor_data = torch.tensor(wave_data, dtype=torch.float32)
            elif isinstance(wave_data, torch.Tensor):
                tensor_data = wave_data.float()  # 转换为float32类型
            else:
                # 尝试将未知类型转换为tensor
                tensor_data = torch.tensor(wave_data, dtype=torch.float32)
            
            # 标准化维度：确保是2D张量 [通道数, 样本数]
            if tensor_data.dim() == 1:
                tensor_data = tensor_data.unsqueeze(0)  # [1, 样本数]
            elif tensor_data.dim() == 3:
                # 如果是3D张量，取第一个维度的数据
                self.log(f"警告: 角色 {role_name} 的音频是3D张量，取第一个维度: {tensor_data.shape}")
                tensor_data = tensor_data[0]
            
            # 检查并修正张量维度顺序
            if tensor_data.shape[0] > 10:  # 通常通道数不会超过10
                self.log(f"警告: 检测到张量维度可能颠倒，尝试转置 - 原始形状: {tensor_data.shape}")
                tensor_data = tensor_data.transpose(0, 1)
                self.log(f"转置后形状: {tensor_data.shape}")
            
            # 更新或使用通道数信息
            current_shape = min(tensor_data.shape[0], 2)  # 限制最多2个通道
            if first_segment_shape is None:
                first_segment_shape = current_shape
            
            # 确保通道数一致
            if tensor_data.shape[0] != first_segment_shape:
                self.log(f"调整角色 {role_name} 的音频通道数从 {tensor_data.shape[0]} 到 {first_segment_shape}")
                if tensor_data.shape[0] < first_segment_shape:
                    # 如果通道数少，复制已有通道到指定大小
                    tensor_data = tensor_data.repeat(first_segment_shape // tensor_data.shape[0] + 1, 1)[:first_segment_shape]
                else:
                    # 如果通道数多，只保留需要的通道
                    tensor_data = tensor_data[:first_segment_shape]
            
            return tensor_data, True, first_segment_shape
            
        except Exception as e:
            self.log(f"标准化角色 {role_name} 的音频数据时出错: {e}")
            return None, False, first_segment_shape

    def _handle_exception(self, error_msg, e, show_traceback=True):
        """
        统一处理异常的辅助方法
        
        Args:
            error_msg: 错误消息
            e: 异常对象
            show_traceback: 是否显示堆栈跟踪
            
        Returns:
            None: 始终返回None以简化错误处理代码
        """
        self.log(f"{error_msg}: {e}")
        if show_traceback:
            traceback.print_exc()
        return None 