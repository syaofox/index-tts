"""角色管理模型
提供TTS角色的管理功能。
"""

import os
import time
import pickle
import glob


class CharacterManager:
    """角色管理类，用于管理TTS角色"""
    def __init__(self, prompt_dir="prompts"):
        self.prompt_dir = prompt_dir
        os.makedirs(prompt_dir, exist_ok=True)
    
    def save_character(self, name, voice_path):
        """保存角色到pickle文件，包含音频数据"""
        if not name or not voice_path or not os.path.exists(voice_path):
            return False
        
        try:
            # 读取音频文件的二进制内容
            with open(voice_path, 'rb') as audio_file:
                audio_data = audio_file.read()
            
            # 获取原始文件名和扩展名
            orig_filename = os.path.basename(voice_path)
            file_extension = os.path.splitext(voice_path)[1]
            
            # 创建角色数据结构
            character_data = {
                "name": name,
                "audio_data": audio_data,  # 直接保存音频二进制数据
                "audio_extension": file_extension,  # 保存扩展名以便后续使用
                "original_filename": orig_filename,  # 保存原始文件名
                "created_time": time.time()
            }
            
            # 保存到pickle文件
            pickle_path = os.path.join(self.prompt_dir, f"{name}.pickle")
            with open(pickle_path, "wb") as f:
                pickle.dump(character_data, f)
            
            return True
        except Exception as e:
            print(f"保存角色出错: {str(e)}")
            return False
    
    def load_character(self, name):
        """从pickle文件加载角色数据，包括从二进制数据还原音频文件"""
        try:
            pickle_path = os.path.join(self.prompt_dir, f"{name}.pickle")
            if not os.path.exists(pickle_path):
                return None
            
            with open(pickle_path, "rb") as f:
                character_data = pickle.load(f)
            
            # 从二进制数据创建临时音频文件
            if "audio_data" in character_data and character_data["audio_data"]:
                # 创建临时目录（如果不存在）
                temp_dir = os.path.join(self.prompt_dir, "temp")
                os.makedirs(temp_dir, exist_ok=True)
                
                # 使用原始文件名（如果存在），否则使用角色名加扩展名
                if "original_filename" in character_data and character_data["original_filename"]:
                    # 为防止文件名冲突，添加前缀
                    filename = f"{name}_{character_data['original_filename']}"
                else:
                    extension = character_data.get("audio_extension", ".wav")
                    filename = f"{name}{extension}"
                
                temp_audio_path = os.path.join(temp_dir, filename)
                
                # 写入音频数据到临时文件
                with open(temp_audio_path, "wb") as audio_file:
                    audio_file.write(character_data["audio_data"])
                
                # 将临时文件路径添加到返回数据中
                character_data["voice_path"] = temp_audio_path
            else:
                print(f"警告: 角色 {name} 的音频数据不存在")
                return None
            
            return character_data
        except Exception as e:
            print(f"加载角色出错: {str(e)}")
            return None
    
    def delete_character(self, name):
        """删除角色pickle文件"""
        try:
            pickle_path = os.path.join(self.prompt_dir, f"{name}.pickle")
            if not os.path.exists(pickle_path):
                return False
            
            # 先获取角色数据，检查原始文件名
            try:
                with open(pickle_path, "rb") as f:
                    character_data = pickle.load(f)
                    
                # 尝试删除临时文件
                temp_dir = os.path.join(self.prompt_dir, "temp")
                if os.path.exists(temp_dir):
                    # 如果有原始文件名，尝试删除对应的临时文件
                    if "original_filename" in character_data and character_data["original_filename"]:
                        temp_path = os.path.join(temp_dir, f"{name}_{character_data['original_filename']}")
                        if os.path.exists(temp_path):
                            os.remove(temp_path)
                    else:
                        # 否则尝试删除各种可能的扩展名文件
                        for ext in [".wav", ".mp3", ".flac", ".ogg"]:
                            temp_path = os.path.join(temp_dir, f"{name}{ext}")
                            if os.path.exists(temp_path):
                                os.remove(temp_path)
            except:
                pass  # 即使获取角色数据失败，也继续删除pickle文件
            
            # 删除pickle文件
            os.remove(pickle_path)
            return True
        except Exception as e:
            print(f"删除角色出错: {str(e)}")
            return False
    
    def get_all_characters(self):
        """获取所有角色名称"""
        try:
            # 确保目录存在
            os.makedirs(self.prompt_dir, exist_ok=True)
            
            # 获取所有pickle文件
            character_files = glob.glob(os.path.join(self.prompt_dir, "*.pickle"))
            characters = []
            
            for file_path in character_files:
                basename = os.path.basename(file_path)
                name, _ = os.path.splitext(basename)
                characters.append(name)
            
            return characters
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
            file_path = os.path.join(self.prompt_dir, f"{character_name}.pickle")
            return os.path.exists(file_path)
        except Exception as e:
            print(f"检查角色是否存在时出错: {e}")
            return False
    
    def export_character(self, name, export_path):
        """将角色导出为单独的文件"""
        try:
            pickle_path = os.path.join(self.prompt_dir, f"{name}.pickle")
            if not os.path.exists(pickle_path):
                return False
            
            import shutil
            shutil.copy2(pickle_path, export_path)
            return True
        except Exception as e:
            print(f"导出角色出错: {str(e)}")
            return False
    
    def import_character(self, import_path):
        """从外部文件导入角色"""
        try:
            if not os.path.exists(import_path) or not import_path.endswith('.pickle'):
                return False, "无效的角色文件"
            
            # 尝试加载文件验证格式
            try:
                with open(import_path, 'rb') as f:
                    data = pickle.load(f)
                if not isinstance(data, dict) or "name" not in data or "audio_data" not in data:
                    return False, "文件格式错误，不是有效的角色文件"
            except:
                return False, "文件损坏或格式错误"
            
            # 提取角色名
            character_name = data["name"]
            
            # 检查是否已存在同名角色
            if os.path.exists(os.path.join(self.prompt_dir, f"{character_name}.pickle")):
                return False, f"已存在同名角色 '{character_name}'"
            
            # 复制文件到prompts目录
            import shutil
            dest_path = os.path.join(self.prompt_dir, f"{character_name}.pickle")
            shutil.copy2(import_path, dest_path)
            
            return True, character_name
        except Exception as e:
            print(f"导入角色出错: {str(e)}")
            return False, str(e) 