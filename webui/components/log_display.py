#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
IndexTTS WebUI 日志显示组件
在UI界面显示终端信息的组件
"""

import gradio as gr


class LogDisplay:
    """日志显示组件，用于在界面展示终端输出信息"""
    
    def __init__(self):
        """初始化日志显示组件"""
        self.logs = ""
    
    def create_log_area(self, label="处理日志"):
        """
        创建日志文本区域组件
        
        Args:
            label: 组件标签
            
        Returns:
            gr.Textbox: Gradio文本框组件
        """
        return gr.Textbox(
            value="",
            label=label,
            lines=10,
            max_lines=15,
            interactive=False,
            show_copy_button=True
        )
    
    def update_logs(self, new_log_entry):
        """
        更新日志内容
        
        Args:
            new_log_entry: 新的日志条目
            
        Returns:
            str: 更新后的日志内容
        """
        # 拼接新的日志条目，保持显示最近的日志内容
        self.logs += f"{new_log_entry}\n"
        
        # 如果日志太长，保留最后的内容
        max_chars = 10000
        if len(self.logs) > max_chars:
            self.logs = self.logs[-max_chars:]
        
        return self.logs
    
    def clear_logs(self):
        """
        清空日志内容
        
        Returns:
            str: 空字符串
        """
        self.logs = ""
        return "" 