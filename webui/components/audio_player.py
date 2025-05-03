#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
音频播放器组件
负责音频的上传、预览和播放
"""

import gradio as gr
from typing import Optional, Dict, Any


class AudioPlayer:
    """音频播放器组件类"""
    
    def __init__(self):
        """初始化音频播放器组件"""
        pass
    
    def create_upload_component(self, 
                               label: str = "音频",
                               sources: Optional[list] = None,
                               type: str = "filepath") -> gr.Audio:
        """创建音频上传组件
        
        Args:
            label: 组件标签
            sources: 音频来源列表，默认为["upload", "microphone"]
            type: 返回类型，默认为"filepath"
        
        Returns:
            Gradio音频组件
        """
        if sources is None:
            sources = ["upload", "microphone"]
        
        return gr.Audio(
            label=label,
            sources=sources,
            type=type,
            autoplay=False,  # 关闭自动播放以减少内存占用
            show_download_button=True,  # 显示下载按钮让用户保存音频
            elem_id=f"audio_upload_{label}"  # 添加唯一ID
        )
    
    def create_playback_component(self, 
                                 label: str = "音频",
                                 visible: bool = True) -> gr.Audio:
        """创建音频播放组件
        
        Args:
            label: 组件标签
            visible: 是否可见
        
        Returns:
            Gradio音频组件
        """
        return gr.Audio(
            label=label,
            visible=visible,
            autoplay=False,  # 关闭自动播放以减少内存占用
            show_download_button=True,  # 显示下载按钮让用户保存音频
            elem_id=f"audio_playback_{label}"  # 添加唯一ID
        )
    
    @staticmethod
    def update_component(value: Optional[str] = None,
                        visible: Optional[bool] = None) -> Dict[str, Any]:
        """更新音频组件的状态
        
        Args:
            value: 音频文件路径
            visible: 是否可见
        
        Returns:
            用于gr.update的参数字典
        """
        update_args = {}
        
        if value is not None:
            update_args["value"] = value
        
        if visible is not None:
            update_args["visible"] = visible
        
        return gr.update(**update_args) 