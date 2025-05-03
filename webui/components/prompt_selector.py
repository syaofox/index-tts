#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
提示选择器组件
提供对prompts目录中模板的浏览和选择
"""

import gradio as gr
from typing import List, Optional


class PromptSelector:
    """提示选择器组件类"""
    
    def __init__(self, file_service):
        """初始化提示选择器组件
        
        Args:
            file_service: 文件服务实例
        """
        self.file_service = file_service
    
    def get_prompt_choices(self) -> List[str]:
        """获取提示模板选项列表
        
        Returns:
            提示模板名称列表
        """
        return self.file_service.get_prompt_names()
    
    def create_dropdown_component(self, 
                                 label: str = "选择提示模板") -> gr.Dropdown:
        """创建提示模板选择下拉框
        
        Args:
            label: 组件标签
        
        Returns:
            Gradio下拉框组件
        """
        choices = self.get_prompt_choices()
        
        return gr.Dropdown(
            choices=choices,
            label=label,
            interactive=True,
            value=choices[0] if choices else None
        )
    
    def create_gallery_component(self, 
                               label: str = "选择提示模板",
                               columns: int = 4) -> gr.Gallery:
        """创建提示模板选择图库（预留功能）
        
        Args:
            label: 组件标签
            columns: 列数
        
        Returns:
            Gradio图库组件
        """
        # 这个功能是为将来的扩展预留的
        # 目前提示模板没有对应的图像，但未来可能会添加
        return gr.Gallery(
            label=label,
            columns=columns,
            show_label=True,
            elem_id="prompt_gallery"
        )
    
    def refresh_prompts(self) -> List[str]:
        """刷新提示模板列表
        
        Returns:
            更新后的提示模板名称列表
        """
        return self.get_prompt_choices() 