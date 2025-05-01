"""IndexTTS UI 包
提供IndexTTS的用户界面组件和相关功能。
"""

# 导入类型兼容层
from ui.models.compat import Self

# 导入主窗口类供外部使用
from ui.views.main_window import MainWindow

"""IndexTTS UI 包初始化
创建所需文件夹并初始化相关变量
"""

import os

# 确保重要的目录存在
for dir_path in ["prompts", "outputs", "outputs/temp", "config"]:
    os.makedirs(dir_path, exist_ok=True) 