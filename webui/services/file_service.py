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
        self._prompt_names_cache = None  # 添加内部缓存
    
    def ensure_directories(self):
        """确保必要的目录存在"""
        os.makedirs(self.prompts_dir, exist_ok=True)
        os.makedirs(self.outputs_dir, exist_ok=True)
    
    def get_prompt_files(self, exts: Optional[List[str]] = None) -> List[str]:
        """获取提示模板文件列表
        
        Args:
            exts: 文件扩展名列表，默认为常见音频格式
        
        Returns:
            提示模板文件名列表（不含路径）
        """
        if exts is None:
            exts = [".wav", ".mp3", ".flac", ".ogg"]
            
        files = []
        for ext in exts:
            pattern = os.path.join(self.prompts_dir, f"*{ext}")
            files.extend(glob.glob(pattern))
        return [os.path.basename(f) for f in files]
    
    def get_output_audio_files(self, exts: Optional[List[str]] = None) -> List[str]:
        """获取输出目录中所有音频文件的列表
        
        Args:
            exts: 文件扩展名列表，默认为常见音频格式
        
        Returns:
            输出目录中音频文件的完整路径列表和文件名列表的元组
        """
        if exts is None:
            exts = [".wav", ".mp3", ".flac", ".ogg"]
            
        files = []
        for ext in exts:
            pattern = os.path.join(self.outputs_dir, f"*{ext}")
            files.extend(glob.glob(pattern))
        
        # 按修改时间降序排序，使最新的文件在前面
        files.sort(key=os.path.getmtime, reverse=True)
        
        # 返回完整路径和文件名的元组
        file_paths = files
        file_names = [os.path.basename(f) for f in files]
        
        return file_paths, file_names
    
    def refresh_cache(self):
        """刷新预设名称缓存"""
        self._prompt_names_cache = None
    
    def update_prompt_names(self, new_names: List[str]):
        """更新预设名称列表缓存
        
        Args:
            new_names: 新的预设名称列表
        """
        if self._prompt_names_cache is None:
            # 如果缓存为空，初始化它
            self._prompt_names_cache = self.get_prompt_names_internal()
        
        # 添加新名称到缓存中
        for name in new_names:
            if name not in self._prompt_names_cache:
                self._prompt_names_cache.append(name)
    
    def get_prompt_names_internal(self) -> List[str]:
        """获取提示模板名称列表（内部实现）
        
        Returns:
            提示模板名称列表
        """
        files = self.get_prompt_files()
        characters = set()
       
        for filename in files:
            # 从文件名中提取角色名（第一个下划线前的部分）
            parts = filename.split("_", 1)
            if len(parts) > 1:
                character_name = parts[0]
                characters.add(character_name)
        
        return list(characters)
    
    def get_prompt_names(self) -> List[str]:
        """获取提示模板名称列表（角色名，从文件名提取）
        
        Returns:
            提示模板名称列表
        """
        # 如果有缓存，直接返回
        if self._prompt_names_cache is not None:
            return self._prompt_names_cache
        
        # 否则从文件系统中获取并缓存结果
        self._prompt_names_cache = self.get_prompt_names_internal()
        return self._prompt_names_cache
    
    def get_prompt_path(self, prompt_name: str) -> str:
        """获取提示模板的完整路径
        
        Args:
            prompt_name: 角色名称
        
        Returns:
            角色音频文件的完整路径
        """
        # 查找匹配的文件模式
        pattern = os.path.join(self.prompts_dir, f"{prompt_name}_*")
        matching_files = glob.glob(pattern)
        
        if matching_files:
            # 返回第一个匹配的文件
            return matching_files[0]
        else:
            # 如果没有找到匹配的文件，返回一个可能的路径（供错误处理）
            return os.path.join(self.prompts_dir, f"{prompt_name}_not_found")
    
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