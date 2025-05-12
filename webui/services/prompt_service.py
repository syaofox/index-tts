import os

class PromptService:

    def __init__(self):
        self.prompt_files = []

    def _load_selected_prompt(self,selected_prompt):
        """根据选择的参考音频名称加载对应的音频文件"""
        if selected_prompt == "无":
            return None
        else:
            prompt_path = os.path.join("prompts", selected_prompt)
            if os.path.exists(prompt_path):
                return prompt_path
            return None

    def _get_prompt_files(self):
        """获取prompts文件夹中的参考音频列表"""
        self.prompt_files = os.listdir("prompts")
        return ["无"] + self.prompt_files

