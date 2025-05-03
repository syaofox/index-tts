#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
增强的TTS服务模块
提供支持文本切分和多角色的TTS服务
"""

import os
import torch
import torchaudio

# 导入相关模块
from ui.models.character_manager import CharacterManager
from ui.utils.text_processor import TextProcessor


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
            print(f"加载替换规则出错: {e}")
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
                print(f"检测到多角色文本，共 {len(role_text_pairs)} 个角色")
                return self.generate_multi_role(role_text_pairs, output_path, mode, punct_chars, pause_time)
            else:
                # 单角色处理，取出文本内容
                _, content = role_text_pairs[0]
                print(f"单角色处理，文本长度: {len(content)} 字符")
                return self.generate_with_segments(prompt_path, content, output_path, mode, punct_chars, pause_time)
        except Exception as e:
            print(f"生成语音出错: {e}")
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
            print("警告: 文本预处理后没有有效的片段")
            return None
            
        # 打印分割后的片段信息
        print(f"文本被分割为 {len(segments)} 个片段，其中BR标记 {segments.count(TextProcessor.BR_TAG)} 个")
        
        if len(segments) == 1:
            # 只有一个片段，直接使用原始服务
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
            print(f"处理片段 {i+1}/{len(segments)}: {segment[:30]}{'...' if len(segment) > 30 else ''}")
            
            # 使用原始服务生成当前片段
            try:
                self.tts_service.generate(prompt_path, segment, temp_file, mode)
                
                # 验证生成的文件有效
                if os.path.exists(temp_file) and os.path.getsize(temp_file) > 0:
                    temp_files.append(temp_file)
                    print(f"片段 {i+1} 生成成功: {temp_file}")
                else:
                    print(f"警告: 片段 {i+1} 未成功生成音频或文件大小为0")
            except Exception as e:
                print(f"处理片段 {i+1} 出错: {e}")
        
        # 检查是否有有效的临时文件
        if not temp_files:
            print("错误: 没有成功生成任何片段的音频")
            return None
            
        print(f"成功生成 {len(temp_files)} 个片段的音频，准备合并")
            
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
        
        role_audio_files = []
        
        print(f"开始处理 {len(role_text_pairs)} 个角色的文本")
        
        # 记录找不到的角色
        missing_characters = []
        
        for i, (role_name, text) in enumerate(role_text_pairs):
            print(f"处理角色 {i+1}/{len(role_text_pairs)}: {role_name}")
            
            # 角色的文本为空，跳过
            if not text.strip():
                print(f"警告: 角色 '{role_name}' 的文本为空，跳过处理")
                continue
                
            # 加载角色数据
            character_data = character_manager.load_character(role_name)
            
            if not character_data or "voice_path" not in character_data:
                print(f"警告: 无法加载角色 '{role_name}'，跳过处理")
                missing_characters.append(role_name)
                continue
            else:
                prompt_path = character_data["voice_path"]
                if not os.path.exists(prompt_path):
                    print(f"警告: 角色 '{role_name}' 的音频文件不存在: {prompt_path}")
                    missing_characters.append(role_name)
                    continue
            
            # 为当前角色生成临时输出文件
            role_output_path = os.path.join(self.temp_dir, f"{role_name}_{i}.wav")
            
            # 生成当前角色的语音
            try:
                role_audio = self.generate_with_segments(prompt_path, text, role_output_path, mode, punct_chars, pause_time)
                
                if role_audio and os.path.exists(role_audio) and os.path.getsize(role_audio) > 0:
                    role_audio_files.append(role_audio)
                    print(f"角色 '{role_name}' 的语音生成成功: {role_audio}")
                else:
                    print(f"警告: 角色 '{role_name}' 的语音生成失败")
            except Exception as e:
                print(f"处理角色 '{role_name}' 时出错: {e}")
        
        # 报告找不到的角色
        if missing_characters:
            print(f"以下角色未找到: {', '.join(missing_characters)}")
        
        if not role_audio_files:
            print("错误: 没有成功生成任何角色的语音")
            return None
            
        print(f"成功生成 {len(role_audio_files)} 个角色的语音，准备合并")
            
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
            print("错误: 没有可合并的音频文件")
            return None
            
        # 如果只有一个文件，直接返回
        if len(audio_files) == 1:
            print(f"只有一个音频文件，直接使用: {audio_files[0]}")
            import shutil
            shutil.copy2(audio_files[0], output_path)
            # 清理临时文件
            try:
                os.remove(audio_files[0])
            except Exception as e:
                print(f"删除临时文件时出错: {e}")
            return output_path
            
        try:
            # 加载所有音频文件
            waveforms = []
            sr = None
            
            # 先验证所有音频文件的有效性
            valid_audio_files = []
            for file_path in audio_files:
                if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                    valid_audio_files.append(file_path)
                else:
                    print(f"警告: 跳过无效音频文件: {file_path}")
            
            if not valid_audio_files:
                print("错误: 没有有效的音频文件可以合并")
                return None
                
            # 确保segments至少包含有效数量的非BR段落
            valid_segments = [s for s in segments if s != TextProcessor.BR_TAG and s.strip()]
            if len(valid_segments) < len(valid_audio_files):
                print(f"警告: 有效段落数({len(valid_segments)})少于音频文件数({len(valid_audio_files)})")
                # 调整segments以匹配音频文件
                segments = valid_segments
            
            print(f"开始合并 {len(valid_audio_files)} 个音频文件")
            
            file_index = 0
            for i, segment in enumerate(segments):
                if segment == TextProcessor.BR_TAG:
                    # 在空行位置添加静音
                    if sr is not None:
                        print(f"在位置 {i} 添加 {pause_time} 秒静音")
                        silence_len = int(sr * pause_time)
                        silence = torch.zeros(1, silence_len)
                        waveforms.append(silence)
                elif segment.strip():
                    # 添加当前片段的音频
                    if file_index < len(valid_audio_files):
                        try:
                            current_file = valid_audio_files[file_index]
                            print(f"加载音频文件: {current_file}")
                            waveform, sample_rate = torchaudio.load(current_file)
                            waveforms.append(waveform)
                            sr = sample_rate
                            file_index += 1
                        except Exception as e:
                            print(f"加载音频文件时出错: {e}")
            
            # 检查waveforms是否为空
            if not waveforms:
                print("错误: 没有成功加载任何音频波形")
                return None
                
            print(f"成功加载 {len(waveforms)} 个波形")
                
            # 合并所有波形
            try:
                merged_waveform = torch.cat(waveforms, dim=1)
                
                # 保存合并后的音频
                torchaudio.save(output_path, merged_waveform, sr)
                print(f"成功保存合并后的音频到: {output_path}")
                
                # 清理临时文件
                for file_path in valid_audio_files:
                    try:
                        os.remove(file_path)
                    except Exception as e:
                        print(f"删除临时文件时出错: {e}")
                        
                return output_path
            except Exception as e:
                print(f"合并音频波形时出错: {e}")
                
                # 如果合并失败，返回第一个有效文件
                if valid_audio_files:
                    print(f"合并失败，使用第一个有效文件作为结果: {valid_audio_files[0]}")
                    import shutil
                    shutil.copy2(valid_audio_files[0], output_path)
                    return output_path
                return None
                
        except Exception as e:
            print(f"合并音频文件时出错: {e}")
            import traceback
            traceback.print_exc()
            
            # 如果出错，尝试使用第一个文件
            if audio_files and os.path.exists(audio_files[0]):
                try:
                    print(f"处理出错，使用第一个文件作为结果: {audio_files[0]}")
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
            print("错误: 没有可合并的音频文件")
            return None
            
        # 如果只有一个文件，直接返回
        if len(audio_files) == 1:
            print(f"只有一个音频文件，直接使用: {audio_files[0]}")
            import shutil
            shutil.copy2(audio_files[0], output_path)
            # 清理临时文件
            try:
                os.remove(audio_files[0])
            except Exception as e:
                print(f"删除临时文件时出错: {e}")
            return output_path
            
        try:
            # 先验证所有音频文件的有效性
            valid_audio_files = []
            for file_path in audio_files:
                if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                    valid_audio_files.append(file_path)
                else:
                    print(f"警告: 跳过无效音频文件: {file_path}")
            
            if not valid_audio_files:
                print("错误: 没有有效的音频文件可以合并")
                return None
                
            print(f"开始合并 {len(valid_audio_files)} 个音频文件")
            
            # 加载所有音频文件
            waveforms = []
            sr = None
            
            for file_path in valid_audio_files:
                try:
                    print(f"加载音频文件: {file_path}")
                    waveform, sample_rate = torchaudio.load(file_path)
                    waveforms.append(waveform)
                    sr = sample_rate
                except Exception as e:
                    print(f"加载音频文件时出错: {file_path}, 错误: {e}")
            
            # 检查是否有加载成功的波形
            if not waveforms:
                print("错误: 没有成功加载任何音频波形")
                # 如果有有效文件但加载失败，尝试使用第一个文件
                if valid_audio_files:
                    print(f"尝试直接使用第一个有效文件: {valid_audio_files[0]}")
                    import shutil
                    shutil.copy2(valid_audio_files[0], output_path)
                    return output_path
                return None
                
            print(f"成功加载 {len(waveforms)} 个波形")
            
            # 合并所有波形
            try:
                merged_waveform = torch.cat(waveforms, dim=1)
                
                # 保存合并后的音频
                torchaudio.save(output_path, merged_waveform, sr)
                print(f"成功保存合并后的音频到: {output_path}")
                
                # 清理临时文件
                for file_path in valid_audio_files:
                    try:
                        os.remove(file_path)
                    except Exception as e:
                        print(f"删除临时文件时出错: {e}")
                        
                return output_path
            except Exception as e:
                print(f"合并音频波形时出错: {e}")
                
                # 如果合并失败，返回第一个有效文件
                if valid_audio_files:
                    print(f"合并失败，使用第一个有效文件作为结果: {valid_audio_files[0]}")
                    import shutil
                    shutil.copy2(valid_audio_files[0], output_path)
                    return output_path
                return None
                
        except Exception as e:
            print(f"合并音频文件时出错: {e}")
            import traceback
            traceback.print_exc()
            
            # 如果出错，尝试使用第一个文件
            if audio_files and os.path.exists(audio_files[0]):
                try:
                    print(f"处理出错，使用第一个文件作为结果: {audio_files[0]}")
                    import shutil
                    shutil.copy2(audio_files[0], output_path)
                    return output_path
                except:
                    pass
            return None 