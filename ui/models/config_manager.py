"""配置管理模型
负责加载、缓存和管理应用程序的各种配置。
"""

import os
import time
from typing import List, Tuple

from ui.models.text_processor import TextProcessor


class ConfigManager:
    """配置管理器类
    负责处理配置文件的加载和缓存
    """
    # 类级别的配置缓存
    _replace_rules_cache = []  # 缓存的替换规则
    _config_last_modified = 0  # 配置文件最后修改时间
    
    @classmethod
    def load_replace_rules(cls, config_path):
        """
        加载文本替换规则，根据文件修改时间决定是否使用缓存
        
        Args:
            config_path: 配置文件路径
            
        Returns:
            list: 替换规则列表，格式为[(search_str, replace_from, replace_to), ...]
        """
        if not os.path.exists(config_path):
            return []
            
        # 获取文件最后修改时间
        current_mtime = os.path.getmtime(config_path)
        
        # 检查是否需要重新加载
        if current_mtime > cls._config_last_modified or not cls._replace_rules_cache:
            rules = TextProcessor.load_replace_rules_from_file(config_path)
            # 更新类级别的缓存
            cls._replace_rules_cache = rules.copy()
            cls._config_last_modified = current_mtime
            print(f"配置文件已更新，重新加载 {len(rules)} 条规则")
            return rules
        else:
            # 使用缓存的规则
            print(f"使用缓存的 {len(cls._replace_rules_cache)} 条替换规则")
            return cls._replace_rules_cache.copy()
    
    @staticmethod
    def get_config_path(config_name, default_path="config"):
        """
        获取配置文件的完整路径
        
        Args:
            config_name: 配置文件名
            default_path: 默认配置目录
            
        Returns:
            str: 配置文件的完整路径
        """
        return os.path.join(default_path, config_name) 