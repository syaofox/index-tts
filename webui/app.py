#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
IndexTTS WebUI 应用入口点
基于Gradio的IndexTTS Web用户界面
"""

import os
import sys
import time
import warnings
import pickle

# 忽略警告
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

# 确保可以导入IndexTTS
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(current_dir)

# 导入必要的模块
import gradio as gr

# 导入WebUI组件
from webui.components.audio_player import AudioPlayer
from webui.components.prompt_selector import PromptSelector
from webui.components.text_input import TextInput

# 导入服务
from webui.services.tts_service import TTSService
from webui.services.file_service import FileService

# 导入配置
from webui.config.settings import Settings

# 导入CharacterManager用于处理pickle文件
from ui.models.character_manager import CharacterManager


def main():
    """WebUI主函数"""
    # 加载设置
    settings = Settings()
    
    # 初始化服务
    file_service = FileService(settings.prompts_dir, settings.outputs_dir)
    tts_service = TTSService(settings.model_dir, settings.config_path)
    
    # 初始化角色管理器，用于处理pickle文件
    character_manager = CharacterManager(settings.prompts_dir)
    
    # 确保必要目录存在
    file_service.ensure_directories()
    
    # 创建Gradio界面
    with gr.Blocks(title="IndexTTS WebUI") as demo:
        gr.HTML('''
        <h2><center>IndexTTS: 工业级可控且高效的零样本文本转语音系统</h2>
        <h2><center>(An Industrial-Level Controllable and Efficient Zero-Shot Text-To-Speech System)</h2>
        <p align="center">
        <a href='https://arxiv.org/abs/2502.05512'><img src='https://img.shields.io/badge/ArXiv-2502.05512-red'></a>
        </p>
        ''')
        
        with gr.Tab("音频生成"):
            # 初始化组件
            audio_player = AudioPlayer()
            prompt_selector = PromptSelector(file_service)
            text_input = TextInput()
            
            # 布局组件
            with gr.Row():
                with gr.Column():
                    prompt_audio = audio_player.create_upload_component(label="请上传参考音频")
                    prompt_dropdown = prompt_selector.create_dropdown_component(label="或选择预设提示")
                
                with gr.Column():
                    text_area = text_input.create_text_area(label="请输入目标文本")
                    mode_selector = gr.Radio(
                        choices=["普通推理", "批次推理"], 
                        label="选择推理模式（批次推理：更适合长句，性能翻倍）",
                        value="普通推理"
                    )
                    gen_button = gr.Button("生成语音")
            
            output_audio = gr.Audio(label="生成结果", visible=True)
            
            # 绑定事件
            def generate_audio(prompt_path, text, mode):
                """生成音频的回调函数"""
                if not prompt_path or not text:
                    return gr.update(value=None, visible=True)
                
                # 确保不是直接使用pickle文件作为音频输入
                if isinstance(prompt_path, str) and prompt_path.endswith('.pickle'):
                    # 从pickle文件中提取正确的音频文件路径
                    try:
                        prompt_path = file_service.get_prompt_path(os.path.basename(prompt_path).split('.')[0])
                    except Exception as e:
                        print(f"处理提示文件路径时出错: {e}")
                        return gr.update(value=None, visible=True)
                
                output_path = os.path.join(settings.outputs_dir, f"spk_{int(time.time())}.wav")
                result = tts_service.generate(prompt_path, text, output_path, 
                                            "normal" if mode == "普通推理" else "fast")
                return gr.update(value=result, visible=True)
            
            # 连接事件和回调
            gen_button.click(
                generate_audio,
                inputs=[prompt_audio, text_area, mode_selector],
                outputs=[output_audio]
            )
            
            # 处理提示选择
            def update_prompt_from_dropdown(prompt_name):
                """
                当从下拉列表选择提示时，加载相应的音频文件
                
                如果是pickle文件，则反序列化提取里面的音频数据
                """
                if not prompt_name:
                    return gr.update(value=None)
                
                try:
                    # 使用CharacterManager加载pickle文件并提取音频
                    character_data = character_manager.load_character(prompt_name)
                    
                    if character_data and "voice_path" in character_data:
                        # 返回提取的音频文件路径
                        return gr.update(value=character_data["voice_path"])
                    else:
                        # 如果字符数据提取失败，尝试直接使用文件服务获取音频路径
                        prompt_file = file_service.get_prompt_path(prompt_name)
                        return gr.update(value=prompt_file)
                except Exception as e:
                    print(f"加载提示音频出错: {e}")
                    return gr.update(value=None)
            
            prompt_dropdown.change(
                update_prompt_from_dropdown,
                inputs=[prompt_dropdown],
                outputs=[prompt_audio]
            )
    
    # 启动Gradio服务
    demo.queue(20)
    demo.launch(server_name=settings.server_host, server_port=settings.server_port)


if __name__ == "__main__":
    main() 