import os
import sys
import warnings

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)
sys.path.append(os.path.join(current_dir, "indextts"))


from ui.main_ui import MainUI
from ui.event_handlers import EventHandlers
from services.prompt_service import PromptService
from services.tts_service import TTS_Service


def main():
    tts_service = TTS_Service()

    prompt_service = PromptService()

    os.makedirs("outputs", exist_ok=True)
    os.makedirs("prompts", exist_ok=True)

    main_ui = MainUI()
    event_handlers = EventHandlers(tts_service, prompt_service)

    demo = main_ui.build(event_handlers)
    demo.queue(20)
    demo.launch(server_name="127.0.0.1")


if __name__ == "__main__":
    main()
