#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
TTS服务模块
封装IndexTTS核心功能的服务接口
"""

import os
import time
from typing import Optional, Union


class TTSService:
    """TTS服务类，封装与IndexTTS的交互"""
    
    def __init__(self, model_dir: str, config_path: str):
        """初始化TTS服务
        
        Args:
            model_dir: 模型目录
            config_path: 配置文件路径
        """
        # 延迟导入以减少启动时间
        from indextts.infer import IndexTTS
        
        self.model_dir = model_dir
        self.config_path = config_path
        
        # 初始化TTS模型
        try:
            self.tts = IndexTTS(model_dir=model_dir, cfg_path=config_path)
            self.initialized = True
        except Exception as e:
            print(f"初始化TTS模型失败: {e}")
            self.initialized = False
            self.tts = None
    
    def generate(self, 
                prompt: str, 
                text: str, 
                output_path: Optional[str] = None,
                mode: str = "normal",
                progress = None) -> Union[str, None]:
        """生成语音
        
        Args:
            prompt: 提示音频路径或模板
            text: 要转换为语音的文本
            output_path: 输出音频路径，默认None则自动生成
            mode: 推理模式，"normal"或"fast"
            progress: 进度回调，用于UI显示
        
        Returns:
            生成的音频路径或None（如果失败）
        """
        if not self.initialized or not self.tts:
            print("TTS模型未初始化")
            return None
        
        # 确保输出路径存在
        if not output_path:
            # 使用固定的"output.wav"以便上层服务可以应用自定义命名逻辑
            output_path = os.path.join("outputs", "output.wav")
        
        # 设置进度回调
        if progress:
            self.tts.gr_progress = progress
        
        try:
            # 根据模式选择推理方法
            if mode == "normal":
                output = self.tts.infer(prompt, text, output_path)
            else:
                output = self.tts.infer_fast(prompt, text, output_path)
            
            return output
        except Exception as e:
            print(f"生成语音失败: {e}")
            return None
    
    def reload_model(self):
        """重新加载模型"""
        try:
            from indextts.infer import IndexTTS
            self.tts = IndexTTS(model_dir=self.model_dir, cfg_path=self.config_path)
            self.initialized = True
            return True
        except Exception as e:
            print(f"重新加载模型失败: {e}")
            self.initialized = False
            return False 