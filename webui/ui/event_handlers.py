#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
IndexTTS WebUI 事件处理模块
处理用户界面的事件响应
"""

import os
import time
import gradio as gr
import threading
import queue
import shutil
import re

# 导入TextProcessor类
try:
    from webui.utils.text_processor import TextProcessor
except ImportError:
    # 尝试备用导入路径
    from utils.text_processor import TextProcessor


class EventHandlers:
    """事件处理类"""
    
    def __init__(self, enhanced_tts_service, character_manager, settings, file_service):
        """
        初始化事件处理器
        
        Args:
            enhanced_tts_service: 增强的TTS服务
            character_manager: 角色管理器
            settings: 应用设置
            file_service: 文件服务
        """
        self.enhanced_tts_service = enhanced_tts_service
        self.character_manager = character_manager
        self.settings = settings
        self.file_service = file_service
        
        # 日志相关变量
        self.logs = ""
        self.log_queue = queue.Queue()
        self.is_processing = False
        
        # 设置TTS服务的日志回调
        self.enhanced_tts_service.set_log_callback(self.enqueue_log)
        
    def enqueue_log(self, message):
        """
        将日志添加到队列
        
        Args:
            message: 日志消息
        """
        # 添加时间戳
        timestamp = time.strftime("[%H:%M:%S]", time.localtime())
        formatted_message = f"{timestamp} {message}"
        self.log_queue.put(formatted_message)
        
    def update_logs(self, message):
        """
        更新日志内容
        
        Args:
            message: 新的日志消息
            
        Returns:
            str: 更新后的日志内容
        """
        # 添加到日志文本
        self.logs += message + "\n"
        
        # 如果日志太长，保留最后的内容
        max_chars = 10000
        if len(self.logs) > max_chars:
            self.logs = self.logs[-max_chars:]
        
        return self.logs
        
    def generate_audio(self, prompt_path, text, mode, punct_chars_input, pause_time_input):
        """
        生成音频的回调函数，使用生成器实时更新日志
        
        Args:
            prompt_path: 提示音频文件路径
            text: 输入文本
            mode: 推理模式，"普通推理"或"批次推理"
            punct_chars_input: 分割标点符号
            pause_time_input: 停顿时间(秒)
            
        Yields:
            tuple: (音频更新, 日志更新)
        """
        # 清空日志
        self.logs = ""
        self.log_queue = queue.Queue()
        self.is_processing = True
        self.result = None  # 存储生成结果
        
        # 输出初始日志
        self.enqueue_log("开始生成语音...")
        yield gr.update(value=None, visible=True), self.update_logs(self.log_queue.get())
        
        if not text:
            self.enqueue_log("错误: 文本为空")
            self.is_processing = False
            yield gr.update(value=None, visible=True), self.update_logs(self.log_queue.get())
            return
        
        # 记录基本参数
        self.enqueue_log(f"推理模式: {mode}")
        yield gr.update(value=None, visible=True), self.update_logs(self.log_queue.get())
        
        self.enqueue_log(f"分割标点: {punct_chars_input}")
        yield gr.update(value=None, visible=True), self.update_logs(self.log_queue.get())
        
        self.enqueue_log(f"停顿时间: {pause_time_input}秒")
        yield gr.update(value=None, visible=True), self.update_logs(self.log_queue.get())
        
        # 解析文本，确定是单人还是多人推理
        is_multi_character, character_text_segments = TextProcessor.parse_multi_role_text(text)
        print(f"解析结果: {is_multi_character}, {character_text_segments}")
        
        self.enqueue_log(f"推理类型: {'多人对话' if is_multi_character else '单人语音'}")
        yield gr.update(value=None, visible=True), self.update_logs(self.log_queue.get())
        
        # 创建后台线程来生成音频，这样可以在生成过程中更新日志
        output_path = os.path.join(self.settings.outputs_dir, "output.wav")
        
        generation_thread = threading.Thread(
            target=self._run_generation,
            args=(prompt_path, text, output_path, mode, punct_chars_input, pause_time_input, is_multi_character, character_text_segments)
        )
        generation_thread.daemon = True
        generation_thread.start()
        
        # 等待生成完成或更新日志
        while self.is_processing or not self.log_queue.empty():
            try:
                # 非阻塞方式获取日志
                log_message = self.log_queue.get_nowait()
                # 更新日志并返回
                yield gr.update(value=self.result, visible=True), self.update_logs(log_message)
            except queue.Empty:
                # 如果队列为空且还在处理，等待一段时间
                if self.is_processing:
                    time.sleep(0.1)
                    continue
                break
        
        # 生成完成后，提示用户刷新历史音频列表
        try:
            # 如果生成成功且有结果
            if self.result:
                self.enqueue_log("生成完成！点击【刷新列表】后，在下拉框中选择音频文件即可播放。")
        except Exception as e:
            self.enqueue_log(f"刷新历史音频列表时出错: {e}")
        
        # 生成完成后，返回最终结果
        yield gr.update(value=self.result, visible=True), self.logs
    
    
    
    def _find_character_prompt(self, character_name):
        """
        根据角色名查找对应的提示音频文件路径
        
        Args:
            character_name: 角色名称
            
        Returns:
            str: 提示音频文件路径，如果找不到则返回None
        """
        if not character_name:
            return None
        
        try:
            # 尝试加载角色信息
            character_data = self.character_manager.load_character(character_name)
            
            if character_data and "voice_path" in character_data:
                # 返回角色音频文件路径
                return character_data["voice_path"]
            else:
                # 如果字符数据提取失败，尝试直接使用文件服务获取音频路径
                prompt_file = self.file_service.get_prompt_path(character_name)
                if os.path.exists(prompt_file) and not prompt_file.endswith("_not_found"):
                    return prompt_file
        except Exception as e:
            self.enqueue_log(f"查找角色 '{character_name}' 的提示音频时出错: {e}")
        
        return None
        
    def _run_generation(self, prompt_path, text, output_path, mode, punct_chars, pause_time, is_multi_character, character_text_segments):
        """
        在后台线程运行音频生成
        
        Args:
            prompt_path: 提示音频文件路径
            text: 输入文本
            output_path: 输出音频文件路径
            mode: 推理模式
            punct_chars: 分割标点符号
            pause_time: 停顿时间(秒)
            is_multi_character: 是否多人推理
            character_text_segments: 角色文本分段列表
        """
        try:
            if not is_multi_character:
                # 单人推理
                self._generate_single_character_audio(prompt_path, text, output_path, mode, punct_chars, pause_time)
            else:
                # 多人推理
                self._generate_multi_character_audio(character_text_segments, output_path, mode, punct_chars, pause_time)
            
        except Exception as e:
            self.enqueue_log(f"生成过程发生错误: {str(e)}")
        finally:
            # 标记处理完成
            self.is_processing = False
    
    def _generate_single_character_audio(self, prompt_path, text, output_path, mode, punct_chars, pause_time):
        """
        生成单人角色音频
        
        Args:
            prompt_path: 提示音频文件路径
            text: 输入文本
            output_path: 输出音频文件路径
            mode: 推理模式
            punct_chars: 分割标点符号
            pause_time: 停顿时间(秒)
        """
        if not prompt_path:
            self.enqueue_log("错误: 提示音频为空")
            return
        
        # 检查提示音频文件路径
        if isinstance(prompt_path, str) and not os.path.exists(prompt_path):
            try:
                # 尝试提取角色名（如果是格式化的角色文件名）
                basename = os.path.basename(prompt_path)
                parts = basename.split("_", 1)
                if len(parts) > 1:
                    character_name = parts[0]
                else:
                    character_name = os.path.splitext(basename)[0]
                
                self.enqueue_log(f"正在查找角色 '{character_name}' 的音频文件")
                
                # 使用文件服务查找角色音频文件
                prompt_path = self.file_service.get_prompt_path(character_name)
                
                if not os.path.exists(prompt_path) or prompt_path.endswith("_not_found"):
                    self.enqueue_log(f"无法找到角色 '{character_name}' 的音频文件")
                    return
                else:
                    self.enqueue_log(f"已找到角色音频: {prompt_path}")
            except Exception as e:
                self.enqueue_log(f"处理提示文件路径时出错: {e}")
                return
        
        # 使用增强的TTS服务生成音频
        mode_str = "normal" if mode == "普通推理" else "fast"
        self.result = self.enhanced_tts_service.generate(
            prompt_path, text, output_path, 
            mode_str, 
            punct_chars, 
            pause_time
        )
        
        if self.result:
            self.enqueue_log(f"单人语音生成完成: {self.result}")
        else:
            self.enqueue_log("单人语音生成失败")
    
    def _generate_multi_character_audio(self, character_text_segments, final_output_path, mode, punct_chars, pause_time):
        """
        生成多人对话音频
        
        Args:
            character_text_segments: 角色文本分段列表，格式为[(角色名1, 文本1), (角色名2, 文本2), ...]
            final_output_path: 最终输出音频文件路径
            mode: 推理模式
            punct_chars: 分割标点符号
            pause_time: 停顿时间(秒)
        """
        self.enqueue_log(f"多人对话包含 {len(character_text_segments)} 个语音段")
        
        mode_str = "normal" if mode == "普通推理" else "fast"
        
        self.enqueue_log(f"开始生成多角色语音，使用模式: {mode_str}，标点符号: '{punct_chars}'，停顿时间: {pause_time}秒")
        
        try:
            # 直接使用增强型TTS服务的多角色生成功能
            result = self.enhanced_tts_service.generate_multi_role_from_segments(
                character_text_segments,
                final_output_path,
                mode_str,
                punct_chars,
                pause_time
            )
            
            if result:
                self.enqueue_log(f"多人对话音频生成完成: {result}")
                self.result = result
            else:
                self.enqueue_log("多人对话音频生成失败")
                
        except Exception as e:
            self.enqueue_log(f"生成多角色音频时出错: {e}")
            import traceback
            traceback.print_exc()
            # 如果生成失败，结果为None
            self.result = None
    
    def update_prompt_from_dropdown(self, prompt_name):
        """
        当从下拉列表选择提示时，加载相应的音频文件
        
        Args:
            prompt_name: 选中的提示名称
            
        Returns:
            gr.update: Gradio界面更新对象
        """
        if not prompt_name or prompt_name == "无":
            return gr.update(value=None)
        
        try:
            # 获取当前有效的预设列表
            valid_presets = self.file_service.get_prompt_names()
            
            # 检查选择的预设是否在有效列表中
            if prompt_name not in valid_presets:
                # 对于自定义输入的值，不显示警告，直接返回空值
                # 当用户点击保存按钮后，会创建新预设
                return gr.update(value=None)
            
            # 使用CharacterManager加载角色音频文件
            character_data = self.character_manager.load_character(prompt_name)
            
            if character_data and "voice_path" in character_data:
                # 返回角色音频文件路径
                return gr.update(value=character_data["voice_path"])
            else:
                # 如果字符数据提取失败，尝试直接使用文件服务获取音频路径
                prompt_file = self.file_service.get_prompt_path(prompt_name)
                return gr.update(value=prompt_file)
        except Exception as e:
            print(f"加载提示音频出错: {e}")
            return gr.update(value=None)
    
    def save_preset(self, prompt_audio, current_preset_name):
        """
        保存当前参考音频为预设
        
        Args:
            prompt_audio: 参考音频文件路径
            current_preset_name: 当前选中的预设名称
            
        Returns:
            tuple: (更新后的预设下拉列表, 日志更新, 音频路径更新)
        """
        # 清空之前的日志
        self.logs = ""
        
        if not prompt_audio:
            self.logs = "错误: 没有有效的参考音频可保存"
            return gr.update(choices=["无"] + sorted(self.file_service.get_prompt_names()), value="无"), self.logs, gr.update(value=None)
        
        try:
            # 获取当前有效的预设列表
            valid_presets = self.file_service.get_prompt_names()
            
            # 决定使用哪个预设名
            if current_preset_name == "无":
                # 如果选择了"无"，使用默认前缀
                prefix = "preset"
                # 生成唯一的预设名，使用时间戳
                timestamp = time.strftime("%Y%m%d-%H%M%S")
                save_name = f"{prefix}-{timestamp}"
                self.logs = f"正在创建新预设 '{save_name}'..."
            elif current_preset_name not in valid_presets:
                # 如果输入了自定义名称（不在预设列表中），直接使用它
                # 替换下划线为连字符，避免影响角色名提取
                save_name = current_preset_name.replace("_", "-")
                self.logs = f"正在创建新预设 '{save_name}'..."
            else:
                # 如果选择了现有预设，表示要更新预设
                save_name = current_preset_name
                self.logs = f"正在更新预设 '{save_name}'..."
            
            # 确保预设目录存在
            os.makedirs(self.settings.prompts_dir, exist_ok=True)
            
            # 从原始音频路径获取音频文件名
            original_audio_filename = os.path.basename(prompt_audio)
            
            # 生成符合格式的文件名："预设名_附加信息.扩展名"
            if not original_audio_filename:
                # 如果没有原始文件名，使用一个时间戳后缀
                timestamp = time.strftime("%Y%m%d%H%M%S")
                target_filename = f"{save_name}_audio_{timestamp}.wav"
            else:
                # 确保使用正确的扩展名
                _, audio_ext = os.path.splitext(original_audio_filename)
                if not audio_ext or audio_ext.lower() not in ['.wav', '.mp3', '.ogg', '.flac']:
                    audio_ext = '.wav'  # 默认使用.wav扩展名
                
                # 使用时间戳作为附加信息，确保文件名唯一
                timestamp = time.strftime("%Y%m%d%H%M%S")
                target_filename = f"{save_name}_voice_{timestamp}{audio_ext}"
            
            # 复制音频文件到预设目录，使用正确的文件命名格式
            dest_path = os.path.join(self.settings.prompts_dir, target_filename)
            shutil.copy2(prompt_audio, dest_path)
            
            # 更新日志
            if current_preset_name == "无" or current_preset_name not in valid_presets:
                self.logs = f"成功创建新预设 '{save_name}'"
            else:
                self.logs = f"成功更新预设 '{save_name}'"
            
            # 刷新预设列表，确保包含新保存的预设
            # 由于文件操作可能需要时间生效，添加一个小延迟
            time.sleep(0.3)  # 增加延迟以确保文件系统刷新
            
            # 刷新文件服务的缓存（如果有这个方法）
            if hasattr(self.file_service, 'refresh_cache'):
                self.file_service.refresh_cache()
            
            # 再次获取最新的预设列表
            prompt_names = sorted(self.file_service.get_prompt_names())
            
            # 确保新保存的预设确实在列表中
            if save_name not in prompt_names:
                # 如果新预设不在列表中，可能是文件系统延迟，直接添加到列表中
                prompt_names.append(save_name)
                prompt_names.sort()
                # 更新文件服务的内部列表，确保下一次调用也能找到这个预设
                if hasattr(self.file_service, 'update_prompt_names'):
                    self.file_service.update_prompt_names([save_name])
            
            # 返回更新后的预设列表，并选择刚保存的预设
            updated_choices = ["无"] + prompt_names
            
            # 返回三个更新值: 下拉框更新、日志更新、音频控件更新(保持原始音频不变)
            return gr.update(choices=updated_choices, value=save_name), self.logs, gr.update(value=prompt_audio)
            
        except Exception as e:
            self.logs = f"保存预设时出错: {str(e)}"
            return gr.update(choices=["无"] + sorted(self.file_service.get_prompt_names()), value="无"), self.logs, gr.update(value=None)
    
    def refresh_presets(self):
        """
        刷新预设列表
        
        Returns:
            tuple: (更新后的预设下拉列表, 日志更新, 音频更新)
        """
        # 清空之前的日志
        self.logs = ""
        
        try:
            # 添加一个小延迟，确保文件系统操作完成
            time.sleep(0.2)
            
            # 刷新文件服务的缓存（如果有这个方法）
            if hasattr(self.file_service, 'refresh_cache'):
                self.file_service.refresh_cache()
            
            # 刷新预设列表
            prompt_names = sorted(self.file_service.get_prompt_names())
            updated_choices = ["无"] + prompt_names
            self.logs = f"已刷新预设列表，共 {len(prompt_names)} 个预设"
            return gr.update(choices=updated_choices, value="无"), self.logs, gr.update(value=None)
            
        except Exception as e:
            self.logs = f"刷新预设列表时出错: {str(e)}"
            return gr.update(choices=["无"]), self.logs, gr.update(value=None)
    
    def delete_preset(self, preset_name):
        """
        删除预设
        
        Args:
            preset_name: 要删除的预设名称
            
        Returns:
            tuple: (更新后的预设下拉列表, 日志更新, 音频路径更新)
        """
        if not preset_name or preset_name == "无":
            return gr.update(choices=self.file_service.get_prompt_names(), value="无"), "未选择预设", None
            
        try:
            # 获取提示音频文件路径
            audio_path = self.file_service.get_prompt_path(preset_name)
            
            # 检查文件是否存在
            if os.path.exists(audio_path):
                # 删除文件
                os.remove(audio_path)
                
                # 刷新缓存
                self.file_service.refresh_cache()
                
                # 获取更新后的预设列表
                preset_choices = self.file_service.get_prompt_names()
                
                return gr.update(choices=preset_choices, value="无"), f"已删除预设: {preset_name}", None
            else:
                return gr.update(choices=self.file_service.get_prompt_names(), value=preset_name), f"文件不存在: {audio_path}", None
        except Exception as e:
            return gr.update(choices=self.file_service.get_prompt_names(), value=preset_name), f"删除预设出错: {e}", None
            
    def get_history_audio_files(self):
        """
        获取输出目录中所有历史音频文件
        
        Returns:
            tuple: (文件路径列表, 文件名列表)
        """
        try:
            # 获取历史音频文件
            file_paths, file_names = self.file_service.get_output_audio_files()
            
            # 记录日志
            self.enqueue_log(f"找到 {len(file_names)} 个历史音频文件")
            
            return file_paths, file_names
        except Exception as e:
            self.enqueue_log(f"获取历史音频文件时出错: {e}")
            return [], []
            
    def play_history_audio(self, selected_file_name):
        """
        播放选定的历史音频文件
        
        Args:
            selected_file_name: 选定的音频文件名
            
        Returns:
            音频组件更新和日志更新
        """
        if not selected_file_name:
            # 下拉框可能被清空或未选择文件时，不显示提示信息，直接返回空
            return None, self.logs
            
        try:
            # 获取所有历史音频文件
            file_paths, file_names = self.file_service.get_output_audio_files()
            
            # 通过文件名找到文件路径
            file_index = file_names.index(selected_file_name)
            file_path = file_paths[file_index]
            
            # 记录日志
            self.enqueue_log(f"正在播放历史音频: {selected_file_name}")
            
            # 返回音频更新
            return file_path, self.update_logs(f"正在播放历史音频: {selected_file_name}")
        except ValueError:
            self.enqueue_log(f"找不到文件: {selected_file_name}")
            return None, self.update_logs(f"找不到文件: {selected_file_name}")
        except Exception as e:
            self.enqueue_log(f"播放历史音频时出错: {e}")
            return None, self.update_logs(f"播放历史音频时出错: {e}")
            
    def refresh_history_files(self):
        """
        刷新历史音频文件列表
        
        Returns:
            tuple: 更新后的下拉框选项和日志更新
        """
        try:
            # 获取最新的历史音频文件
            _, file_names = self.file_service.get_output_audio_files()
            
            # 记录日志
            self.enqueue_log(f"已刷新历史音频列表，共 {len(file_names)} 个文件")
            
            return gr.update(choices=file_names, value=None), self.update_logs(f"已刷新历史音频列表，共 {len(file_names)} 个文件")
        except Exception as e:
            self.enqueue_log(f"刷新历史音频列表时出错: {e}")
            return gr.update(choices=[], value=None), self.update_logs(f"刷新历史音频列表时出错: {e}") 