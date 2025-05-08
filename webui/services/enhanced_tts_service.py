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

# 导入相关模块
from ui.models.character_manager import CharacterManager
from ui.models.text_processor import TextProcessor


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
        
        # 从配置文件加载文本替换规则
        self.replace_rules = self.load_replace_rules("webui/text_replace_config.txt")
        
        # 日志回调函数，默认为打印到控制台
        self.log_callback = print
        
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
            # 检查是否是多角色文本
            role_text_pairs = TextProcessor.parse_multi_role_text(text)
            
            if len(role_text_pairs) > 1:
                self.log(f"检测到多角色文本，共 {len(role_text_pairs)} 个角色")
                return self.generate_multi_role(role_text_pairs, output_path, mode, punct_chars, pause_time)
            else:
                # 单角色处理，取出文本内容
                _, content = role_text_pairs[0]
                self.log(f"单角色处理，文本长度: {len(content)} 字符")
                
                # 自定义文件名（如果未提供有效的路径或是默认路径）
                if not output_path or output_path.endswith("output.wav"):
                    # 从提示音频路径中提取角色名（如果可能）
                    prompt_filename = os.path.basename(prompt_path)
                    speaker_name = os.path.splitext(prompt_filename)[0]
                    
                    # 清理文本内容（取前50个字符）
                    text_sample = content.strip().replace("\n", "").replace("\r", "").replace(" ", "")
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
                
                return self.generate_with_segments(prompt_path, content, output_path, mode, punct_chars, pause_time)
        except Exception as e:
            self.log(f"生成语音出错: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def generate_with_segments(self, prompt_path, text, output_path, mode="normal", punct_chars="。？！.!?;；：:", pause_time=0.2):
        """
        按段落生成语音
        
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
        self.log(f"文本被分割为 {len(segments)} 个片段，其中BR标记 {segments.count(TextProcessor.BR_TAG)} 个")
        
        if len(segments) == 1:
            # 只有一个片段，直接使用原始服务
            self.log("只有一个文本片段，直接进行处理")
            return self.tts_service.generate(prompt_path, segments[0], output_path, mode)
        
        # 有多个片段，逐一处理并合并
        temp_files = []
        
        for i, segment in enumerate(segments):
            if segment == TextProcessor.BR_TAG:
                # 这是一个空行标记，跳过处理
                continue
                
            if not segment.strip():
                # 跳过空片段
                continue
            
            # 为当前片段创建临时文件
            temp_file = os.path.join(self.temp_dir, f"segment_{i}.wav")
            
            # 打印当前处理的片段
            self.log(f"处理片段 {i+1}/{len(segments)}: {segment[:30]}{'...' if len(segment) > 30 else ''}")
            
            # 使用原始服务生成当前片段
            try:
                self.tts_service.generate(prompt_path, segment, temp_file, mode)
                
                # 验证生成的文件有效
                if os.path.exists(temp_file) and os.path.getsize(temp_file) > 0:
                    temp_files.append(temp_file)
                    self.log(f"片段 {i+1} 生成成功: {temp_file}")
                else:
                    self.log(f"警告: 片段 {i+1} 未成功生成音频或文件大小为0")
            except Exception as e:
                self.log(f"处理片段 {i+1} 出错: {e}")
        
        # 检查是否有有效的临时文件
        if not temp_files:
            self.log("错误: 没有成功生成任何片段的音频")
            return None
            
        self.log(f"成功生成 {len(temp_files)} 个片段的音频，准备合并")
            
        # 合并所有音频文件，包括添加停顿
        return self.merge_audio_with_pauses(temp_files, segments, output_path, pause_time)
    
    def generate_multi_role(self, role_text_pairs, output_path, mode="normal", punct_chars="。？！.!?;；：:", pause_time=0.2):
        """
        处理多角色文本
        
        Args:
            role_text_pairs: [(角色名, 文本内容), ...] 格式的列表
            output_path: 输出音频文件路径
            mode: 推理模式，"normal"或"fast"
            punct_chars: 分割标点符号
            pause_time: 停顿时间(秒)
            
        Returns:
            str: 生成的音频文件路径
        """
        # 需要角色管理器来获取角色音频
        character_manager = CharacterManager("prompts")
        
        # 生成自定义的输出文件名，使用角色名和时间戳
        if not output_path or output_path.endswith("output.wav"):
            # 使用第一个角色名和总角色数
            first_role = role_text_pairs[0][0]
            combined_name = f"{first_role}"
            if len(role_text_pairs) > 1:
                combined_name += f"等{len(role_text_pairs)}人对话"
            
            # 添加时间戳
            timestamp = time.strftime("%Y%m%d%H%M%S", time.localtime())
            output_filename = f"[多角色][{timestamp}]{combined_name}"
            output_path = os.path.join("outputs", f"{output_filename}.wav")
            
            # 确保输出目录存在
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            self.log(f"已生成自定义输出文件名: {output_path}")
        
        role_audio_files = []
        
        self.log(f"开始处理 {len(role_text_pairs)} 个角色的文本")
        
        # 记录找不到的角色
        missing_characters = []
        
        for i, (role_name, text) in enumerate(role_text_pairs):
            self.log(f"处理角色 {i+1}/{len(role_text_pairs)}: {role_name}")
            
            # 角色的文本为空，跳过
            if not text.strip():
                self.log(f"警告: 角色 '{role_name}' 的文本为空，跳过处理")
                continue
                
            # 加载角色数据
            character_data = character_manager.load_character(role_name)
            
            if not character_data or "voice_path" not in character_data:
                self.log(f"警告: 无法加载角色 '{role_name}'，跳过处理")
                missing_characters.append(role_name)
                continue
            else:
                prompt_path = character_data["voice_path"]
                if not os.path.exists(prompt_path):
                    self.log(f"警告: 角色 '{role_name}' 的音频文件不存在: {prompt_path}")
                    missing_characters.append(role_name)
                    continue
            
            # 为当前角色生成临时输出文件
            role_output_path = os.path.join(self.temp_dir, f"{role_name}_{i}.wav")
            
            # 生成当前角色的语音
            try:
                role_audio = self.generate_with_segments(prompt_path, text, role_output_path, mode, punct_chars, pause_time)
                
                if role_audio and os.path.exists(role_audio):
                    role_audio_files.append(role_audio)
                    self.log(f"角色 '{role_name}' 的语音生成成功: {role_audio}")
                else:
                    self.log(f"警告: 角色 '{role_name}' 的语音生成失败")
            except Exception as e:
                self.log(f"生成角色 '{role_name}' 的语音出错: {e}")
        
        # 检查是否有成功生成的角色语音
        if not role_audio_files:
            error_msg = "错误: 没有成功生成任何角色的语音"
            if missing_characters:
                error_msg += f"，找不到以下角色: {', '.join(missing_characters)}"
            self.log(error_msg)
            return None
        
        # 报告处理结果
        self.log(f"成功生成 {len(role_audio_files)}/{len(role_text_pairs)} 个角色的语音，准备合并")
        
        # 合并所有角色的音频
        return self.merge_audio_files(role_audio_files, output_path)
    
    def merge_audio_with_pauses(self, audio_files, segments, output_path, pause_time=0.2):
        """
        合并音频文件，在段落间添加停顿
        
        Args:
            audio_files: 音频文件列表
            segments: 文本段落列表，用于确定哪些位置需要添加停顿
            output_path: 输出音频文件路径
            pause_time: 停顿时间(秒)
            
        Returns:
            str: 合并后的音频文件路径
        """
        if not audio_files:
            self.log("错误: 没有可合并的音频文件")
            return None
            
        # 如果只有一个文件，直接返回
        if len(audio_files) == 1:
            self.log(f"只有一个音频文件，直接使用: {audio_files[0]}")
            import shutil
            shutil.copy2(audio_files[0], output_path)
            # 清理临时文件
            try:
                os.remove(audio_files[0])
            except Exception as e:
                self.log(f"删除临时文件时出错: {e}")
            return output_path
            
        try:
            # 先验证所有音频文件的有效性
            valid_audio_files = []
            for file_path in audio_files:
                if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                    valid_audio_files.append(file_path)
                else:
                    self.log(f"警告: 跳过无效音频文件: {file_path}")
            
            if not valid_audio_files:
                self.log("错误: 没有有效的音频文件可以合并")
                return None
            
            self.log(f"开始合并 {len(valid_audio_files)} 个音频文件")
            
            # 创建一个映射关系，将非BR_TAG的segments位置映射到audio_files的索引
            segment_to_audio_map = {}
            audio_idx = 0
            
            for i, segment in enumerate(segments):
                if segment != TextProcessor.BR_TAG and segment.strip():
                    if audio_idx < len(valid_audio_files):
                        segment_to_audio_map[i] = audio_idx
                        audio_idx += 1
            
            if not segment_to_audio_map:
                self.log("错误: 无法建立段落和音频文件的映射关系")
                return None
            
            # 加载音频波形
            waveforms = []
            sr = None
            
            # 根据segments顺序处理，确保停顿在正确位置
            last_processed_segment_idx = -1
            
            for i, segment in enumerate(segments):
                if segment == TextProcessor.BR_TAG:
                    # 在空行位置添加较长的静音
                    if sr is not None:
                        # 空行使用更长的停顿时间
                        br_pause_time = pause_time  # 空行停顿时间是普通停顿的2倍
                        self.log(f"在空行位置 {i} 添加 {br_pause_time} 秒静音")
                        silence_len = int(sr * br_pause_time)
                        silence = torch.zeros(1, silence_len)
                        waveforms.append(silence)
                elif segment.strip() and i in segment_to_audio_map:
                    # 处理有效文本段落
                    audio_index = segment_to_audio_map[i]
                    current_file = valid_audio_files[audio_index]
                    
                    try:
                        self.log(f"加载音频文件: {current_file} (段落 {i+1})")
                        waveform, sample_rate = torchaudio.load(current_file)
                        waveforms.append(waveform)
                        sr = sample_rate
                        
                        # 在每个有效段落后添加普通停顿（除非下一个段落是BR_TAG）
                        if i + 1 < len(segments):                            
                            self.log(f"在段落 {i+1} 后添加 {pause_time} 秒停顿")
                            silence_len = int(sr * pause_time)
                            silence = torch.zeros(1, silence_len)
                            waveforms.append(silence)
                            
                    except Exception as e:
                        self.log(f"加载音频文件时出错: {e}")
                    
                    last_processed_segment_idx = i
            
            # 检查waveforms是否为空
            if not waveforms:
                self.log("错误: 没有成功加载任何音频波形")
                return None
                
            self.log(f"成功加载 {len(waveforms)} 个波形")
                
            # 合并所有波形
            try:
                merged_waveform = torch.cat(waveforms, dim=1)
                
                # 保存合并后的音频
                torchaudio.save(output_path, merged_waveform, sr)
                self.log(f"成功保存合并后的音频到: {output_path}")
                
                # 清理临时文件
                for file_path in valid_audio_files:
                    try:
                        os.remove(file_path)
                    except Exception as e:
                        self.log(f"删除临时文件时出错: {e}")
                        
                return output_path
            except Exception as e:
                self.log(f"合并音频波形时出错: {e}")
                
                # 如果合并失败，返回第一个有效文件
                if valid_audio_files:
                    self.log(f"合并失败，使用第一个有效文件作为结果: {valid_audio_files[0]}")
                    import shutil
                    shutil.copy2(valid_audio_files[0], output_path)
                    return output_path
                return None
                
        except Exception as e:
            self.log(f"合并音频文件时出错: {e}")
            import traceback
            traceback.print_exc()
            
            # 如果出错，尝试使用第一个文件
            if audio_files and os.path.exists(audio_files[0]):
                try:
                    self.log(f"处理出错，使用第一个文件作为结果: {audio_files[0]}")
                    import shutil
                    shutil.copy2(audio_files[0], output_path)
                    return output_path
                except:
                    pass
            return None
    
    def merge_audio_files(self, audio_files, output_path):
        """
        合并多个音频文件
        
        Args:
            audio_files: 音频文件列表
            output_path: 输出音频文件路径
            
        Returns:
            str: 合并后的音频文件路径
        """
        if not audio_files:
            self.log("错误: 没有可合并的音频文件")
            return None
            
        # 如果只有一个文件，直接返回
        if len(audio_files) == 1:
            self.log(f"只有一个音频文件，直接使用: {audio_files[0]}")
            import shutil
            shutil.copy2(audio_files[0], output_path)
            # 清理临时文件
            try:
                os.remove(audio_files[0])
            except Exception as e:
                self.log(f"删除临时文件时出错: {e}")
            return output_path
            
        try:
            # 先验证所有音频文件的有效性
            valid_audio_files = []
            for file_path in audio_files:
                if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                    valid_audio_files.append(file_path)
                else:
                    self.log(f"警告: 跳过无效音频文件: {file_path}")
            
            if not valid_audio_files:
                self.log("错误: 没有有效的音频文件可以合并")
                return None
                
            self.log(f"开始合并 {len(valid_audio_files)} 个音频文件")
            
            # 加载所有音频文件
            waveforms = []
            sr = None
            
            for file_path in valid_audio_files:
                try:
                    self.log(f"加载音频文件: {file_path}")
                    waveform, sample_rate = torchaudio.load(file_path)
                    waveforms.append(waveform)
                    sr = sample_rate
                except Exception as e:
                    self.log(f"加载音频文件时出错: {file_path}, 错误: {e}")
            
            # 检查是否有加载成功的波形
            if not waveforms:
                self.log("错误: 没有成功加载任何音频波形")
                # 如果有有效文件但加载失败，尝试使用第一个文件
                if valid_audio_files:
                    self.log(f"尝试直接使用第一个有效文件: {valid_audio_files[0]}")
                    import shutil
                    shutil.copy2(valid_audio_files[0], output_path)
                    return output_path
                return None
                
            self.log(f"成功加载 {len(waveforms)} 个波形")
            
            # 合并所有波形
            try:
                merged_waveform = torch.cat(waveforms, dim=1)
                
                # 保存合并后的音频
                torchaudio.save(output_path, merged_waveform, sr)
                self.log(f"成功保存合并后的音频到: {output_path}")
                
                # 清理临时文件
                for file_path in valid_audio_files:
                    try:
                        os.remove(file_path)
                    except Exception as e:
                        self.log(f"删除临时文件时出错: {e}")
                        
                return output_path
            except Exception as e:
                self.log(f"合并音频波形时出错: {e}")
                
                # 如果合并失败，返回第一个有效文件
                if valid_audio_files:
                    self.log(f"合并失败，使用第一个有效文件作为结果: {valid_audio_files[0]}")
                    import shutil
                    shutil.copy2(valid_audio_files[0], output_path)
                    return output_path
                return None
                
        except Exception as e:
            self.log(f"合并音频文件时出错: {e}")
            import traceback
            traceback.print_exc()
            
            # 如果出错，尝试使用第一个文件
            if audio_files and os.path.exists(audio_files[0]):
                try:
                    self.log(f"处理出错，使用第一个文件作为结果: {audio_files[0]}")
                    import shutil
                    shutil.copy2(audio_files[0], output_path)
                    return output_path
                except:
                    pass
            return None 