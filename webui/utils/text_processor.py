import re
import os
import time

from typing import List, Tuple, Dict
from utils.logger import info, warning, error, debug


class TextProcessor:
    # 段落分隔标记（空行标记）
    BR_TAG = "<BR>"
    TEXT_REPLACE_RULES_FILE = "webui/text_replace_rules.txt"

    def __init__(self):
        self.last_mtime = 0
        self.replace_rules = self._load_replace_rules()

    def _load_replace_rules(self) -> List[Tuple[str, str, str]]:
        if not os.path.exists(self.TEXT_REPLACE_RULES_FILE):
            return []

        # 读取配置文件修改时间，如果修改时间大于last_mtime，则重新加载配置文件
        file_mtime = os.path.getmtime(self.TEXT_REPLACE_RULES_FILE)

        if file_mtime <= self.last_mtime:
            info("文本替换规则文件未修改，跳过加载")
            return self.replace_rules

        self.last_mtime = file_mtime
        self.replace_rules = []

        try:
            with open(self.TEXT_REPLACE_RULES_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    # 跳过空行和注释行
                    if not line or line.startswith("#"):
                        continue

                    parts = line.split("|")  # 使用竖线分隔
                    if len(parts) == 3:
                        search_str, replace_from, replace_to = parts
                        self.replace_rules.append(
                            (search_str, replace_from, replace_to)
                        )
                    else:
                        warning(f"警告：配置行格式不正确，已跳过: {line}")

            if self.replace_rules:
                info(f"已加载 {len(self.replace_rules)} 条文本替换规则")
        except Exception as e:
            error(f"加载文本替换配置文件出错: {str(e)}")

        return self.replace_rules

    @staticmethod
    def _clean_quotes(text: str) -> str:
        """
        清除引号
        """
        pattern = r"[\"\'\*\#“”]"
        return re.sub(pattern, "", text)

    def _apply_replace_rules(self, text: str) -> str:
        replace_rules = self._load_replace_rules()

        result_text = text
        for search_str, replace_from, replace_to in replace_rules:
            # 在搜索字符串中查找需要修改的部分并替换
            if search_str in result_text:
                # 创建一个新字符串，将搜索字符串中的替换源替换为替换目标
                modified_search_str = search_str.replace(replace_from, replace_to)
                # 替换原文本中的搜索字符串为修改后的字符串
                result_text = result_text.replace(search_str, modified_search_str)
                debug(f"文本替换: {search_str} -> {modified_search_str}")

        return result_text

    def _split_text_by_speaker_and_lines(
        self, text: str, default_speaker: str
    ) -> List[Dict[str, str]]:
        """
        按角色分割文本，并返回字典列表。
        文本格式示例：
        ```
        <角色名1>
        文本内容段落1

        文本内容段落2

        <角色名2>
        文本内容段落1

        文本内容段落2
        ```

        如果第一行不是<角色名>格式，则使用default_speaker

        返回格式：
        [
            {"text": "文本内容段落1", "speaker": "角色名1"},
            {"text": "<BR>", "speaker": "角色名1"},
            ...
        ]
        """
        if not text:
            return []

        # 清除文本开头的空行
        text = re.sub(r"^[\n\r]+", "", text)

        # 清除引号
        text = self._clean_quotes(text)

        # 应用替换规则
        text = self._apply_replace_rules(text)

        segments = []
        lines = text.split("\n")

        current_speaker = default_speaker

        buffer = []  # 用于临时存储当前角色的文本行

        # 角色标记正则表达式，匹配<角色名>格式
        speaker_pattern = re.compile(r"^<([^>]+)>$")

        # 检查第一行是否是角色标记，如果不是，保持默认角色
        first_line_processed = False

        for line in lines:
            line = line.strip()

            # 检查是否是角色标记行
            speaker_match = speaker_pattern.match(line)
            if speaker_match:
                # 如果buffer中有内容，先处理之前角色的内容
                if buffer:
                    for text_line in buffer:
                        if not text_line:
                            segments.append(
                                {"text": self.BR_TAG, "speaker": current_speaker}
                            )
                        else:
                            segments.append(
                                {"text": text_line, "speaker": current_speaker}
                            )
                    buffer = []

                # 更新当前角色
                current_speaker = speaker_match.group(1)
                first_line_processed = True
            else:
                # 普通文本行，添加到buffer
                buffer.append(line)
                # 如果这是第一行且不是角色标记，标记为已处理
                if not first_line_processed:
                    first_line_processed = True

        # 处理最后一个角色的内容
        if buffer:
            for text_line in buffer:
                if not text_line:
                    segments.append({"text": self.BR_TAG, "speaker": current_speaker})
                else:
                    segments.append({"text": text_line, "speaker": current_speaker})

        return segments

    def preprocess_text(self, text: str, speaker: str) -> List[Dict[str, str]]:
        if not text:
            return []

        # 去除最开始的空行，直到有内容的行
        text = re.sub(r"^[\n\r]+", "", text)

        # 清除引号
        text = self._clean_quotes(text)

        # 应用替换规则
        text = self._apply_replace_rules(text)

        # 将文本按行分割
        segments = self._split_text_by_speaker_and_lines(text, speaker)

        return segments

    @staticmethod
    def generate_output_filename(speaker_name, text):
        try:
            # 清理文本内容（取前50个字符）
            text_sample = (
                text.strip().replace("\n", "").replace("\r", "").replace(" ", "")
            )
            # 替换Windows文件名中的非法字符
            for char in '\\/:"*?<>|':
                text_sample = text_sample.replace(char, "_")
            text_sample = text_sample[:50]  # 限制长度

            # 添加时间戳
            timestamp = time.strftime("%Y%m%d%H%M%S", time.localtime())
            output_filename = f"[{speaker_name}][{timestamp}]{text_sample}"
            output_path = os.path.join("outputs", f"{output_filename}.wav")

            # 确保输出目录存在
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            return output_path

        except Exception:
            # 返回一个默认的输出路径
            timestamp = time.strftime("%Y%m%d%H%M%S", time.localtime())
            return os.path.join("outputs", f"audio_{timestamp}.wav")
