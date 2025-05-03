#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文件服务模块
处理文件的读写、保存和加载
"""

import os
import glob
import shutil
from typing import List, Optional


class FileService:
    """文件服务类，处理文件管理"""
    
    def __init__(self, prompts_dir: str, outputs_dir: str):
        """初始化文件服务
        
        Args:
            prompts_dir: 提示模板目录
            outputs_dir: 输出目录
        """
        self.prompts_dir = prompts_dir
        self.outputs_dir = outputs_dir
    
    def ensure_directories(self):
        """确保必要的目录存在"""
        os.makedirs(self.prompts_dir, exist_ok=True)
        os.makedirs(self.outputs_dir, exist_ok=True)
        os.makedirs(os.path.join(self.outputs_dir, "tasks"), exist_ok=True)
    
    def get_prompt_files(self, ext: Optional[str] = ".pickle") -> List[str]:
        """获取提示模板文件列表
        
        Args:
            ext: 文件扩展名，默认为.pickle
        
        Returns:
            提示模板文件名列表（不含路径）
        """
        pattern = os.path.join(self.prompts_dir, f"*{ext}")
        files = glob.glob(pattern)
        return [os.path.basename(f) for f in files]
    
    def get_prompt_names(self) -> List[str]:
        """获取提示模板名称列表（不含扩展名）
        
        Returns:
            提示模板名称列表
        """
        files = self.get_prompt_files()
        return [os.path.splitext(f)[0] for f in files]
    
    def get_prompt_path(self, prompt_name: str) -> str:
        """获取提示模板的完整路径
        
        Args:
            prompt_name: 提示模板名称，可以包含或不包含扩展名
        
        Returns:
            提示模板的完整路径
        """
        # 检查是否已包含扩展名
        if prompt_name.endswith('.pickle'):
            filename = prompt_name
        else:
            filename = f"{prompt_name}.pickle"
        
        return os.path.join(self.prompts_dir, filename)
    
    def save_file(self, source_path: str, target_dir: Optional[str] = None) -> str:
        """保存文件到指定目录
        
        Args:
            source_path: 源文件路径
            target_dir: 目标目录，默认为输出目录
        
        Returns:
            保存后的文件路径
        """
        if not target_dir:
            target_dir = self.outputs_dir
        
        # 确保目标目录存在
        os.makedirs(target_dir, exist_ok=True)
        
        # 获取文件名
        filename = os.path.basename(source_path)
        target_path = os.path.join(target_dir, filename)
        
        # 复制文件
        shutil.copy2(source_path, target_path)
        
        return target_path
    
    def delete_file(self, file_path: str) -> bool:
        """删除文件
        
        Args:
            file_path: 文件路径
        
        Returns:
            是否成功删除
        """
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                return True
            return False
        except Exception as e:
            print(f"删除文件失败: {e}")
            return False 