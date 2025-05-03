#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
配置工具模块
提供配置加载和保存功能
"""

import os
import json
import yaml
from typing import Dict, Any, Optional


def load_json_config(config_path: str, default_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """加载JSON格式配置文件
    
    Args:
        config_path: 配置文件路径
        default_config: 默认配置，当文件不存在时返回
    
    Returns:
        配置字典
    """
    if default_config is None:
        default_config = {}
    
    if not os.path.exists(config_path):
        return default_config
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"加载JSON配置文件失败: {e}")
        return default_config


def save_json_config(config_data: Dict[str, Any], config_path: str) -> bool:
    """保存配置到JSON文件
    
    Args:
        config_data: 配置数据
        config_path: 配置文件路径
    
    Returns:
        是否成功保存
    """
    try:
        # 确保目录存在
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=4, ensure_ascii=False)
        
        return True
    except Exception as e:
        print(f"保存JSON配置文件失败: {e}")
        return False


def load_yaml_config(config_path: str, default_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """加载YAML格式配置文件
    
    Args:
        config_path: 配置文件路径
        default_config: 默认配置，当文件不存在时返回
    
    Returns:
        配置字典
    """
    if default_config is None:
        default_config = {}
    
    if not os.path.exists(config_path):
        return default_config
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"加载YAML配置文件失败: {e}")
        return default_config


def save_yaml_config(config_data: Dict[str, Any], config_path: str) -> bool:
    """保存配置到YAML文件
    
    Args:
        config_data: 配置数据
        config_path: 配置文件路径
    
    Returns:
        是否成功保存
    """
    try:
        # 确保目录存在
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)
        
        return True
    except Exception as e:
        print(f"保存YAML配置文件失败: {e}")
        return False


def merge_configs(base_config: Dict[str, Any], override_config: Dict[str, Any]) -> Dict[str, Any]:
    """合并配置
    
    Args:
        base_config: 基础配置
        override_config: 覆盖配置
    
    Returns:
        合并后的配置
    """
    result = base_config.copy()
    
    for key, value in override_config.items():
        # 如果是字典，递归合并
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_configs(result[key], value)
        else:
            result[key] = value
    
    return result 