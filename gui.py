"""IndexTTS主程序入口
提供IndexTTS的主程序入口点。
"""

# ===== 重要：在任何导入之前添加类型兼容层 =====
import sys
# 对typing.Self应用全局补丁
try:
    from typing import Self
except ImportError:
    try:
        # 尝试从typing_extensions导入
        from typing_extensions import Self
    except ImportError:
        # 如果无法导入，创建一个假的Self类型
        # 将其添加到typing模块中，使得所有导入typing的地方都能获取到这个补丁
        import typing
        typing.Self = object
        sys.modules['typing'].Self = object
# ===============================================

import os
from PySide6.QtWidgets import QApplication, QMessageBox

from ui import MainWindow


def main():
    """程序主入口函数"""
    # 确保必要的目录存在
    os.makedirs("outputs", exist_ok=True)
    os.makedirs("prompts", exist_ok=True)
    
    # 创建应用
    app = QApplication(sys.argv)
    
    try:
        # 导入和初始化TTS模型
        from indextts.infer import IndexTTS
        tts = IndexTTS(model_dir="checkpoints", cfg_path="checkpoints/config.yaml")
        
        # 创建主窗口
        window = MainWindow(tts)
        window.show()
        
        sys.exit(app.exec())
    except Exception as e:
        QMessageBox.critical(None, "错误", f"初始化失败: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main() 