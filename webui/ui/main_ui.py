#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
IndexTTS WebUI 界面构建模块
负责构建Gradio的用户界面
"""

import gradio as gr


class MainUI:
    """主界面构建类"""
    
    def __init__(self, audio_player, prompt_selector, text_input, log_display):
        """
        初始化UI构建器
        
        Args:
            audio_player: 音频播放器组件
            prompt_selector: 提示选择器组件
            text_input: 文本输入组件
            log_display: 日志显示组件
        """
        self.audio_player = audio_player
        self.prompt_selector = prompt_selector
        self.text_input = text_input
        self.log_display = log_display
        
    def build(self, generate_callback, update_prompt_callback, save_preset_callback=None, refresh_presets_callback=None, delete_preset_callback=None, play_history_callback=None, refresh_history_callback=None):
        """
        构建Gradio界面
        
        Args:
            generate_callback: 生成音频的回调函数
            update_prompt_callback: 更新提示的回调函数
            save_preset_callback: 保存预设的回调函数
            refresh_presets_callback: 刷新预设的回调函数
            delete_preset_callback: 删除预设的回调函数
            play_history_callback: 播放历史音频的回调函数
            refresh_history_callback: 刷新历史音频列表的回调函数
            
        Returns:
            gr.Blocks: Gradio界面对象
        """
        # 创建Gradio界面
        demo = gr.Blocks(title="IndexTTS WebUI")
        
        with demo:
            self._add_header()
            
            with gr.Tab("音频生成"):
                # 布局组件
                prompt_audio, prompt_dropdown, _, save_btn, refresh_btn, delete_btn, text_area, mode_selector, punct_chars, pause_time, gen_button, output_audio, log_area, history_dropdown, refresh_history_btn, history_audio = self._create_main_tab()
                
             
                
                # 绑定事件 - 使用每一个yield更新UI
                gen_button.click(
                    fn=generate_callback,
                    inputs=[prompt_audio, text_area, mode_selector, punct_chars, pause_time],
                    outputs=[output_audio, log_area],
                    show_progress="minimal"  # 显示最小的进度指示
                )
                
                prompt_dropdown.change(
                    update_prompt_callback,
                    inputs=[prompt_dropdown],
                    outputs=[prompt_audio]
                )
                
                # 绑定预设管理按钮事件
                if save_preset_callback:
                    save_btn.click(
                        fn=save_preset_callback,
                        inputs=[prompt_audio, prompt_dropdown],
                        outputs=[prompt_dropdown, log_area, prompt_audio]  # 添加prompt_audio作为输出参数
                    )
                
                if refresh_presets_callback:
                    refresh_btn.click(
                        fn=refresh_presets_callback,
                        inputs=[],
                        outputs=[prompt_dropdown, log_area, prompt_audio]  # 添加prompt_audio作为输出参数
                    )
                
                if delete_preset_callback:
                    delete_btn.click(
                        fn=delete_preset_callback,
                        inputs=[prompt_dropdown],
                        outputs=[prompt_dropdown, log_area, prompt_audio]  # 添加prompt_audio作为输出参数
                    )
                
                # 将历史音频下拉框的change事件绑定到播放回调函数
                if play_history_callback:
                    history_dropdown.change(
                        fn=play_history_callback,
                        inputs=[history_dropdown],
                        outputs=[history_audio, log_area]
                    )
                
                # 绑定刷新历史音频列表事件
                if refresh_history_callback:
                    refresh_history_btn.click(
                        fn=refresh_history_callback,
                        inputs=[],
                        outputs=[history_dropdown, log_area]
                    )
                    
                    # 不再使用_js参数，而是在生成音频完成后由用户手动刷新或通过事件处理器内部处理
                    
                    # 在应用启动时初始化历史音频列表
                    demo.load(
                        fn=refresh_history_callback,
                        inputs=[],
                        outputs=[history_dropdown, log_area],
                        show_progress=False  # 不显示进度
                    )
        
        return demo
    
    def _add_header(self):
        """添加页面标题和介绍"""
        gr.HTML('''
        <h2><center>IndexTTS: 工业级可控且高效的零样本文本转语音系统</h2>
        <h2><center>(An Industrial-Level Controllable and Efficient Zero-Shot Text-To-Speech System)</h2>
        <p align="center">
        <a href='https://arxiv.org/abs/2502.05512'><img src='https://img.shields.io/badge/ArXiv-2502.05512-red'></a>
        </p>
        ''')
    
    def _create_main_tab(self):
        """创建主要的音频生成标签页"""
        with gr.Row():
            with gr.Column():
                prompt_audio = self.audio_player.create_upload_component(label="请上传参考音频")
                
                # 预设选择区域调整
                with gr.Row():
                    prompt_dropdown = self.prompt_selector.create_dropdown_component(label="或选择预设提示")
                
                # 预设管理区域重新布局 - 移除预设名称输入框
                with gr.Row(equal_height=True, variant="panel"):
                    save_btn = gr.Button("保存为预设", size="md")
                    refresh_btn = gr.Button("刷新预设", size="md")
                    delete_btn = gr.Button("删除预设", size="md")
            
            with gr.Column():
                text_area = self.text_input.create_text_area(label="请输入目标文本")
                
                with gr.Row():
                    mode_selector = gr.Radio(
                        choices=["普通推理", "批次推理"], 
                        label="推理模式",
                        value="普通推理"
                    )
                    
                with gr.Row():
                    # 添加文本处理选项
                    punct_chars = gr.Textbox(label="分割标点符号", value="。？！!?;；", lines=1)
                    pause_time = gr.Number(label="停顿时间(秒)", value=0.3, step=0.1)
                
                gen_button = gr.Button("生成语音")
        
        output_audio = gr.Audio(label="生成结果", visible=True)
        
        # 添加日志显示区域
        log_area = self.log_display.create_log_area(label="处理日志")
        
        # 添加历史音频回放区域
        with gr.Row(variant="panel"):
            gr.HTML("<h3>历史音频回放</h3>")
        
        with gr.Row():
            # 历史音频下拉列表
            history_dropdown = gr.Dropdown(label="选择历史音频", choices=[], interactive=True)
            
            # 只保留刷新按钮，移除播放按钮
            refresh_history_btn = gr.Button("刷新列表", size="sm")
        
        # 历史音频播放器
        history_audio = gr.Audio(label="历史音频播放", visible=True)
        
        # 返回组件，包括新添加的历史音频组件，移除了不再需要的play_history_btn
        return prompt_audio, prompt_dropdown, None, save_btn, refresh_btn, delete_btn, text_area, mode_selector, punct_chars, pause_time, gen_button, output_audio, log_area, history_dropdown, refresh_history_btn, history_audio
