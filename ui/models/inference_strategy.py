"""推理策略模型
实现不同的TTS推理策略，采用策略模式设计模式。
"""

import os
from typing import Tuple, Optional, Union


class InferenceStrategy:
    """推理策略接口"""
    
    def infer(self, tts, voice_path, text, output_path=None):
        """
        执行推理
        
        Args:
            tts: TTS模型对象
            voice_path: 参考音频路径
            text: 推理文本
            output_path: 输出音频路径，如果为None则返回波形数据
            
        Returns:
            bool 或 (波形, 采样率): 推理是否成功，或者波形数据和采样率
        """
        raise NotImplementedError("子类必须实现infer方法")


class NormalInferenceStrategy(InferenceStrategy):
    """普通推理策略"""
    
    def infer(self, tts, voice_path, text, output_path=None):
        """使用普通模式执行推理"""
        try:
            result = tts.infer(voice_path, text, output_path)
            if output_path is None:
                # 内存模式，返回波形数据和采样率
                return result  # (采样率, 波形数据)
            else:
                # 文件模式，返回是否成功
                return os.path.exists(output_path) and os.path.getsize(output_path) > 0
        except Exception as e:
            print(f"普通推理出错: {str(e)}")
            return False if output_path else (None, None)


class FastInferenceStrategy(InferenceStrategy):
    """快速推理策略"""
    
    def infer(self, tts, voice_path, text, output_path=None):
        """使用快速模式执行推理"""
        try:
            result = tts.infer_fast(voice_path, text, output_path)
            if output_path is None:
                # 内存模式，返回波形数据和采样率
                return result  # (采样率, 波形数据)
            else:
                # 文件模式，返回是否成功
                return os.path.exists(output_path) and os.path.getsize(output_path) > 0
        except Exception as e:
            print(f"快速推理出错: {str(e)}")
            return False if output_path else (None, None)


class InferenceStrategyFactory:
    """推理策略工厂类"""
    
    @staticmethod
    def create_strategy(mode: str) -> InferenceStrategy:
        """
        创建推理策略
        
        Args:
            mode: 推理模式，"normal"或"fast"
            
        Returns:
            InferenceStrategy: 推理策略对象
        """
        if mode == "fast":
            return FastInferenceStrategy()
        else:
            return NormalInferenceStrategy() 