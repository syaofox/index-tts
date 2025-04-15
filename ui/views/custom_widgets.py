"""自定义小部件模块
提供IndexTTS UI中使用的自定义小部件类。
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSlider, QStyle


class ClickableSlider(QSlider):
    """可点击的进度条，允许用户直接点击某个位置以跳转"""
    def __init__(self, orientation):
        super().__init__(orientation)
    
    def mousePressEvent(self, event):
        """处理鼠标点击事件，直接调整滑块位置"""
        if self.orientation() == Qt.Orientation.Horizontal:
            # 水平滑块，计算点击位置对应的值
            value = QStyle.sliderValueFromPosition(
                self.minimum(), self.maximum(),
                event.position().x(), self.width()
            )
        else:
            # 垂直滑块，计算点击位置对应的值
            value = QStyle.sliderValueFromPosition(
                self.minimum(), self.maximum(),
                event.position().y(), self.height(),
                upsideDown=True
            )
        
        self.setValue(value)
        # 发射sliderMoved信号
        self.sliderMoved.emit(value)
        
        # 调用基类的鼠标事件处理
        super().mousePressEvent(event) 