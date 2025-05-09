#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文本处理器模块
为TTS服务提供文本预处理功能
"""

import re
import os
from typing import List, Tuple, Optional, Dict, Any


class TextProcessor:
    """文本处理器类，提供各种文本预处理功能"""
    
    # 段落分隔标记（空行标记）
    BR_TAG = "[BR]"
    
    @staticmethod
    def preprocess_text(text, punct_chars="。？！.!?;；", replace_rules=None):
        """
        预处理文本，根据标点符号分割成段落
        
        Args:
            text: 输入文本
            punct_chars: 用于分割的标点符号
            replace_rules: 文本替换规则
            
        Returns:
            list: 分割后的文本段落列表
        """
        if not text:
            return []
            
        # 应用替换规则（如果有）
        if replace_rules:
            print(f"应用替换规则: {replace_rules}")
            text = TextProcessor.apply_replace_rules(text, replace_rules)
            
        # 将文本按行分割
        lines = text.split('\n')
        segments = []
        
        # 处理每一行，保留空行逻辑
        for line in lines:
            line = line.strip()
            
            # 空行处理（添加段落分隔标记）
            if not line:
                segments.append(TextProcessor.BR_TAG)
                continue
            
            # 使用split_text_by_punctuation方法按标点符号分割当前行
            line_segments = TextProcessor.split_text_by_punctuation(line, punct_chars)
            segments.extend(line_segments)
        
        return segments
        
    @staticmethod
    def parse_multi_role_text(text):
        """
        解析文本，确定是单人还是多人推理，并按角色分割文本
        
        Args:
            text: 输入文本
            
        Returns:
            tuple: (是否多人推理, 角色文本分段列表)
        """
        if not text:
            return False, []
            
        # 正则表达式匹配角色对话，只使用尖括号格式
        # 匹配形式：<角色名>\n对话内容
        pattern = r"<([^>]+)>\s*\n([\s\S]+?)(?=(?:\n<[^>]+>)|$)"
        
        matches = re.findall(pattern, text, re.DOTALL)
        
        # 处理匹配结果
        character_text_segments = []
        
        for character, content in matches:
            character = character.strip()
            if character and content:
                character_text_segments.append((character, content))
        
        # 如果找到多个角色对话，则为多人推理
        is_multi_character = len(character_text_segments) > 1
        
        # 如果没有找到匹配，则认为是单人推理，整个文本作为内容
        if not character_text_segments:
            is_multi_character = False
            character_text_segments = [(None, text.strip())]        
        
        return is_multi_character, character_text_segments

    @classmethod
    def clean_quotes(cls, text: str) -> str:
        """
        清除引号
        """
        pattern = r'[\"\'"\"\*\#]'
        return re.sub(pattern, '', text)
       
    @classmethod
    def apply_replace_rules(cls, text: str, replace_rules: List[Tuple[str, str, str]]) -> str:
        """
        根据配置规则替换文本
        
        Args:
            text (str): 要替换的文本
            replace_rules (list): 替换规则列表，格式为[(search_str, replace_from, replace_to), ...]
            
        Returns:
            str: 替换后的文本
        """
        if not replace_rules:
            return text
            
        result_text = text
        for search_str, replace_from, replace_to in replace_rules:
            # 在搜索字符串中查找需要修改的部分并替换
            if search_str in result_text:
                # 创建一个新字符串，将搜索字符串中的替换源替换为替换目标
                modified_search_str = search_str.replace(replace_from, replace_to)
                # 替换原文本中的搜索字符串为修改后的字符串
                result_text = result_text.replace(search_str, modified_search_str)
        
        return result_text
    
    @classmethod
    def split_text_by_punctuation(cls, text: str, punct_chars: str) -> List[str]:
        """
        按指定的标点符号分割文本
        
        Args:
            text (str): 要分割的文本
            punct_chars (str): 分割文本的标点符号
            
        Returns:
            list: 分割后的文本段落列表
        """
        if not text:
            return []

        # 如果标点符号为空，说明是快速模式，则不进行分割
        if not punct_chars:
            return [text]
            
        # 构建用于分割的正则表达式
        pattern = f"([{re.escape(punct_chars)}])"
        
        # 分割文本
        parts = re.split(pattern, text)
        
        # 将标点符号与前面的文本合并
        segments = []
        i = 0
        while i < len(parts):
            if i + 1 < len(parts) and parts[i+1] in punct_chars:
                # 当前文本加上后面的标点
                segments.append(parts[i] + parts[i+1])
                i += 2
            else:
                # 没有标点的文本
                if parts[i]:  # 不添加空文本
                    segments.append(parts[i])
                i += 1
        
        return segments
    
    @classmethod
    def split_text_by_newlines_with_br(cls, text: str) -> List[str]:
        """
        按换行符分割文本，并将空行替换为<br>标记
        
        Args:
            text (str): 输入文本
            
        Returns:
            list: 分割后的段落列表，空行被替换为<br>标记
        """
        if not text:
            return []
            
        # 分割行
        lines = text.split('\n')
        
        # 处理段落和空行
        paragraphs = []
        current_paragraph = []
        empty_line_count = 0  # 用于跟踪连续空行计数
        
        for line in lines:
            line = line.strip()
            if line:
                # 如果之前有空行计数，先处理
                if empty_line_count > 0:
                    # 为之前的每个空行添加一个<br>标记
                    for _ in range(empty_line_count):
                        paragraphs.append(cls.BR_TAG)
                    empty_line_count = 0
                
                # 非空行，添加到当前段落
                current_paragraph.append(line)
            else:
                # 空行，结束当前段落
                if current_paragraph:
                    # 将当前段落合并为一个字符串
                    paragraphs.append(' '.join(current_paragraph))
                    current_paragraph = []
                
                # 累加空行计数，而不是立即添加<br>标记
                empty_line_count += 1
        
        # 处理文本末尾的空行
        if empty_line_count > 0:
            for _ in range(empty_line_count):
                paragraphs.append(cls.BR_TAG)
        
        # 处理最后一个段落
        if current_paragraph:
            paragraphs.append(' '.join(current_paragraph))
        
        return paragraphs
        
    @classmethod
    def load_replace_rules_from_file(cls, config_path: str) -> List[Tuple[str, str, str]]:
        """
        从配置文件加载文本替换规则
        
        Args:
            config_path (str): 配置文件路径
            
        Returns:
            list: 替换规则列表，格式为[(search_str, replace_from, replace_to), ...]
        """
        replace_rules = []
        
        if not os.path.exists(config_path):
            return replace_rules
            
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    # 跳过空行和注释行
                    if not line or line.startswith('#'):
                        continue
                    
                    parts = line.split('|')  # 使用竖线分隔
                    if len(parts) == 3:
                        search_str, replace_from, replace_to = parts
                        replace_rules.append((search_str, replace_from, replace_to))
                    else:
                        print(f"警告：配置行格式不正确，已跳过: {line}")
            
            if replace_rules:
                print(f"已加载 {len(replace_rules)} 条文本替换规则")
        except Exception as e:
            print(f"加载文本替换配置文件出错: {str(e)}")
            
        return replace_rules 