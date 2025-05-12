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
 

    def _gen_data(self, prompt, text, infer_mode, silence_duration=0.3):
        """根据选择的参考音频名称和文本生成音频数据"""

        if infer_mode == "普通推理":
            sampling_rate, wav_data = self.tts.infer(prompt, text, None, verbose=True, silence_duration=silence_duration) # 普通推理
        else:
            sampling_rate, wav_data  = self.tts.infer_fast(prompt, text, None, verbose=True, silence_duration=silence_duration) # 批次推理
        return sampling_rate, wav_data

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

    def gen_single(self, prompt, text, infer_mode, silence_duration=0.3, progress=gr.Progress()):

        output_path = None
        if not output_path:
            output_path = os.path.join("outputs", f"spk_{int(time.time())}.wav")
        # set gradio progress
        self.tts.gr_progress = progress    
        sampling_rate, wav_data = self._gen_data(prompt, text, infer_mode, silence_duration)
        
        return gr.update(value=(sampling_rate, wav_data), visible=True)

    
