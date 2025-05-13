import os
import sys
import warnings
import argparse
import logging

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)
sys.path.append(os.path.join(current_dir, "indextts"))

from utils.logger import info, error, set_level
from ui.main_ui import MainUI
from ui.event_handlers import EventHandlers
from services.prompt_service import PromptService
from services.tts_service import TTS_Service
from services.config_service import ConfigService

# 设置系统变量
os.environ['GRADIO_SERVER_NAME'] = '0.0.0.0'
os.environ['GRADIO_SERVER_PORT'] = '7860'

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="IndexTTS WebUI")
    parser.add_argument(
        "--log-level",
        type=str,
        default="info",
        choices=["debug", "info", "warning", "error", "critical"],
        help="日志级别 (debug, info, warning, error, critical)",
    )
    return parser.parse_args()


def main():
    # 解析命令行参数
    args = parse_args()

    # 设置日志级别
    log_level_map = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "error": logging.ERROR,
        "critical": logging.CRITICAL,
    }
    set_level(log_level_map[args.log_level])

    try:
        info("IndexTTS WebUI 启动中...")

        info("初始化配置服务...")
        config_service = ConfigService()

        info("初始化提示词服务...")
        prompt_service = PromptService()

        info("初始化 TTS 服务...")
        tts_service = TTS_Service(config_service=config_service)

        info("创建必要目录...")
        os.makedirs("outputs", exist_ok=True)
        os.makedirs("prompts", exist_ok=True)

        info("构建用户界面...")
        main_ui = MainUI()
        event_handlers = EventHandlers(tts_service, prompt_service, config_service)

        info("启动 Gradio 界面...")
        demo = main_ui.build(event_handlers)
        demo.queue(20)

        info(f"服务器准备就绪，监听地址: {os.environ['GRADIO_SERVER_NAME']}:{os.environ['GRADIO_SERVER_PORT']}")
        demo.launch(favicon_path="webui/favicon.png")
    except Exception as e:
        error(f"程序启动出错: {str(e)}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
