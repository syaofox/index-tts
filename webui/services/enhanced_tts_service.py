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

# 使用try-except适应不同的导入场景
try:
    # 直接运行时的导入路径
    from utils.character_manager import CharacterManager
    from utils.text_processor import TextProcessor
    from utils.audio_utils import AudioUtils
except ImportError:
    # 以模块方式运行时的导入路径
    from webui.utils.character_manager import CharacterManager
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
        self.temp_dir = os.path.join("outputs", "temp")
        os.makedirs(self.temp_dir, exist_ok=True)
        
        # 从配置文件加载文本替换规则 - 支持多种运行方式
        config_path = "webui/text_replace_config.txt"
        if not os.path.exists(config_path):
            # 尝试相对路径
            config_path = "text_replace_config.txt"
        
        self.replace_rules = self.load_replace_rules(config_path)
        
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
        # 打印到终端并通过回调发送到UI
        print(message)
        if self.log_callback and self.log_callback != print:
            self.log_callback(message)
        
    def load_replace_rules(self, config_path):
        """从配置文件加载文本替换规则"""
        replace_rules = []
        try:
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        # 跳过空行和注释行
                        if not line or line.startswith('#'):
                            continue
                        # 解析规则：查找字符串|需修改字符串|替换后的字符串
                        parts = line.split('|')
                        if len(parts) == 3:
                            replace_rules.append((parts[0], parts[1], parts[2]))
            return replace_rules
        except Exception as e:
            self.log(f"加载替换规则出错: {e}")
            return []
    
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
            self.log(f"生成语音出错: {e}")
            import traceback
            traceback.print_exc()
            return None
            
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
            
            # 使用原始服务生成当前片段，直接返回音频数据
            try:
                result = self.tts_service.generate(prompt_path, segment, None, mode)
                
                # 验证生成的音频数据有效
                if isinstance(result, tuple) and len(result) == 2:
                    sample_rate, wave_data = result
                    segment_audios.append((i, wave_data))
                    self.log(f"片段 {i+1} 生成成功，波形长度: {len(wave_data)}")
                else:
                    self.log(f"警告: 片段 {i+1} 生成失败或格式不正确")
            except Exception as e:
                self.log(f"处理片段 {i+1} 出错: {e}")
                import traceback
                traceback.print_exc()
        
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
        
        # 保存合并后的音频到文件
        self.log(f"保存合并后的音频到 {output_path}")
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            torchaudio.save(output_path, merged_audio, merged_sr)
            self.log(f"成功保存音频到 {output_path}")
            return output_path
        except Exception as e:
            self.log(f"保存音频文件出错: {e}")
            import traceback
            traceback.print_exc()
            return None
    
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
        import torch
        import numpy as np
        import torchaudio
        import os
        import time
        
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
            
            # 为此角色生成音频
            try:
                # 使用内存模式，不保存临时文件
                result = self.tts_service.generate(prompt_path, text, None, mode)
                
                # 验证生成的音频数据有效
                if isinstance(result, tuple) and len(result) == 2:
                    sample_rate, wave_data = result
                    role_audio_segments.append((role_name, wave_data, sample_rate))
                    self.log(f"角色 {role_name} 的音频生成成功，波形长度: {len(wave_data)}")
                else:
                    self.log(f"警告: 角色 {role_name} 的音频生成失败或格式不正确")
            except Exception as e:
                self.log(f"处理角色 {role_name} 出错: {e}")
                import traceback
                traceback.print_exc()
        
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
                
                # 确保数据格式正确
                if isinstance(wave_data, np.ndarray):
                    # 将NumPy数组转换为Torch张量，并确保是浮点型
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
                        # 如果第一维很大，可能是颠倒的，尝试转置
                        tensor_data = tensor_data.transpose(0, 1)
                        self.log(f"转置后形状: {tensor_data.shape}")
                    
                    # 记录第一个有效片段的形状
                    if first_segment_shape is None:
                        # 确保不超过2个通道（通常为单声道或立体声）
                        first_segment_shape = min(tensor_data.shape[0], 2)
                    
                    # 确保通道数一致且合理（不超过2个通道）
                    if tensor_data.shape[0] != first_segment_shape:
                        self.log(f"调整角色 {role_name} 的音频通道数从 {tensor_data.shape[0]} 到 {first_segment_shape}")
                        if tensor_data.shape[0] < first_segment_shape:
                            # 如果通道数少，复制已有通道到指定大小
                            tensor_data = tensor_data.repeat(first_segment_shape // tensor_data.shape[0] + 1, 1)[:first_segment_shape]
                        else:
                            # 如果通道数多，只保留需要的通道
                            tensor_data = tensor_data[:first_segment_shape]
                    
                    processed_segments.append(tensor_data)
                elif isinstance(wave_data, torch.Tensor):
                    # 确保Torch张量有正确的维度和类型
                    tensor_data = wave_data.float()  # 转换为float32类型
                    
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
                        # 如果第一维很大，可能是颠倒的，尝试转置
                        tensor_data = tensor_data.transpose(0, 1)
                        self.log(f"转置后形状: {tensor_data.shape}")
                    
                    # 记录第一个有效片段的形状
                    if first_segment_shape is None:
                        # 确保不超过2个通道（通常为单声道或立体声）
                        first_segment_shape = min(tensor_data.shape[0], 2)
                    
                    # 确保通道数一致且合理（不超过2个通道）
                    if tensor_data.shape[0] != first_segment_shape:
                        self.log(f"调整角色 {role_name} 的音频通道数从 {tensor_data.shape[0]} 到 {first_segment_shape}")
                        if tensor_data.shape[0] < first_segment_shape:
                            # 如果通道数少，复制已有通道到指定大小
                            tensor_data = tensor_data.repeat(first_segment_shape // tensor_data.shape[0] + 1, 1)[:first_segment_shape]
                        else:
                            # 如果通道数多，只保留需要的通道
                            tensor_data = tensor_data[:first_segment_shape]
                    
                    processed_segments.append(tensor_data)
                else:
                    self.log(f"警告: 角色 {role_name} 的音频数据类型不支持: {type(wave_data)}，尝试转换为tensor")
                    try:
                        # 尝试将未知类型转换为tensor
                        tensor_data = torch.tensor(wave_data, dtype=torch.float32)
                        if tensor_data.dim() == 1:
                            tensor_data = tensor_data.unsqueeze(0)
                        elif tensor_data.dim() == 3:
                            tensor_data = tensor_data[0]
                        
                        # 检查并修正张量维度顺序
                        if tensor_data.shape[0] > 10:  # 通常通道数不会超过10
                            self.log(f"警告: 检测到张量维度可能颠倒，尝试转置 - 原始形状: {tensor_data.shape}")
                            tensor_data = tensor_data.transpose(0, 1)
                            self.log(f"转置后形状: {tensor_data.shape}")
                        
                        # 记录第一个有效片段的形状
                        if first_segment_shape is None:
                            # 确保不超过2个通道（通常为单声道或立体声）
                            first_segment_shape = min(tensor_data.shape[0], 2)
                        
                        # 确保通道数一致且合理
                        if tensor_data.shape[0] != first_segment_shape:
                            if tensor_data.shape[0] < first_segment_shape:
                                tensor_data = tensor_data.repeat(first_segment_shape // tensor_data.shape[0] + 1, 1)[:first_segment_shape]
                            else:
                                tensor_data = tensor_data[:first_segment_shape]
                        
                        processed_segments.append(tensor_data)
                    except:
                        self.log(f"错误: 无法将角色 {role_name} 的音频数据转换为tensor")
                        continue
            
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
            self.log(f"合并多角色音频出错: {e}")
            import traceback
            traceback.print_exc()
            
            # 如果合并失败，尝试返回第一个成功生成的角色音频
            if role_audio_segments:
                self.log("尝试使用第一个角色的音频作为备选输出")
                try:
                    role_name, wave_data, sr = role_audio_segments[0]
                    fallback_output = output_path.replace(".wav", "_fallback.wav")
                    
                    # 确保数据格式正确
                    if isinstance(wave_data, np.ndarray):
                        tensor_data = torch.tensor(wave_data, dtype=torch.float32)
                        if tensor_data.dim() == 1:
                            tensor_data = tensor_data.unsqueeze(0)
                        elif tensor_data.dim() == 3:
                            tensor_data = tensor_data[0]  # 取第一个维度
                        
                        # 检查并修正张量维度顺序
                        if tensor_data.shape[0] > 10:  # 通常通道数不会超过10
                            self.log(f"警告: 备选输出检测到张量维度可能颠倒，尝试转置 - 原始形状: {tensor_data.shape}")
                            tensor_data = tensor_data.transpose(0, 1)
                    elif isinstance(wave_data, torch.Tensor):
                        tensor_data = wave_data.float()
                        if tensor_data.dim() == 1:
                            tensor_data = tensor_data.unsqueeze(0)
                        elif tensor_data.dim() == 3:
                            tensor_data = tensor_data[0]  # 取第一个维度
                        
                        # 检查并修正张量维度顺序
                        if tensor_data.shape[0] > 10:  # 通常通道数不会超过10
                            self.log(f"警告: 备选输出检测到张量维度可能颠倒，尝试转置 - 原始形状: {tensor_data.shape}")
                            tensor_data = tensor_data.transpose(0, 1)
                    else:
                        raise ValueError(f"不支持的数据类型: {type(wave_data)}")
                    
                    # 确保tensor是2D的且通道数合理
                    if tensor_data.shape[0] > 2:
                        self.log(f"警告: 备选输出通道数 {tensor_data.shape[0]} 异常大，重置为单通道")
                        # 如果通道数异常大，可能是颠倒的，取第一列作为单通道
                        tensor_data = tensor_data[:1]
                    
                    self.log(f"备选输出音频的形状: {tensor_data.shape}")
                    
                    # 转换为int16并保存
                    tensor_data_int16 = tensor_data.to(torch.int16)
                    torchaudio.save(fallback_output, tensor_data_int16, sr)
                    self.log(f"已生成备选输出: {fallback_output}")
                    return fallback_output
                except Exception as e:
                    self.log(f"生成备选输出失败: {e}")
                    import traceback
                    traceback.print_exc()
                    pass
            
            return None 