"""自定义小部件模块
提供IndexTTS UI中使用的自定义小部件类。
"""

from PySide6.QtCore import Qt, QMimeData, Signal
from PySide6.QtWidgets import QSlider, QStyle, QPushButton
from PySide6.QtGui import QDragEnterEvent, QDropEvent


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


class DropFileButton(QPushButton):
    """支持文件拖放的按钮
    
    允许用户直接拖放文件到按钮上，以便选择文件。
    """
    # 添加文件拖放信号
    fileDropped = Signal(str)
    
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        # 启用接收拖放
        self.setAcceptDrops(True)
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        """当用户拖动文件进入按钮区域时触发"""
        # 只接受包含文件URL的拖放操作
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
    
    def dropEvent(self, event: QDropEvent):
        """当用户在按钮上释放拖动的文件时触发"""
        mime_data = event.mimeData()
        if mime_data.hasUrls():
            # 获取第一个文件的URL
            url = mime_data.urls()[0]
            # 发射文件拖放信号
            self.fileDropped.emit(url.toLocalFile()) 