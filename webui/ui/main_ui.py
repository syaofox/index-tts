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
        
    def build(self, generate_callback, update_prompt_callback, save_preset_callback=None, refresh_presets_callback=None, delete_preset_callback=None):
        """
        构建Gradio界面
        
        Args:
            generate_callback: 生成音频的回调函数
            update_prompt_callback: 更新提示的回调函数
            save_preset_callback: 保存预设的回调函数
            refresh_presets_callback: 刷新预设的回调函数
            delete_preset_callback: 删除预设的回调函数
            
        Returns:
            gr.Blocks: Gradio界面对象
        """
        # 创建Gradio界面
        demo = gr.Blocks(title="IndexTTS WebUI")
        
        with demo:
            self._add_header()
            
            with gr.Tab("音频生成"):
                # 布局组件
                prompt_audio, prompt_dropdown, _, save_btn, refresh_btn, delete_btn, text_area, mode_selector, punct_chars, pause_time, gen_button, output_audio, log_area = self._create_main_tab()
                
                self._add_multi_role_instructions()
                
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
        
        # 返回组件，但移除了preset_name
        return prompt_audio, prompt_dropdown, None, save_btn, refresh_btn, delete_btn, text_area, mode_selector, punct_chars, pause_time, gen_button, output_audio, log_area
    
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