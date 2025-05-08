#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
IndexTTS WebUI 应用入口点
基于Gradio的IndexTTS Web用户界面
"""

import os
import sys
import warnings

# 忽略警告
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

# 确保可以导入IndexTTS
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(current_dir)

# 确保必要的目录存在
for dir_path in ["prompts", "outputs", "outputs/temp", "webui/text_replace_config.txt"]:
    if dir_path.endswith(".txt"):
        # 确保文件所在目录存在
        os.makedirs(os.path.dirname(dir_path), exist_ok=True)
        # 如果文件不存在且是配置文件，复制从ui目录
        if not os.path.exists(dir_path) and os.path.exists(dir_path.replace("webui/", "ui/")):
            import shutil
            shutil.copy2(dir_path.replace("webui/", "ui/"), dir_path)
    else:
        os.makedirs(dir_path, exist_ok=True)

# 导入必要的模块
import gradio as gr

# 导入WebUI组件
from webui.components.audio_player import AudioPlayer
from webui.components.prompt_selector import PromptSelector
from webui.components.text_input import TextInput
from webui.components.log_display import LogDisplay

# 导入服务
from webui.services.tts_service import TTSService
from webui.services.file_service import FileService
from webui.services.enhanced_tts_service import EnhancedTTSService

# 导入配置
from webui.config.settings import Settings

# 导入UI构建和事件处理
from webui.ui.main_ui import MainUI
from webui.ui.event_handlers import EventHandlers

# 导入角色管理
from ui.models.character_manager import CharacterManager


def main():
    """WebUI主函数"""
    # 加载设置
    settings = Settings()
    
    # 初始化服务
    file_service = FileService(settings.prompts_dir, settings.outputs_dir)
    tts_service = TTSService(settings.model_dir, settings.config_path)
    
    # 初始化增强的TTS服务
    enhanced_tts_service = EnhancedTTSService(tts_service)
    
    # 初始化角色管理器
    character_manager = CharacterManager(settings.prompts_dir)
    
    # 确保必要目录存在
    file_service.ensure_directories()
    
    # 初始化UI组件
    audio_player = AudioPlayer()
    prompt_selector = PromptSelector(file_service)
    text_input = TextInput()
    log_display = LogDisplay()
    
    # 初始化事件处理器
    event_handlers = EventHandlers(
        enhanced_tts_service=enhanced_tts_service,
        character_manager=character_manager,
        settings=settings,
        file_service=file_service
    )
    
    # 初始化主界面
    main_ui = MainUI(
        audio_player=audio_player,
        prompt_selector=prompt_selector,
        text_input=text_input,
        log_display=log_display
    )
    
    # 构建Gradio界面
    demo = main_ui.build(
        generate_callback=event_handlers.generate_audio,
        update_prompt_callback=event_handlers.update_prompt_from_dropdown,
        save_preset_callback=event_handlers.save_preset,
        refresh_presets_callback=event_handlers.refresh_presets,
        delete_preset_callback=event_handlers.delete_preset,
        play_history_callback=event_handlers.play_history_audio,
        refresh_history_callback=event_handlers.refresh_history_files
    )
    
    # 启动Gradio服务
    demo.queue(20)
    demo.launch(server_name=settings.server_host, server_port=settings.server_port)


if __name__ == "__main__":
    main() 