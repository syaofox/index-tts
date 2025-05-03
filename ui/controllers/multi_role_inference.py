"""多角色推理控制器
提供多角色TTS推理的流程控制。
"""

import os
from typing import List, Tuple, Optional

from ui.controllers.inference_base import InferenceBase
from ui.controllers.single_role_inference import SingleRoleInference
from ui.models.audio_processor import AudioProcessor
from ui.models.text_processor import TextProcessor


class MultiRoleInference(InferenceBase):
    """多角色推理控制器"""
    
    def __init__(self, tts, character_manager, role_text_pairs, 
                 output_path=None, punct_chars="。？！", pause_time=0.3, replace_rules=None, infer_mode="normal"):
        """
        初始化多角色推理控制器
        
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
    
    def process_inference(self) -> Tuple[bool, Optional[Tuple]]:
        """
        处理多角色推理任务
        
        Returns:
            tuple: (success, (sample_rate, wave_data))
        """
        try:
            # 检查是否有有效的角色-文本对
            if not self.role_text_pairs:
                self.error.emit("没有有效的角色-文本对")
                return False, None
            
            # 检查所有角色是否存在
            missing_roles = self._check_roles_exist()
            if missing_roles:
                self.error.emit(f"以下角色不存在: {', '.join(missing_roles)}")
                return False, None
            
            # 用于存储每个角色生成的音频数据
            audio_segments = []
            sample_rate = 24000  # 默认采样率
            
            # 对每个角色-文本对进行推理
            for i, (role_name, text) in enumerate(self.role_text_pairs):
                # 检查是否请求停止
                if self.is_stop_requested():
                    self.error.emit("推理已被用户中断")
                    return False, None
                
                # 处理单个角色
                self.progress.emit(f"正在处理角色 '{role_name}' 的文本 ({i+1}/{len(self.role_text_pairs)})，使用{self.infer_mode}模式")
                
                # 处理当前角色
                audio_result = self._process_single_role(role_name, text, i)
                if audio_result:
                    # _process_single_role返回(sample_rate, wave_data)格式
                    sr, wave_data = audio_result
                    if sr != sample_rate and sample_rate != 24000:
                        # 如果有不同的采样率，记录下来
                        self.progress.emit(f"角色 '{role_name}' 的音频采样率为 {sr}，与默认采样率 {sample_rate} 不同")
                        # 使用第一个非默认采样率作为基准
                        sample_rate = sr
                    audio_segments.append(wave_data)
            
            # 检查是否请求停止
            if self.is_stop_requested():
                self.error.emit("推理已被用户中断")
                return False, None
            
            # 检查是否至少有一个音频片段
            if not audio_segments:
                self.error.emit("没有生成任何有效的音频数据")
                return False, None
                
            # 合并所有角色的音频数据
            self.progress.emit(f"正在合并 {len(audio_segments)} 个角色的音频数据...")
            
            # 在内存中合并音频
            merged_wave, merged_sr = AudioProcessor.merge_audio_data(audio_segments, sample_rate)
            
            if merged_wave is None:
                self.error.emit("合并音频数据失败")
                return False, None
            
            # 返回内存中的合并结果
            self.progress.emit("多角色音频合并完成！")
            return True, (merged_sr, merged_wave)
            
        except Exception as e:
            import traceback
            error_msg = f"多角色推理时出错: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            self.error.emit(f"多角色推理失败: {str(e)}")
            return False, None
    
    def _check_roles_exist(self) -> List[str]:
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
    
    def _process_single_role(self, role_name: str, text: str, index: int):
        """
        处理单个角色的推理
        
        Args:
            role_name: 角色名
            text: 文本内容
            index: 角色索引
            
        Returns:
            tuple: (sample_rate, wave_data)，如果失败则返回None
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
            
            # 创建单角色推理控制器，但不要启动新线程
            inference = SingleRoleInference(
                self.tts,
                voice_path,
                text,
                output_path=None,  # 不指定输出路径，使用内存模式
                punct_chars=self.punct_chars,
                pause_time=self.pause_time,
                replace_rules=self.replace_rules,
                infer_mode=self.infer_mode
            )
            
            # 连接进度信号，添加角色名前缀
            inference.progress.connect(lambda msg, name=role_name: self.progress.emit(f"[{name}] {msg}"))
            
            # 同步执行推理，使用内存模式
            if len(text.strip()) > 0:
                # 如果是长文本，进行分段处理
                segments = TextProcessor.preprocess_text(
                    text, self.punct_chars, self.replace_rules
                )
                
                if len(segments) > 1:
                    # 使用内部方法处理分段文本
                    success, result = inference._process_text_in_segments(segments)
                else:
                    # 使用内部方法处理单个文本
                    success, result = inference._process_single_text(text)
                
                if not success:
                    self.error.emit(f"处理角色 '{role_name}' 的文本时出错")
                    return None
                
                # 处理返回的结果 - 只接受(sample_rate, wave_data)格式
                if isinstance(result, tuple) and len(result) == 2:
                    sample_rate, wave_data = result
                    # 确保数据不为None
                    if sample_rate is None or wave_data is None:
                        self.error.emit(f"角色 '{role_name}' 的生成结果包含无效数据")
                        return None
                    return (sample_rate, wave_data)
                else:
                    # 非预期的返回格式
                    self.error.emit(f"角色 '{role_name}' 的生成结果格式错误: {type(result)}")
                    return None
            else:
                self.progress.emit(f"角色 '{role_name}' 的文本为空，跳过")
                return None
            
        except Exception as e:
            import traceback
            error_msg = f"处理角色 '{role_name}' 的推理时出错: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            self.error.emit(f"处理角色 '{role_name}' 失败: {str(e)}")
            return None 