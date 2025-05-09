"""角色管理模型
提供TTS角色的管理功能。
"""

import os
import time
import glob
import shutil


class CharacterManager:
    """角色管理类，用于管理TTS角色"""
    def __init__(self, prompt_dir="prompts"):
        self.prompt_dir = prompt_dir
        os.makedirs(prompt_dir, exist_ok=True)
    
    def save_character(self, name, voice_path):
        """保存角色（直接复制并重命名音频文件）"""
        if not name or not voice_path or not os.path.exists(voice_path):
            return False
        
        try:
            # 获取原始文件名和扩展名
            orig_filename = os.path.basename(voice_path)
            
            # 创建新的文件名格式：角色名_原文件名
            new_filename = f"{name}_{orig_filename}"
            
            # 目标路径
            target_path = os.path.join(self.prompt_dir, new_filename)
            
            # 复制文件
            shutil.copy2(voice_path, target_path)
            
            return True
        except Exception as e:
            print(f"保存角色出错: {str(e)}")
            return False
    
    def load_character(self, name):
        """加载角色数据"""
        try:
            # 查找匹配的角色文件（格式为：角色名_*.*)
            pattern = os.path.join(self.prompt_dir, f"{name}_*")
            matching_files = glob.glob(pattern)
            
            if not matching_files:
                return None
            
            # 获取第一个匹配的文件（如果有多个，使用第一个）
            voice_path = matching_files[0]
            
            # 创建角色数据结构
            character_data = {
                "name": name,
                "voice_path": voice_path,
                "original_filename": os.path.basename(voice_path),
                "created_time": os.path.getctime(voice_path)
            }
            
            return character_data
        except Exception as e:
            print(f"加载角色出错: {str(e)}")
            return None
    
    def delete_character(self, name):
        """删除角色音频文件"""
        try:
            # 查找匹配的角色文件
            pattern = os.path.join(self.prompt_dir, f"{name}_*")
            matching_files = glob.glob(pattern)
            
            if not matching_files:
                return False
            
            # 删除所有匹配的文件
            for file_path in matching_files:
                os.remove(file_path)
            
            return True
        except Exception as e:
            print(f"删除角色出错: {str(e)}")
            return False
    
    def get_all_characters(self):
        """获取所有角色名称"""
        try:
            # 确保目录存在
            os.makedirs(self.prompt_dir, exist_ok=True)
            
            # 获取所有音频文件
            audio_files = []
            for ext in [".wav", ".mp3", ".flac", ".ogg"]:
                audio_files.extend(glob.glob(os.path.join(self.prompt_dir, f"*{ext}")))
            
            characters = set()

            for file_path in audio_files:
                basename = os.path.basename(file_path)
                # 从文件名中提取角色名（第一个下划线前的部分）
                parts = basename.split("_", 1)
                if len(parts) > 1:
                    character_name = parts[0]
                    characters.add(character_name)
            
            # 返回按字母顺序排序的角色列表
            return sorted(list(characters))
        except Exception as e:
            print(f"获取角色列表出错: {e}")
            return []
    
    def character_exists(self, character_name):
        """
        检查指定的角色是否存在
        
        Args:
            character_name (str): 角色名称
            
        Returns:
            bool: 如果角色存在则返回True，否则返回False
        """
        if not character_name:
            return False
            
        try:
            # 查找匹配的角色文件
            pattern = os.path.join(self.prompt_dir, f"{character_name}_*")
            matching_files = glob.glob(pattern)
            return len(matching_files) > 0
        except Exception as e:
            print(f"检查角色是否存在时出错: {e}")
            return False
    
    def export_character(self, name, export_path):
        """将角色导出为单独的文件"""
        try:
            # 查找匹配的角色文件
            pattern = os.path.join(self.prompt_dir, f"{name}_*")
            matching_files = glob.glob(pattern)
            
            if not matching_files:
                return False
            
            # 导出第一个匹配的文件
            shutil.copy2(matching_files[0], export_path)
            return True
        except Exception as e:
            print(f"导出角色出错: {str(e)}")
            return False
    
    def import_character(self, import_path):
        """从外部文件导入角色"""
        try:
            if not os.path.exists(import_path):
                return False, "文件不存在"
                
            # 检查文件是否为音频文件
            file_ext = os.path.splitext(import_path)[1].lower()
            valid_extensions = [".wav", ".mp3", ".flac", ".ogg"]
            
            if file_ext not in valid_extensions:
                return False, f"不支持的文件格式，请使用 {', '.join(valid_extensions)}"
                
            # 从文件名获取角色名
            file_basename = os.path.basename(import_path)
            
            # 如果文件名已经包含下划线，假设第一部分是角色名
            if "_" in file_basename:
                character_name = file_basename.split("_", 1)[0]
            else:
                # 如果没有下划线，使用文件名（不含扩展名）作为角色名
                character_name = os.path.splitext(file_basename)[0]
            
            # 检查是否已存在同名角色
            if self.character_exists(character_name):
                return False, f"已存在同名角色 '{character_name}'"
            
            # 创建目标文件名
            target_filename = f"{character_name}_{file_basename}"
            target_path = os.path.join(self.prompt_dir, target_filename)
            
            # 复制文件
            shutil.copy2(import_path, target_path)
            
            return True, character_name
        except Exception as e:
            print(f"导入角色出错: {str(e)}")
            return False, str(e) 