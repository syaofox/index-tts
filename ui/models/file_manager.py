"""文件管理模型
处理音频文件管理、临时文件创建和清理等功能。
"""

import os
import time
import uuid
import traceback
from typing import Optional


class FileManager:
    """文件管理器类
    负责管理音频文件、生成输出路径等
    """
    
    @staticmethod
    def generate_output_path(prefix="output") -> str:
        """
        生成默认输出路径
        
        Args:
            prefix: 文件名前缀
            
        Returns:
            str: 生成的输出文件路径
        """
        # 创建输出目录（如果不存在）
        output_dir = "outputs"
        FileManager.ensure_dir_exists(output_dir)
        
        # 为输出文件生成一个带时间戳的文件名
        timestamp = time.strftime("%Y%m%d%H%M%S", time.localtime())
        return os.path.join(output_dir, f"{prefix}_{timestamp}.wav")
    
    @staticmethod
    def ensure_dir_exists(dir_path):
        """
        确保目录存在，如果不存在则创建
        
        Args:
            dir_path: 目录路径
        """
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
    
    @staticmethod
    def generate_temp_id():
        """
        生成唯一的临时ID
        
        Returns:
            str: UUID字符串
        """
        return str(uuid.uuid4())
    
    @staticmethod
    def generate_temp_path(base_dir="temp", extension=".wav"):
        """
        生成临时文件路径
        
        Args:
            base_dir: 临时文件目录
            extension: 文件扩展名
            
        Returns:
            str: 临时文件路径
        """
        # 确保临时目录存在
        FileManager.ensure_dir_exists(base_dir)
        
        # 生成唯一文件名
        temp_id = FileManager.generate_temp_id()
        return os.path.join(base_dir, f"temp_{temp_id}{extension}")
    
    @staticmethod
    def get_partial_output_path(original_path, suffix="_部分"):
        """
        基于原始输出路径生成部分输出路径
        
        Args:
            original_path: 原始输出路径
            suffix: 添加的后缀
            
        Returns:
            str: 部分输出路径
        """
        if not original_path:
            return FileManager.generate_output_path(prefix="partial")
            
        # 分离文件名和扩展名
        base_filename = os.path.splitext(os.path.basename(original_path))[0]
        dirname = os.path.dirname(original_path)
        
        # 创建新路径
        return os.path.join(dirname, f"{base_filename}{suffix}.wav")
    
    @staticmethod
    def cleanup_temp_files(temp_files):
        """
        清理临时文件
        
        Args:
            temp_files: 临时文件路径列表
        """
        try:
            for file_path in temp_files:
                if os.path.exists(file_path):
                    os.remove(file_path)
        except Exception as e:
            print(f"清理临时文件出错: {str(e)}")
    
    @staticmethod
    def is_valid_audio_file(file_path):
        """
        检查是否为有效的音频文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            bool: 是否为有效音频文件
        """
        return (file_path and os.path.exists(file_path) and 
                os.path.isfile(file_path) and os.path.getsize(file_path) > 0) 