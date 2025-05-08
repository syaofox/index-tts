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
        
        if not prompt_path or not text:
            self.enqueue_log("错误: 提示音频或文本为空")
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
        
        # 如果prompt_path不是直接可用的音频文件，尝试查找对应角色的音频文件
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
                yield gr.update(value=None, visible=True), self.update_logs(self.log_queue.get())
                
                # 使用文件服务查找角色音频文件
                prompt_path = self.file_service.get_prompt_path(character_name)
                
                if not os.path.exists(prompt_path) or prompt_path.endswith("_not_found"):
                    self.enqueue_log(f"无法找到角色 '{character_name}' 的音频文件")
                    self.is_processing = False
                    yield gr.update(value=None, visible=True), self.update_logs(self.log_queue.get())
                    return
                else:
                    self.enqueue_log(f"已找到角色音频: {prompt_path}")
                    yield gr.update(value=None, visible=True), self.update_logs(self.log_queue.get())
            except Exception as e:
                self.enqueue_log(f"处理提示文件路径时出错: {e}")
                self.is_processing = False
                yield gr.update(value=None, visible=True), self.update_logs(self.log_queue.get())
                return
        
        # 使用"output.wav"作为输出路径，让enhanced_tts_service.py中的自定义命名逻辑生效
        output_path = os.path.join(self.settings.outputs_dir, "output.wav")
        
        # 创建后台线程来生成音频，这样可以在生成过程中更新日志
        generation_thread = threading.Thread(
            target=self._run_generation,
            args=(prompt_path, text, output_path, mode, punct_chars_input, pause_time_input)
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
        
        # 生成完成后，返回最终结果
        yield gr.update(value=self.result, visible=True), self.logs
        
    def _run_generation(self, prompt_path, text, output_path, mode, punct_chars, pause_time):
        """
        在后台线程运行音频生成
        
        Args:
            prompt_path: 提示音频文件路径
            text: 输入文本
            output_path: 输出音频文件路径
            mode: 推理模式
            punct_chars: 分割标点符号
            pause_time: 停顿时间(秒)
        """
        try:
            # 使用增强的TTS服务生成音频
            self.result = self.enhanced_tts_service.generate(
                prompt_path, text, output_path, 
                "normal" if mode == "普通推理" else "fast", 
                punct_chars, 
                pause_time
            )
            
            if self.result:
                self.enqueue_log(f"语音生成完成: {self.result}")
            else:
                self.enqueue_log("语音生成失败")
        except Exception as e:
            self.enqueue_log(f"生成过程发生错误: {str(e)}")
        finally:
            # 标记处理完成
            self.is_processing = False
        
    def update_prompt_from_dropdown(self, prompt_name):
        """
        当从下拉列表选择提示时，加载相应的音频文件
        
        Args:
            prompt_name: 选中的提示名称
            
        Returns:
            gr.update: Gradio界面更新对象
        """
        if not prompt_name:
            return gr.update(value=None)
        
        try:
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