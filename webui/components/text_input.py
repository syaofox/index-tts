#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文本输入组件
处理用户输入的目标文本
"""

import gradio as gr
from typing import Optional, Dict, Any


class TextInput:
    """文本输入组件类"""
    
    def __init__(self):
        """初始化文本输入组件"""
        pass
    
    def create_text_area(self, 
                        label: str = "输入文本",
                        placeholder: Optional[str] = None,
                        lines: int = 5) -> gr.TextArea:
        """创建文本输入区域
        
        Args:
            label: 组件标签
            placeholder: 占位文本
            lines: 行数
        
        Returns:
            Gradio文本区域组件
        """
        if placeholder is None:
            placeholder = """请输入需要转换为语音的文本...
多角色使用说明：
可以使用<角色名>的格式来指定不同角色的对话。例如：

<角色1>
这是角色1说的话。
<角色2>
这是角色2的回应。
            
注意：

角色名必须与预先保存的角色名称完全匹配
每个角色的文本可以包含多行
空行会自动添加停顿"""
        
        return gr.TextArea(
            label=label,
            placeholder=placeholder,
            lines=lines,
            max_lines=20,
            interactive=True
        )
    
    def create_text_box(self, 
                      label: str = "输入文本",
                      placeholder: Optional[str] = None) -> gr.Textbox:
        """创建单行文本输入框
        
        Args:
            label: 组件标签
            placeholder: 占位文本
        
        Returns:
            Gradio文本框组件
        """
        if placeholder is None:
            placeholder = "输入短文本..."
        
        return gr.Textbox(
            label=label,
            placeholder=placeholder,
            interactive=True
        )
    
    @staticmethod
    def update_component(value: Optional[str] = None,
                        placeholder: Optional[str] = None,
                        interactive: Optional[bool] = None) -> Dict[str, Any]:
        """更新文本组件的状态
        
        Args:
            value: 文本内容
            placeholder: 占位文本
            interactive: 是否可交互
        
        Returns:
            用于gr.update的参数字典
        """
        update_args = {}
        
        if value is not None:
            update_args["value"] = value
        
        if placeholder is not None:
            update_args["placeholder"] = placeholder
        
        if interactive is not None:
            update_args["interactive"] = interactive
        
        return gr.update(**update_args)
    
    @staticmethod
    def validate_text(text: str) -> bool:
        """验证文本是否有效
        
        Args:
            text: 输入文本
        
        Returns:
            文本是否有效
        """
        return text is not None and len(text.strip()) > 0 