"""推理工作线程控制器
提供TTS推理的后台处理功能。
"""

import os
from typing import List, Tuple, Dict, Optional, Any

from PySide6.QtCore import QObject, Signal
from ui.controllers.inference_base import InferenceBase
from ui.controllers.multi_role_inference import MultiRoleInference
from ui.models.text_processor import TextProcessor
from ui.models.audio_processor import AudioProcessor
from ui.models.file_manager import FileManager
from ui.models.config_manager import ConfigManager
from ui.models.inference_processor import InferenceProcessor
from ui.config import REPLACE_RULES_CONFIG_PATH


class InferenceWorker(QObject):
    """推理工作线程类，用于执行语音生成任务"""
    # 定义信号
    finished = Signal(str)  # 推理完成信号，返回输出文件路径
    progress = Signal(str)  # 进度信号，发送处理状态信息
    error = Signal(str)     # 错误信号
    
    # 特殊标记
    BR_TAG = "<br>"  # 空行标记
    # 固定的配置文件路径
    REPLACE_CONFIG_PATH = REPLACE_RULES_CONFIG_PATH

    def __init__(self, tts, voice_path, text, output_path=None, 
                 punct_chars="。？！", pause_time=0.3):
        super().__init__()
        self.tts = tts
        self.voice_path = voice_path
        self.text = text
        self.output_path = output_path
        self.punct_chars = punct_chars    # 分割标点符号
        self.pause_time = pause_time      # 段落间停顿时间（秒）
        self._stop_requested = False      # 停止标志
        
        # 加载配置
        self.replace_rules = ConfigManager.load_replace_rules(self.REPLACE_CONFIG_PATH)

    def stop(self):
        """请求停止推理过程"""
        self._stop_requested = True
        self.progress.emit("正在停止推理过程...")
    
    def is_stop_requested(self):
        """检查是否请求停止推理"""
        return self._stop_requested

    def run(self):
        """
        执行推理任务
        该方法在单独的线程中运行
        """
        try:
            # 使用InferenceProcessor处理推理任务
            success, result = self.process_inference()
            
            # 处理结果
            if success and result:
                if isinstance(result, str):
                    # 文件路径结果
                    self.finished.emit(result)
                else:
                    # 不应该到达这里，因为InferenceWorker总是提供output_path
                    self.error.emit("推理结果格式不正确")
            else:
                if self.is_stop_requested():
                    self.error.emit("推理已被用户中断")
                else:
                    self.error.emit("语音生成失败")
                
        except Exception as e:
            import traceback
            error_msg = f"推理出错: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            self.error.emit(error_msg)

    def process_inference(self):
        """
        处理推理任务，可被同步调用
        
        Returns:
            tuple: (success, output_file_path)
        """
        # 生成输出路径（如果未提供）
        if not self.output_path:
            self.output_path = FileManager.generate_output_path()
        
        # 使用InferenceProcessor进行推理，传递回调函数
        return InferenceProcessor.preprocess_and_infer(
            tts=self.tts,
            voice_path=self.voice_path,
            text=self.text,
            output_path=self.output_path,
            punct_chars=self.punct_chars,
            pause_time=self.pause_time, 
            replace_rules=self.replace_rules,
            progress_callback=self.progress.emit,
            stop_check_callback=self.is_stop_requested
        )


class MultiRoleInferenceWorker(MultiRoleInference):
    """多角色推理工作器类
    
    注意：此类已被 ui.controllers.multi_role_inference.MultiRoleInference 取代，
    将在后续版本中移除。请直接使用 MultiRoleInference 类。
    """
    
    def __init__(self, *args, **kwargs):
        import warnings
        warnings.warn(
            "MultiRoleInferenceWorker 类已被弃用，请直接使用 MultiRoleInference 类",
            DeprecationWarning, stacklevel=2
        )
        super().__init__(*args, **kwargs) 