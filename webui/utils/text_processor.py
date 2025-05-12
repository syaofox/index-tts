import re
import os
import time

from typing import List, Tuple


class TextProcessor:
    # 段落分隔标记（空行标记）
    BR_TAG = "<BR>"
    TEXT_REPLACE_RULES_FILE = "webui/text_replace_rules.txt"

    def __init__(self):
        self.last_mtime = 0
        self.replace_rules = self.load_replace_rules()

    def load_replace_rules(self) -> List[Tuple[str, str, str]]:
        if not os.path.exists(self.TEXT_REPLACE_RULES_FILE):
            return []

        # 读取配置文件修改时间，如果修改时间大于last_mtime，则重新加载配置文件
        file_mtime = os.path.getmtime(self.TEXT_REPLACE_RULES_FILE)

        if file_mtime <= self.last_mtime:
            print("文本替换规则文件未修改，跳过加载")
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
                        print(f"警告：配置行格式不正确，已跳过: {line}")

            if self.replace_rules:
                print(f"已加载 {len(self.replace_rules)} 条文本替换规则")
        except Exception as e:
            print(f"加载文本替换配置文件出错: {str(e)}")

        return self.replace_rules

    @staticmethod
    def clean_quotes(text: str) -> str:
        """
        清除引号
        """
        pattern = r"[\"\'\*\#“”]"
        return re.sub(pattern, "", text)

    def apply_replace_rules(self, text: str) -> str:
        replace_rules = self.load_replace_rules()

        result_text = text
        for search_str, replace_from, replace_to in replace_rules:
            # 在搜索字符串中查找需要修改的部分并替换
            if search_str in result_text:
                # 创建一个新字符串，将搜索字符串中的替换源替换为替换目标
                modified_search_str = search_str.replace(replace_from, replace_to)
                # 替换原文本中的搜索字符串为修改后的字符串
                result_text = result_text.replace(search_str, modified_search_str)
                print(f"文本替换: {search_str} -> {modified_search_str}")

        return result_text

    # 文本块处理
    def single_stock_text(self, text: str) -> List[str]:
        # 将文本按行分割
        lines = text.split("\n")
        segments = []

        # 处理每一行，保留空行逻辑
        for line in lines:
            line = line.strip()

            # 空行处理（添加段落分隔标记）
            if not line:
                segments.append(self.BR_TAG)
            else:
                segments.append(line)

        return segments

    def preprocess_text(self, text: str) -> List[str]:
        if not text:
            return []

        # 去除最开始的空行，直到有内容的行
        text = re.sub(r"^[\n\r]+", "", text)

        # 清除引号
        text = self.clean_quotes(text)

        # 应用替换规则
        text = self.apply_replace_rules(text)

        # 将文本按行分割
        segments = self.single_stock_text(text)

        return segments

    @staticmethod
    def _generate_output_filename(speaker_name, text):
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


if __name__ == "__main__":
    text = "你好，世界！\n\n\n\n\n\n你好，中国！"
    text_processor = TextProcessor()
    print(text_processor.preprocess_text(text))
