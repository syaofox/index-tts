"""多角色推理工作线程
提供多角色TTS推理的功能。
"""

import os
import time
import uuid
import traceback
import shutil
from typing import List, Tuple, Optional

from PySide6.QtCore import QMutex, QWaitCondition
from ui.controllers.inference_base import InferenceBase
from ui.controllers.single_role_worker import SingleRoleInferenceWorker
from ui.utils.text_processor import TextProcessor


class MultiRoleInferenceWorker(InferenceBase):
    """多角色推理工作线程类"""
    
    def __init__(self, tts, character_manager, role_text_pairs, 
                 output_path=None, punct_chars="。？！", pause_time=0.3, replace_rules=None, infer_mode="normal"):
        """
        初始化多角色推理工作器
        
        Args:
            tts: TTS模型对象
            character_manager: 角色管理器对象
            role_text_pairs: [(角色名, 文本内容), ...] 格式的列表
            output_path: 输出音频文件路径，如果为None则自动生成
            punct_chars: 分割文本的标点符号
            pause_time: 段落间停顿时间(秒)
            replace_rules: 文本替换规则列表，格式为[(search_str, replace_from, replace_to), ...]
            infer_mode: 推理模式，"normal"或"fast"
        """
        super().__init__(tts, output_path, punct_chars, pause_time)
        self.character_manager = character_manager
        self.role_text_pairs = role_text_pairs
        self.replace_rules = replace_rules or []
        self.infer_mode = infer_mode
        
        # 临时目录已在基类中创建，这里不需要重复创建
    
    def process_inference(self) -> Tuple[bool, Optional[str]]:
        """
        处理多角色推理任务
        
        Returns:
            tuple: (success, output_file_path)
        """
        try:
            # 检查是否有有效的角色-文本对
            if not self.role_text_pairs:
                self.error.emit("没有有效的角色-文本对")
                return False, None
            
            # 检查所有角色是否存在
            missing_roles = self.check_roles_exist()
            if missing_roles:
                self.error.emit(f"以下角色不存在: {', '.join(missing_roles)}")
                return False, None
            
            # 生成输出路径（如果未提供）
            if not self.output_path:
                self.output_path = self.generate_output_path()
            
            # 用于存储每个角色生成的音频文件路径
            audio_files = []
            
            # 对每个角色-文本对进行推理
            for i, (role_name, text) in enumerate(self.role_text_pairs):
                # 检查是否请求停止
                if self.is_stop_requested():
                    self.cleanup_temp_files()
                    self.error.emit("推理已被用户中断")
                    return False, None
                
                # 处理单个角色
                self.progress.emit(f"正在处理角色 '{role_name}' 的文本 ({i+1}/{len(self.role_text_pairs)})，使用{self.infer_mode}模式")
                
                # 处理当前角色
                audio_file = self.process_single_role(role_name, text, i)
                if audio_file and os.path.exists(audio_file) and os.path.getsize(audio_file) > 0:
                    audio_files.append(audio_file)
            
            # 检查是否请求停止
            if self.is_stop_requested():
                self.cleanup_temp_files()
                self.error.emit("推理已被用户中断")
                return False, None
            
            # 检查是否至少有一个音频文件
            if not audio_files:
                self.error.emit("没有生成任何有效的音频文件")
                self.cleanup_temp_files()
                return False, None
                
            # 合并所有角色的音频文件
            self.progress.emit(f"正在合并 {len(audio_files)} 个角色的音频文件...")
            
            # 尝试合并音频
            merged_file = self.merge_all_audio_files(audio_files)
            
            # 清理临时目录
            self.cleanup_temp_files()
            
            if not merged_file or not os.path.exists(merged_file):
                self.error.emit("合并音频文件失败")
                return False, None
            
            # 发送完成信号
            self.progress.emit("多角色推理完成！")
            return True, merged_file
            
        except Exception as e:
            error_msg = self.handle_exception(e, "多角色推理")
            self.cleanup_temp_files()
            return False, None
    
    def check_roles_exist(self) -> List[str]:
        """
        检查所有角色是否存在
        
        Returns:
            list: 不存在的角色名列表
        """
        missing_roles = []
        for role_name, _ in self.role_text_pairs:
            if not self.character_manager.character_exists(role_name):
                missing_roles.append(role_name)
        return missing_roles
    
    def process_single_role(self, role_name: str, text: str, index: int) -> Optional[str]:
        """
        处理单个角色的推理
        
        Args:
            role_name: 角色名
            text: 文本内容
            index: 角色索引
            
        Returns:
            str: 生成的音频文件路径，如果失败则返回None
        """
        try:
            # 检查是否请求停止
            if self.is_stop_requested():
                return None
            
            # 加载角色数据
            character_data = self.character_manager.load_character(role_name)
            if not character_data or "voice_path" not in character_data:
                self.error.emit(f"无法加载角色 '{role_name}' 或角色数据不完整")
                return None
            
            voice_path = character_data["voice_path"]
            if not os.path.exists(voice_path):
                self.error.emit(f"角色 '{role_name}' 的参考音频不存在: {voice_path}")
                return None
            
            # 为当前角色生成一个临时输出文件
            role_output_path = self.create_temp_file_path(f"{role_name}_{index}")
            
            # 创建单角色推理工作器，但不要启动新线程
            worker = SingleRoleInferenceWorker(
                self.tts,
                voice_path,
                text,
                output_path=role_output_path,
                punct_chars=self.punct_chars,
                pause_time=self.pause_time,
                replace_rules=self.replace_rules,  # 传递替换规则
                infer_mode=self.infer_mode  # 传递推理模式
            )
            
            # 连接进度信号，添加角色名前缀
            worker.progress.connect(lambda msg, name=role_name: self.progress.emit(f"[{name}] {msg}"))
            
            # 同步执行推理
            success, output_file = worker.process_inference()
            
            if not success or not output_file:
                self.error.emit(f"处理角色 '{role_name}' 的文本时出错")
                return None
            
            if not os.path.exists(output_file) or os.path.getsize(output_file) == 0:
                self.error.emit(f"生成的角色 '{role_name}' 的音频文件无效")
                return None
            
            return output_file
            
        except Exception as e:
            error_msg = self.handle_exception(e, f"处理角色 '{role_name}' 的推理")
            return None
    
    def merge_all_audio_files(self, audio_files: List[str]) -> Optional[str]:
        """
        合并所有角色的音频文件
        
        Args:
            audio_files: 音频文件路径列表
            
        Returns:
            str: 合并后的文件路径，如果失败则返回None
        """
        if not audio_files:
            return None
        
        try:
            # 确保输出目录存在
            os.makedirs(os.path.dirname(self.output_path), exist_ok=True)
            
            # 使用基类的合并方法
            self.progress.emit(f"正在合并 {len(audio_files)} 个音频文件...")
            merged_file = self.merge_audio_files(audio_files, self.output_path)
            
            if not merged_file or not os.path.exists(merged_file):
                # 如果合并失败但至少有一个音频文件，可以保存第一个音频文件作为最终输出
                if audio_files and os.path.exists(audio_files[0]):
                    self.progress.emit("合并失败，保存第一个角色的音频作为输出...")
                    shutil.copy2(audio_files[0], self.output_path)
                    return self.output_path
                else:
                    self.error.emit("合并音频文件失败且没有可用的备选音频")
                    return None
            
            return merged_file
            
        except Exception as e:
            error_msg = self.handle_exception(e, "合并音频文件")
            
            # 保存第一个角色的音频作为输出
            if audio_files and os.path.exists(audio_files[0]):
                try:
                    self.progress.emit("合并失败，保存第一个角色的音频作为输出...")
                    shutil.copy2(audio_files[0], self.output_path)
                    return self.output_path
                except Exception as copy_error:
                    self.error.emit(f"保存单个角色音频失败: {str(copy_error)}")
            
            return None
    
    def cleanup_temp_files(self):
        """清理临时文件和目录"""
        try:
            self.progress.emit("清理临时文件...")
            if os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception as e:
            print(f"清理临时文件时出错: {str(e)}")
            # 不抛出异常，因为这只是清理操作 