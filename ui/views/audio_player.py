"""音频播放器组件
提供音频文件播放和控制功能的UI组件。
"""

import os
import sys
import traceback
from urllib.parse import unquote

from PySide6.QtCore import Qt, QUrl
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QStyle
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

# 波形图相关库
import pyqtgraph as pg
import numpy as np
import torchaudio
import torch
import librosa


class AudioPlayer(QWidget):
    """音频播放器控件"""
    def __init__(self, label="音频播放器", parent=None, waveform_height=40, 
                 background_color='w', foreground_color='k', 
                 waveform_color=(200, 200, 200), position_line_color='red'):
        super().__init__(parent)
        self.label = label
        self.mediaPlayer = QMediaPlayer()
        self.audioOutput = QAudioOutput()
        self.mediaPlayer.setAudioOutput(self.audioOutput)
        self.audioOutput.setVolume(1)  # 设置默认音量为100%
        
        # 设置焦点策略，使得组件可以接收键盘事件
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        
        # 连接媒体播放器信号
        self.mediaPlayer.positionChanged.connect(self.onPositionChanged)
        self.mediaPlayer.durationChanged.connect(self.onDurationChanged)
        self.mediaPlayer.playbackStateChanged.connect(self.onPlaybackStateChanged)
        self.mediaPlayer.mediaStatusChanged.connect(self.onMediaStatusChanged)
        
        # 波形图相关 - 移到setupUI前初始化
        self.has_pyqtgraph = True
        self.waveformPlot = None
        self.waveformCurve = None
        self.positionLine = None
        self.audio_data = None
        self.sample_rate = None
        self.duration = 0
        self.waveform_height = waveform_height  # 保存波形图高度设置
        
        # 保存颜色设置
        self.background_color = background_color
        self.foreground_color = foreground_color
        self.waveform_color = waveform_color
        self.position_line_color = position_line_color
        
        # 设置界面
        self.setupUI()
        
    def setupUI(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)  # 减少边距
        
        # 创建播放控制区域
        control_layout = QHBoxLayout()
        control_layout.setContentsMargins(4, 4, 4, 4)  # 调整边距
        
        # 音频文件路径标签
        self.pathLabel = QLabel("未选择音频")
        self.pathLabel.setWordWrap(True)
        
        # 添加播放/暂停图标按钮
        self.playPauseBtn = QPushButton()
        self.playPauseBtn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.playPauseBtn.setEnabled(False)  # 初始时禁用播放按钮
        self.playPauseBtn.setFixedSize(32, 32)
        self.playPauseBtn.clicked.connect(self.togglePlayback)
        self.playPauseBtn.setToolTip("播放/暂停")
        
        # 时间显示
        self.timeLabel = QLabel("00:00 / 00:00")
        self.timeLabel.setFixedWidth(100)
        self.timeLabel.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        # 先添加路径标签占据大部分空间，然后添加控制元素
        control_layout.addWidget(self.pathLabel, 1)  # 让标签占据剩余空间
        control_layout.addWidget(self.playPauseBtn)
        control_layout.addWidget(self.timeLabel)
        
        # 添加布局
        main_layout.addLayout(control_layout)
        
        # 波形图区域
        # 设置背景为设定颜色
        pg.setConfigOption('background', self.background_color)
        # 设置前景为设定颜色
        pg.setConfigOption('foreground', self.foreground_color)
        
        # 创建波形图小部件
        self.waveformPlot = pg.PlotWidget(background=self.background_color)  # 使用设定的背景色
        self.waveformPlot.setFixedHeight(self.waveform_height)  # 使用设置的高度值
        self.waveformPlot.setMouseEnabled(x=True, y=False)  # 启用X轴方向的鼠标交互
        self.waveformPlot.hideAxis('left')  # 隐藏Y轴
        self.waveformPlot.hideAxis('bottom')  # 隐藏X轴
        self.waveformPlot.setYRange(-1, 1)  # 设置固定的Y轴范围
        self.waveformPlot.setMinimumHeight(max(30, self.waveform_height))  # 确保有最小高度
        
        # 初始化波形图数据 - 使用设定的波形颜色，减小线宽使连线更细
        self.waveformCurve = self.waveformPlot.plot([], [], pen=pg.mkPen(color=self.waveform_color, width=0.8))
        self.positionLine = pg.InfiniteLine(pos=0, angle=90, pen=pg.mkPen(color=self.position_line_color, width=1.5))
        self.waveformPlot.addItem(self.positionLine)
        
        # 添加波形图点击事件处理
        self.waveformPlot.scene().sigMouseClicked.connect(self.onWaveformClicked)
        
        # 添加到主布局
        main_layout.addWidget(self.waveformPlot)
        
        print(f"波形图组件初始化成功, 组件ID: {id(self.waveformPlot)}")
        
        self.setLayout(main_layout)
    
    def onWaveformClicked(self, event):
        """处理波形图点击事件，跳转到对应位置"""
        if self.waveformCurve is None or self.duration <= 0:
            return
            
        try:
            # 获取点击位置对应的x坐标
            pos = self.waveformPlot.plotItem.vb.mapSceneToView(event.scenePos())
            x_pos = pos.x()
            
            # 获取波形图的x轴范围
            curve_data = self.waveformCurve.getData()
            if curve_data and len(curve_data[0]) > 0:
                max_x = curve_data[0][-1]
                
                # 确保位置在有效范围内
                x_pos = max(0, min(x_pos, max_x))
                
                # 计算对应的音频位置（毫秒）
                position_ratio = x_pos / max_x
                position_ms = int(position_ratio * self.duration)
                
                # 设置播放位置
                self.mediaPlayer.setPosition(position_ms)
                
                print(f"波形图点击位置: {x_pos}, 对应音频位置: {position_ms}ms")
        except Exception as e:
            print(f"处理波形图点击事件出错: {str(e)}")
            traceback.print_exc()
    
    def keyPressEvent(self, event):
        """处理键盘事件"""
        if event.key() == Qt.Key.Key_Space:
            # 空格键切换播放/暂停状态
            self.togglePlayback()
            event.accept()  # 标记事件已处理
        else:
            # 其他键交给父类处理
            super().keyPressEvent(event)
    
    def setAudioFile(self, file_path):
        """设置音频文件"""
        if not file_path:
            return False
        
        # 处理file:开头的URL
        if file_path.startswith("file:"):
            # 从URL中提取真实路径
            file_path = unquote(file_path.replace("file:///", "").replace("file://", ""))
            
        # 检查文件是否存在    
        if not os.path.exists(file_path):
            print(f"文件不存在: {file_path}")
            return False
            
        # 如果正在播放，先停止
        if self.mediaPlayer.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.mediaPlayer.stop()
        
        try:    
            self.mediaPlayer.setSource(QUrl.fromLocalFile(file_path))
            self.pathLabel.setText(os.path.basename(file_path))
            self.playPauseBtn.setEnabled(True)  # 启用播放按钮
            
            # 加载并显示波形图
            self.loadWaveform(file_path)
            
            # 设置焦点，以便直接用空格键控制
            self.setFocus()
            
            return True
        except Exception as e:
            print(f"设置音频文件出错: {str(e)}")
            traceback.print_exc()
            return False
    
    def loadWaveform(self, file_path):
        """加载并显示音频波形"""
        if self.waveformPlot is None or self.waveformCurve is None:
            print("波形图组件未初始化")
            return False
            
        try:
            print(f"开始加载波形图: {file_path}")
            
            # 使用torchaudio加载音频
            print("使用torchaudio加载音频...")
            waveform, sample_rate = torchaudio.load(file_path)
            
            # 转换为单声道
            if waveform.shape[0] > 1:
                waveform = torch.mean(waveform, dim=0, keepdim=True)
            
            # 转换为numpy数组以便处理
            audio_data = waveform.numpy()[0]  # 取第一个通道
            print(f"音频加载完成, 长度: {len(audio_data)}, 采样率: {sample_rate}")
            
            # 处理过长的音频，降采样以提高UI性能
            if len(audio_data) > 1000:
                # 限制最大点数为1000，大幅提高渲染性能
                step = max(1, len(audio_data) // 1000)
                audio_data = audio_data[::step]
                print(f"降采样后长度: {len(audio_data)}")
            
            # 标准化音频数据到-1到1之间
            max_val = np.max(np.abs(audio_data))
            if max_val > 0:
                audio_data = audio_data / max_val
            

            # 保存音频数据和采样率
            self.audio_data = audio_data
            self.sample_rate = sample_rate
            
            # 准备绘图数据 - 进一步优化点数
            # 对于超过1000个点的数据进行额外的优化：只绘制极值点和部分采样点
            if len(audio_data) > 1000:
                print("进行额外的绘图点数优化...")
                
                # 计算每个段的最大值和最小值
                segment_size = len(audio_data) // 500  # 将数据分为500段
                if segment_size < 2:
                    segment_size = 2
                
                optimized_x = []
                optimized_y = []
                
                for i in range(0, len(audio_data), segment_size):
                    segment = audio_data[i:i+segment_size]
                    if len(segment) > 0:
                        # 只添加每段的最大值和最小值点
                        max_idx = np.argmax(segment)
                        min_idx = np.argmin(segment)
                        
                        # 添加最小值点
                        optimized_x.append(i + min_idx)
                        optimized_y.append(segment[min_idx])
                        
                        # 如果最大值与最小值不是同一个点，也添加最大值点
                        if max_idx != min_idx:
                            optimized_x.append(i + max_idx)
                            optimized_y.append(segment[max_idx])
                
                # 使用优化后的数据
                x = np.array(optimized_x)
                y = np.array(optimized_y)
                print(f"优化后的绘图点数: {len(x)}")
            else:
                # 点数较少时使用全部数据
                x = np.arange(len(audio_data))
                y = audio_data
            
            # 检查曲线对象
            print(f"更新波形图，组件ID: {id(self.waveformPlot)}, 曲线ID: {id(self.waveformCurve)}")
            
            # 更新波形图数据
            self.waveformCurve.setData(x, y)
            
            # 确保波形图正确显示
            self.waveformPlot.setYRange(-1, 1)  # 重设Y轴范围
            
            # 强制更新
            self.waveformPlot.update()  # 强制更新绘图
            
            # 显示波形图组件(以防之前被隐藏)
            self.waveformPlot.show()
            
            # 重置位置线
            if self.positionLine is not None:
                self.positionLine.setValue(0)
                
            print(f"波形图更新完成，波形点数: {len(audio_data)}")
            return True
        except Exception as e:
            print(f"加载波形图出错: {str(e)}")
            traceback.print_exc()
            return False
    
    def reset(self):
        """重置播放器状态，清除音频源"""
        self.mediaPlayer.stop()
        self.mediaPlayer.setSource(QUrl())
        self.pathLabel.setText("未选择音频")
        self.playPauseBtn.setEnabled(False)
        self.timeLabel.setText("00:00 / 00:00")
        
        # 恢复播放图标
        self.playPauseBtn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        
        # 清除波形图
        if self.waveformCurve is not None:
            try:
                # 清除波形数据
                self.waveformCurve.setData([], [])
                if self.positionLine is not None:
                    self.positionLine.setValue(0)
                # 清除保存的音频数据
                self.audio_data = None
                self.sample_rate = None
            except Exception as e:
                print(f"清除波形图出错: {str(e)}")
    
    def togglePlayback(self):
        if self.mediaPlayer.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.mediaPlayer.pause()
        else:
            self.mediaPlayer.play()
    
    def stop(self):
        """停止音频播放"""
        if self.mediaPlayer.playbackState() != QMediaPlayer.PlaybackState.StoppedState:
            self.mediaPlayer.stop()
    
    def onPlaybackStateChanged(self, state):
        """监听播放状态变化"""
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.playPauseBtn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
        else:
            self.playPauseBtn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
    
    def onMediaStatusChanged(self, status):
        """监听媒体状态变化"""
        # 当播放结束时(EndOfMedia)，确保按钮显示为播放图标
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.playPauseBtn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
    
    def onPositionChanged(self, position):
        """当播放位置变化时更新时间标签和波形图位置线"""
        # 更新时间标签
        current = self.formatTime(position)
        total = self.formatTime(self.duration)
        self.timeLabel.setText(f"{current} / {total}")
        
        # 更新波形图位置线
        if self.waveformCurve is not None and self.duration > 0:
            try:
                # 计算当前位置对应的波形图x轴位置
                curve_data = self.waveformCurve.getData()
                if curve_data and len(curve_data[0]) > 0:
                    max_x = curve_data[0][-1]
                    position_ratio = position / self.duration
                    position_x = max_x * position_ratio
                    if self.positionLine is not None:
                        self.positionLine.setValue(position_x)
            except Exception as e:
                print(f"更新波形图位置线出错: {str(e)}")
    
    def onDurationChanged(self, duration):
        """当音频时长变化时更新时间标签"""
        self.duration = duration
        
        # 更新时间标签
        current = self.formatTime(self.mediaPlayer.position())
        total = self.formatTime(duration)
        self.timeLabel.setText(f"{current} / {total}")
    
    def formatTime(self, ms):
        """将毫秒转换为 mm:ss 格式"""
        s = ms // 1000
        m = s // 60
        s = s % 60
        return f"{m:02d}:{s:02d}"
    
    def getAudioPath(self):
        url_string = self.mediaPlayer.source().toString()
        # 处理URL格式路径，移除"file:"前缀
        if url_string.startswith("file:"):
            # 在Windows上，URL格式可能是file:///D:/path，需要正确转换
            path = unquote(url_string[5:])  # 移除"file:"前缀
            # 确保路径格式正确
            if path.startswith("///") and sys.platform == "win32":
                path = path[3:]  # 在Windows上移除多余的斜杠
            return path
        return url_string
    
    def setVolume(self, volume):
        """设置音量，取值范围0.0-1.0"""
        self.audioOutput.setVolume(volume)
    
    def setWaveformHeight(self, height):
        """设置波形图高度
        
        Args:
            height (int): 波形图高度（像素）
        
        Returns:
            bool: 设置是否成功
        """
        if self.waveformPlot is None:
            print("波形图不可用，无法设置高度")
            return False
            
        try:
            self.waveform_height = height
            self.waveformPlot.setFixedHeight(height)
            self.waveformPlot.setMinimumHeight(max(30, height))
            print(f"波形图高度已设为 {height} 像素")
            return True
        except Exception as e:
            print(f"设置波形图高度出错: {str(e)}")
            traceback.print_exc()
            return False
            
    def getWaveformHeight(self):
        """获取当前波形图高度
        
        Returns:
            int: 当前波形图高度（像素）
        """
        return self.waveform_height

    def setBackgroundColor(self, color):
        """设置波形图背景颜色
        
        Args:
            color: 颜色值，可以是名称字符串(如'white')、RGB元组(如(255,255,255))或十六进制字符串(如'#FFFFFF')
            
        Returns:
            bool: 设置是否成功
        """
        if self.waveformPlot is None:
            print("波形图不可用，无法设置背景颜色")
            return False
            
        try:
            self.background_color = color
            self.waveformPlot.setBackground(color)
            print(f"波形图背景颜色已设为 {color}")
            return True
        except Exception as e:
            print(f"设置波形图背景颜色出错: {str(e)}")
            traceback.print_exc()
            return False
    
    def setForegroundColor(self, color):
        """设置波形图前景颜色
        
        Args:
            color: 颜色值，可以是名称字符串(如'black')、RGB元组(如(0,0,0))或十六进制字符串(如'#000000')
            
        Returns:
            bool: 设置是否成功
        """
        if self.waveformPlot is None:
            print("波形图不可用，无法设置前景颜色")
            return False
        
        try:
            self.foreground_color = color
            # 前景色主要影响坐标轴和文本，但我们已经隐藏了坐标轴
            # 需要重新应用样式或重新创建控件才能完全生效
            print(f"波形图前景颜色已设为 {color}")
            return True
        except Exception as e:
            print(f"设置波形图前景颜色出错: {str(e)}")
            traceback.print_exc()
            return False
    
    def setWaveformColor(self, color):
        """设置波形线条颜色
        
        Args:
            color: 颜色值，可以是名称字符串(如'blue')、RGB元组(如(0,0,255))或十六进制字符串(如'#0000FF')
            
        Returns:
            bool: 设置是否成功
        """
        if self.waveformCurve is None:
            print("波形图不可用，无法设置波形颜色")
            return False
            
        try:
            self.waveform_color = color
            self.waveformCurve.setPen(pg.mkPen(color=color, width=0.8))
            print(f"波形线条颜色已设为 {color}")
            return True
        except Exception as e:
            print(f"设置波形线条颜色出错: {str(e)}")
            traceback.print_exc()
            return False
    
    def setPositionLineColor(self, color):
        """设置位置指示线颜色
        
        Args:
            color: 颜色值，可以是名称字符串(如'red')、RGB元组(如(255,0,0))或十六进制字符串(如'#FF0000')
            
        Returns:
            bool: 设置是否成功
        """
        if self.positionLine is None:
            print("波形图不可用，无法设置位置线颜色")
            return False
            
        try:
            self.position_line_color = color
            self.positionLine.setPen(pg.mkPen(color=color, width=1.5))
            print(f"位置指示线颜色已设为 {color}")
            return True
        except Exception as e:
            print(f"设置位置指示线颜色出错: {str(e)}")
            traceback.print_exc()
            return False 