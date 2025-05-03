"""文本处理工具
提供TTS文本的预处理功能。
"""

import re
from typing import List, Tuple, Optional, Dict, Any


class TextProcessor:
    """文本处理工具类，提供文本预处理方法"""
    
    # 特殊标记
    BR_TAG = "<br>"  # 空行标记
    
    @classmethod
    def preprocess_text(cls, text: str, punct_chars: str = "。？！", replace_rules=None) -> List[str]:
        """
        文本预处理，包括：
        1. 应用文本替换规则（如果有）
        2. 按段落分割
        3. 将空行替换为<br>标记
        4. 对非<br>段落按标点符号分割
        
        Args:
            text (str): 要处理的原始文本
            punct_chars (str): 分割文本的标点符号，默认为"。？！"
            replace_rules (list): 替换规则列表，格式为[(search_str, replace_from, replace_to), ...]
            
        Returns:
            list: 处理后的文本段落列表
        """
        # 应用文本替换规则
        if replace_rules:
            text = cls.apply_replace_rules(text, replace_rules)
        
        # 分割段落并处理空行
        paragraphs = cls.split_text_by_newlines_with_br(text)
        
        # 对每个段落，如果不是<br>标记，则按标点分割
        segments = []
        for para in paragraphs:
            if para == cls.BR_TAG:
                segments.append(para)
            else:
                # 对非空且非<br>的段落按标点分割
                if para.strip():
                    para_segments = cls.split_text_by_punctuation(para, punct_chars)
                    segments.extend(para_segments)
        
        return segments
    
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
        import os
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

    @staticmethod
    def parse_multi_role_text(text: str) -> List[Tuple[Optional[str], str]]:
        """
        解析多角色文本
        
        格式：
        <角色名1>
        角色1的文本内容
        <角色名2>
        角色2的文本内容
        
        Args:
            text: 输入的多角色文本
            
        Returns:
            list: 包含(角色名, 文本内容)元组的列表
        """
        # 按行分割文本
        lines = text.split("\n")
        result = []
        
        current_role = None
        current_text_lines = []
        
        # 检查文本是否包含角色标记
        has_role_marker = False
        for line in lines:
            line_stripped = line.strip()
            # 检查是否是角色标记行（格式为 <角色名>）
            if line_stripped.startswith("<") and line_stripped.endswith(">"):
                has_role_marker = True
                break
        
        # 如果没有角色标记，作为单角色处理
        if not has_role_marker:
            return [(None, text)]
        
        # 解析多角色文本
        for line in lines:
            line_stripped = line.strip()
            # 检查是否是角色标记行（格式为 <角色名>）
            if line_stripped.startswith("<") and line_stripped.endswith(">"):
                # 如果已有当前角色，保存之前的内容
                if current_role is not None and len(current_text_lines) > 0:
                    # 不去除空行，直接连接所有行
                    result.append((current_role, "\n".join(current_text_lines)))
                    current_text_lines = []
                
                # 提取新角色名
                current_role = line_stripped[1:-1].strip()
            else:
                # 只有当已经有角色标记时才添加文本
                if current_role is not None:
                    # 不管是否为空行，都添加到当前角色的文本中
                    current_text_lines.append(line)  # 保留原始行，包括空行
        
        # 添加最后一个角色的内容
        if current_role is not None and len(current_text_lines) > 0:
            result.append((current_role, "\n".join(current_text_lines)))
        
        return result 