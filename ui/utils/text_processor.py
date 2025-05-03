"""文本处理工具类
提供用于处理和解析文本的工具函数。
"""

import re
from typing import List, Tuple, Optional, Dict, Any


class TextProcessor:
    """文本处理工具类，提供文本分割、解析等功能"""
    
    # 特殊标记
    BR_TAG = "<br>"  # 空行标记
    
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
    
    @staticmethod
    def split_text_by_newlines_with_br(text: str) -> List[str]:
        """
        按换行符分割文本，并将空行替换为<br>标记
        
        Args:
            text: 输入文本
            
        Returns:
            list: 分割后的段落列表，空行被替换为<br>标记
        """
        if not text:
            return []
            
        # 分割行，保留末尾空行
        lines = text.split('\n')
        
        # 处理段落和空行
        paragraphs = []
        current_paragraph = []
        
        # 添加调试信息
        print(f"原始文本行数: {len(lines)}")
        consecutive_empty = 0
        
        for i, line in enumerate(lines):
            stripped_line = line.strip()
            
            if stripped_line:  # 非空行
                consecutive_empty = 0
                # 非空行，添加到当前段落
                current_paragraph.append(stripped_line)
            else:  # 空行
                consecutive_empty += 1
                # 1. 结束当前段落
                if current_paragraph:
                    # 将当前段落合并为一个字符串
                    paragraphs.append(' '.join(current_paragraph))
                    current_paragraph = []
                
                # 2. 添加<br>标记表示空行
                # 注意：多个连续空行应添加多个<br>标记
                paragraphs.append(TextProcessor.BR_TAG)
                print(f"行 {i+1}: 检测到空行 (连续{consecutive_empty}个)")
        
        # 处理最后一个段落
        if current_paragraph:
            paragraphs.append(' '.join(current_paragraph))
        
        print(f"处理后的段落数: {len(paragraphs)}, 其中BR标记数: {paragraphs.count(TextProcessor.BR_TAG)}")
        
        return paragraphs
    
    @staticmethod
    def split_text_by_punctuation(text: str, punct_chars: str = "。？！") -> List[str]:
        """
        按指定的标点符号分割文本
        
        Args:
            text: 输入文本
            punct_chars: 用于分割的标点符号
            
        Returns:
            list: 分割后的文本段落列表
        """
        if not text:
            return []
            
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
    
    @staticmethod
    def preprocess_text(text: str, punct_chars: str = "。？！", replace_rules=None) -> List[str]:
        """
        文本预处理，包括：
        1. 应用文本替换规则（如果有）
        2. 按段落分割
        3. 将空行替换为<br>标记
        4. 对非<br>段落按标点符号分割（仅当punct_chars不为空时）
        
        Args:
            text: 输入文本
            punct_chars: 分割标点符号，为空时仅使用换行符分割
            replace_rules: 文本替换规则列表
            
        Returns:
            list: 预处理后的文本段落列表
        """
        # 应用文本替换规则
        if replace_rules:
            text = TextProcessor.apply_replace_rules(text, replace_rules)
        
        # 分割段落并处理空行
        paragraphs = TextProcessor.split_text_by_newlines_with_br(text)
        
        # 当punct_chars为空时，跳过标点分割，只保留段落分割
        if not punct_chars:
            print("标点符号列表为空，仅使用换行符分割文本")
            return paragraphs
        
        # 对每个段落，如果不是<br>标记，则按标点分割
        segments = []
        for para in paragraphs:
            if para == TextProcessor.BR_TAG:
                segments.append(para)
            else:
                # 对非空且非<br>的段落按标点分割
                if para.strip():
                    para_segments = TextProcessor.split_text_by_punctuation(para, punct_chars)
                    segments.extend(para_segments)
        
        # 添加调试信息
        print(f"预处理后的片段数: {len(segments)}, 其中BR标记数: {segments.count(TextProcessor.BR_TAG)}")
        
        return segments
    
    @staticmethod
    def apply_replace_rules(text: str, replace_rules: list) -> str:
        """
        应用文本替换规则
        
        Args:
            text: 输入文本
            replace_rules: 替换规则列表，格式为 [(search_str, replace_from, replace_to), ...]
            
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