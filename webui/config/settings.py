#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
IndexTTS WebUI 配置模块
包含应用的各种设置和配置项
"""

import os
import json
from dataclasses import dataclass, field


@dataclass
class Settings:
    """WebUI设置类"""
    # 服务器配置
    server_host: str = "0.0.0.0"
    server_port: int = 7777
    
    # 目录配置
    prompts_dir: str = field(default="prompts")
    outputs_dir: str = field(default="outputs")
    
    # 模型配置
    model_dir: str = field(default="checkpoints")
    config_path: str = field(default="checkpoints/config.yaml")
    
    def __post_init__(self):
        """初始化后的处理"""
        # 转换相对路径为绝对路径
        self.prompts_dir = os.path.abspath(self.prompts_dir)
        self.outputs_dir = os.path.abspath(self.outputs_dir)
        self.model_dir = os.path.abspath(self.model_dir)
        self.config_path = os.path.abspath(self.config_path)
        
        # 尝试从配置文件加载
        self.load_from_file()
    
    def load_from_file(self, config_file="webui/config/config.json"):
        """从配置文件加载设置"""
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                
                # 更新设置
                for key, value in config_data.items():
                    if hasattr(self, key):
                        setattr(self, key, value)
            except Exception as e:
                print(f"加载配置文件时出错: {e}")
    
    def save_to_file(self, config_file="webui/config/config.json"):
        """保存设置到配置文件"""
        # 创建配置目录
        os.makedirs(os.path.dirname(config_file), exist_ok=True)
        
        # 准备数据
        config_data = {
            'server_host': self.server_host,
            'server_port': self.server_port,
            'prompts_dir': self.prompts_dir,
            'outputs_dir': self.outputs_dir,
            'model_dir': self.model_dir,
            'config_path': self.config_path
        }
        
        # 保存到文件
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"保存配置文件时出错: {e}") 