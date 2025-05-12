import gradio as gr

from indextts.infer import IndexTTS


class TTS_Service:
    def __init__(self):
        self.tts = IndexTTS(model_dir="checkpoints",cfg_path="checkpoints/config.yaml")


    def gen_wavdata(self, prompt, text, infer_mode, silence_duration=0.3):
        """根据选择的参考音频名称和文本生成音频数据"""

        if infer_mode == "普通推理":
            sampling_rate, wav_data = self.tts.infer(prompt, text, None, verbose=True, silence_duration=silence_duration) # 普通推理
        else:
            sampling_rate, wav_data  = self.tts.infer_fast(prompt, text, None, verbose=True, silence_duration=silence_duration) # 批次推理
        return sampling_rate, wav_data

    
    def gen_wavdata_togr(self, prompt, text, infer_mode, silence_duration=0.3, progress=gr.Progress()):

        self.tts.gr_progress = progress    
        sampling_rate, wav_data = self.gen_wavdata(prompt, text, infer_mode, silence_duration)
        
        return gr.update(value=(sampling_rate, wav_data), visible=True)
