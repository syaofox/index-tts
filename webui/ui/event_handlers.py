import os
import time
import gradio as gr
import threading
import queue
import shutil
import re


class EventHandlers:
    def __init__(self,tts_service, prompt_service):
        self.tts = tts_service
        self.prompt_service = prompt_service   
 
  
    @property
    def prompt_files(self):
        return self.prompt_service._get_prompt_files()
        
    def update_prompt_audio(self):
        return gr.update(interactive=True)
    
    def refresh_prompt_files(self):
        return gr.update(choices=self.prompt_service._get_prompt_files())

    def dropdown_change(self,selected_prompt):
        prompt_path = self.prompt_service._load_selected_prompt(selected_prompt)
        return gr.update(value=prompt_path)

    def gen_wavdata_togr(self, prompt, text, infer_mode, silence_duration=0.3, progress=gr.Progress()):
        """根据选择的参考音频名称和文本生成音频数据"""
        return self.tts.gen_wavdata_togr(prompt, text, infer_mode, silence_duration, progress)


    
