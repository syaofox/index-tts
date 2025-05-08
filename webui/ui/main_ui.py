#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
IndexTTS WebUI 界面构建模块
负责构建Gradio的用户界面
"""

import gradio as gr


class MainUI:
    """主界面构建类"""
    
    def __init__(self, audio_player, prompt_selector, text_input):
        """
        初始化UI构建器
        
        Args:
            audio_player: 音频播放器组件
            prompt_selector: 提示选择器组件
            text_input: 文本输入组件
        """
        self.audio_player = audio_player
        self.prompt_selector = prompt_selector
        self.text_input = text_input
        
    def build(self, generate_callback, update_prompt_callback):
        """
        构建Gradio界面
        
        Args:
            generate_callback: 生成音频的回调函数
            update_prompt_callback: 更新提示的回调函数
            
        Returns:
            gr.Blocks: Gradio界面对象
        """
        # 创建Gradio界面
        demo = gr.Blocks(title="IndexTTS WebUI")
        
        with demo:
            self._add_header()
            
            with gr.Tab("音频生成"):
                # 布局组件
                prompt_audio, prompt_dropdown, text_area, mode_selector, punct_chars, pause_time, gen_button, output_audio = self._create_main_tab()
                
                self._add_multi_role_instructions()
                
                # 绑定事件
                gen_button.click(
                    generate_callback,
                    inputs=[prompt_audio, text_area, mode_selector, punct_chars, pause_time],
                    outputs=[output_audio]
                )
                
                prompt_dropdown.change(
                    update_prompt_callback,
                    inputs=[prompt_dropdown],
                    outputs=[prompt_audio]
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
                prompt_dropdown = self.prompt_selector.create_dropdown_component(label="或选择预设提示")
            
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
        
        return prompt_audio, prompt_dropdown, text_area, mode_selector, punct_chars, pause_time, gen_button, output_audio
    
    def _add_multi_role_instructions(self):
        """添加多角色使用说明"""
        gr.HTML('''
        <div style="margin: 10px 0; padding: 10px; border: 1px solid #ddd; border-radius: 5px; background-color: #f9f9f9;">
            <h3>多角色使用说明：</h3>
            <p>可以使用&lt;角色名&gt;的格式来指定不同角色的对话。例如：</p>
            <pre>
&lt;角色1&gt;
这是角色1说的话。
&lt;角色2&gt;
这是角色2的回应。
            </pre>
            <p>注意：</p>
            <ul>
                <li>角色名必须与预先保存的角色名称完全匹配</li>
                <li>每个角色的文本可以包含多行</li>
                <li>空行会自动添加停顿</li>
            </ul>
        </div>
        ''') 