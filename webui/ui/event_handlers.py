#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
IndexTTS WebUI 事件处理模块
处理用户界面的事件响应
"""

import os
import time
import gradio as gr


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
        
    def generate_audio(self, prompt_path, text, mode, punct_chars_input, pause_time_input):
        """
        生成音频的回调函数
        
        Args:
            prompt_path: 提示音频文件路径
            text: 输入文本
            mode: 推理模式，"普通推理"或"批次推理"
            punct_chars_input: 分割标点符号
            pause_time_input: 停顿时间(秒)
            
        Returns:
            gr.update: Gradio界面更新对象
        """
        if not prompt_path or not text:
            return gr.update(value=None, visible=True)
        
        # 确保不是直接使用pickle文件作为音频输入
        if isinstance(prompt_path, str) and prompt_path.endswith('.pickle'):
            # 从pickle文件中提取正确的音频文件路径
            try:
                prompt_path = self.file_service.get_prompt_path(os.path.basename(prompt_path).split('.')[0])
            except Exception as e:
                print(f"处理提示文件路径时出错: {e}")
                return gr.update(value=None, visible=True)
        
        output_path = os.path.join(self.settings.outputs_dir, f"spk_{int(time.time())}.wav")
        
        # 使用增强的TTS服务生成音频
        result = self.enhanced_tts_service.generate(
            prompt_path, text, output_path, 
            "normal" if mode == "普通推理" else "fast", 
            punct_chars_input, 
            pause_time_input
        )
        
        return gr.update(value=result, visible=True)
        
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
            # 使用CharacterManager加载pickle文件并提取音频
            character_data = self.character_manager.load_character(prompt_name)
            
            if character_data and "voice_path" in character_data:
                # 返回提取的音频文件路径
                return gr.update(value=character_data["voice_path"])
            else:
                # 如果字符数据提取失败，尝试直接使用文件服务获取音频路径
                prompt_file = self.file_service.get_prompt_path(prompt_name)
                return gr.update(value=prompt_file)
        except Exception as e:
            print(f"加载提示音频出错: {e}")
            return gr.update(value=None) 