import os
from typing import List, Dict


class PromptService:
    def __init__(self):
        self.prompt_datas = List[Dict[str, str]]

        # 加载prompt_datas
        self._load_prompt_datas()

    def _load_prompt_datas(self):
        """获取prompts文件夹中的参考音频列表，并提取第一_之前的文字作为角色名"""

        # 清除prompt_datas
        self.prompt_datas = []

        # 获取prompts文件夹中的参考音频列表
        files = os.listdir("prompts")
        print(f"files: {files}")

        for file in files:
            prompt_filename = os.path.basename(file)
            full_name = os.path.splitext(prompt_filename)[0]

            # 提取第一个下划线之前的内容作为角色名
            if "_" in full_name:
                speaker_name = full_name.split("_", 1)[0]
            else:
                speaker_name = full_name

            self.prompt_datas.append(
                {"name": speaker_name, "path": os.path.join("prompts", file)}
            )

    def get_prompt_files(self):
        return ["无"] + [data["name"] for data in self.prompt_datas]

    def refresh_prompt_datas(self):
        self._load_prompt_datas()
        return self.get_prompt_files()

    # 从角色名获取对应的音频文件路径
    def get_prompt_file_path(self, speaker_name):
        for data in self.prompt_datas:
            if data["name"] == speaker_name:
                return data["path"]
        return None
