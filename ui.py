import os
import sys
import time
import pickle
import threading
from pathlib import Path

# 添加typing_extensions兼容层
try:
    from typing import Self
except ImportError:
    try:
        from typing_extensions import Self
    except ImportError:
        # 如果无法导入，我们定义一个假的Self类型
        Self = object

from PySide6.QtCore import Qt, QUrl, Signal, Slot, QSize, QThread, QObject
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QTextEdit, QComboBox, QFileDialog, QListWidget, 
    QListWidgetItem, QMessageBox, QScrollArea, QSplitter, QSlider, QStyle
)
from PySide6.QtGui import QIcon, QPixmap, QFont
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput


# 工作线程类，用于执行语音生成任务
class InferenceWorker(QObject):
    # 定义信号
    finished = Signal(str)  # 推理完成信号，返回输出文件路径
    progress = Signal(str)  # 进度信号，发送处理状态信息
    error = Signal(str)     # 错误信号

    def __init__(self, tts, voice_path, text, output_path=None):
        super().__init__()
        self.tts = tts
        self.voice_path = voice_path
        self.text = text
        self.output_path = output_path

    def run(self):
        try:
            if not self.output_path:
                self.output_path = os.path.join("outputs", f"spk_{int(time.time())}.wav")
            
            # 如果文本过长，分段处理
            if len(self.text) > 500:
                self.progress.emit("文本较长，进行分段处理...")
                chunks = self.split_text(self.text, 500)
                temp_outputs = []
                
                for i, chunk in enumerate(chunks):
                    temp_path = os.path.join("outputs", f"temp_{int(time.time())}_{i}.wav")
                    self.progress.emit(f"处理第 {i+1}/{len(chunks)} 段...")
                    self.tts.infer(self.voice_path, chunk, temp_path)
                    temp_outputs.append(temp_path)
                
                # 合并所有音频片段
                self.progress.emit("合并音频片段...")
                self.merge_audio_files(temp_outputs, self.output_path)
                
                # 清理临时文件
                for temp_file in temp_outputs:
                    try:
                        os.remove(temp_file)
                    except:
                        pass
            else:
                self.progress.emit("开始语音生成...")
                self.tts.infer(self.voice_path, self.text, self.output_path)
            
            self.progress.emit("语音生成完成！")
            self.finished.emit(self.output_path)
        except Exception as e:
            self.error.emit(f"处理过程中出错: {str(e)}")
    
    def split_text(self, text, max_length):
        """将文本按句子分割成多个片段，每个片段不超过max_length字符"""
        # 常见的句子结束标记
        sentence_ends = ["。", "！", "？", "；", ".", "!", "?", ";"]
        
        chunks = []
        current_chunk = ""
        
        for char in text:
            current_chunk += char
            
            if char in sentence_ends and len(current_chunk) >= max_length / 2:
                chunks.append(current_chunk)
                current_chunk = ""
        
        # 处理最后一个片段
        if current_chunk:
            # 如果最后一个片段很短，可以与前一个合并
            if chunks and len(current_chunk) < max_length / 4 and len(chunks[-1]) + len(current_chunk) <= max_length:
                chunks[-1] += current_chunk
            else:
                chunks.append(current_chunk)
        
        return chunks
    
    def merge_audio_files(self, input_files, output_file):
        """合并多个音频文件成一个"""
        import torch
        import torchaudio
        
        # 读取所有音频
        waveforms = []
        sample_rate = None
        
        for file_path in input_files:
            waveform, sr = torchaudio.load(file_path)
            if sample_rate is None:
                sample_rate = sr
            elif sample_rate != sr:
                # 如果采样率不同，进行重采样
                waveform = torchaudio.transforms.Resample(sr, sample_rate)(waveform)
            waveforms.append(waveform)
        
        # 合并音频
        merged_waveform = torch.cat(waveforms, dim=1)
        
        # 保存合并后的音频
        torchaudio.save(output_file, merged_waveform, sample_rate)


# 添加自定义可点击滑块类
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


# 音频播放器控件
class AudioPlayer(QWidget):
    """音频播放器控件"""
    def __init__(self, label="音频播放器", parent=None):
        super().__init__(parent)
        self.label = label
        self.mediaPlayer = QMediaPlayer()
        self.audioOutput = QAudioOutput()
        self.mediaPlayer.setAudioOutput(self.audioOutput)
        self.audioOutput.setVolume(1)  # 设置默认音量为70%
        
        # 设置焦点策略，使得组件可以接收键盘事件
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        
        # 连接媒体播放器信号
        self.mediaPlayer.positionChanged.connect(self.onPositionChanged)
        self.mediaPlayer.durationChanged.connect(self.onDurationChanged)
        self.mediaPlayer.playbackStateChanged.connect(self.onPlaybackStateChanged)
        self.mediaPlayer.mediaStatusChanged.connect(self.onMediaStatusChanged)
        
        self.setupUI()
        
        # 波形图相关
        self.waveformPlot = None
        self.position_line = None
        self.audio_data = None
        self.sample_rate = None
        self.duration = 0
        
    def setupUI(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)  # 减少边距
        
        # 创建播放控制区域
        control_layout = QHBoxLayout()
        control_layout.setContentsMargins(4, 4, 4, 0)  # 减少边距
        
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
        
        # 进度条
        progress_layout = QHBoxLayout()
        progress_layout.setContentsMargins(4, 0, 4, 4)  # 减少边距
        
        # 使用自定义的可点击进度条
        self.progressSlider = ClickableSlider(Qt.Orientation.Horizontal)
        self.progressSlider.setEnabled(False)
        self.progressSlider.sliderMoved.connect(self.setPosition)
        self.progressSlider.setFixedHeight(16)
        
        progress_layout.addWidget(self.progressSlider)
        
        # 添加布局
        main_layout.addLayout(control_layout)
        main_layout.addLayout(progress_layout)
        
        # 波形图区域
        try:
            import pyqtgraph as pg
            self.has_pyqtgraph = True
            
            # 创建波形图小部件
            self.waveformPlot = pg.PlotWidget()
            self.waveformPlot.setBackground('w')  # 白色背景
            self.waveformPlot.setFixedHeight(60)
            self.waveformPlot.setMouseEnabled(x=False, y=False)  # 禁用鼠标交互
            self.waveformPlot.hideAxis('left')  # 隐藏Y轴
            self.waveformPlot.hideAxis('bottom')  # 隐藏X轴
            
            # 初始化波形图数据
            self.waveformCurve = self.waveformPlot.plot(pen=pg.mkPen(color=(30, 144, 255), width=1))
            self.positionLine = pg.InfiniteLine(pos=0, angle=90, pen=pg.mkPen(color=(255, 0, 0), width=1))
            self.waveformPlot.addItem(self.positionLine)
            
            main_layout.addWidget(self.waveformPlot)
        except ImportError:
            self.has_pyqtgraph = False
            warning_label = QLabel("注意: 安装 pyqtgraph 可显示波形图")
            warning_label.setStyleSheet("color: gray;")
            main_layout.addWidget(warning_label)
        
        self.setLayout(main_layout)
    
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
            from urllib.parse import unquote
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
            self.progressSlider.setEnabled(True)  # 启用进度条
            
            # 加载并显示波形图
            self.loadWaveform(file_path)
            
            # 设置焦点，以便直接用空格键控制
            self.setFocus()
            
            return True
        except Exception as e:
            print(f"设置音频文件出错: {str(e)}")
            return False
    
    def loadWaveform(self, file_path):
        """加载并显示音频波形"""
        try:
            import librosa
            import numpy as np
            
            # 加载音频数据（降低采样率以提高性能）
            y, sr = librosa.load(file_path, sr=22050, mono=True)
            
            # 对于过长的音频，进行降采样以提高UI性能
            if len(y) > 10000:
                y = y[::len(y)//10000]
            
            # 更新波形图
            x = np.arange(len(y))
            self.waveformCurve.setData(x, y)
            
            # 重置位置线
            self.positionLine.setValue(0)
        except Exception as e:
            print(f"加载波形图出错: {str(e)}")
    
    def reset(self):
        """重置播放器状态，清除音频源"""
        self.mediaPlayer.stop()
        self.mediaPlayer.setSource(QUrl())
        self.pathLabel.setText("未选择音频")
        self.playPauseBtn.setEnabled(False)
        self.progressSlider.setEnabled(False)
        self.timeLabel.setText("00:00 / 00:00")
        
        # 恢复播放图标
        self.playPauseBtn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        
        # 清除波形图
        if self.has_pyqtgraph:
            self.waveformCurve.setData([], [])
    
    def togglePlayback(self):
        if self.mediaPlayer.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.mediaPlayer.pause()
        else:
            self.mediaPlayer.play()
    
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
        """当播放位置变化时更新进度条和时间标签"""
        # 更新进度条
        self.progressSlider.setValue(position)
        
        # 更新时间标签
        current = self.formatTime(position)
        total = self.formatTime(self.duration)
        self.timeLabel.setText(f"{current} / {total}")
        
        # 更新波形图位置线
        if self.has_pyqtgraph and self.duration > 0:
            # 计算当前位置对应的波形图x轴位置
            curve_data = self.waveformCurve.getData()
            if curve_data and len(curve_data[0]) > 0:
                max_x = curve_data[0][-1]
                position_ratio = position / self.duration
                position_x = max_x * position_ratio
                self.positionLine.setValue(position_x)
    
    def onDurationChanged(self, duration):
        """当音频时长变化时更新进度条"""
        self.duration = duration
        self.progressSlider.setRange(0, duration)
        
        # 更新时间标签
        current = self.formatTime(self.mediaPlayer.position())
        total = self.formatTime(duration)
        self.timeLabel.setText(f"{current} / {total}")
    
    def setPosition(self, position):
        """设置播放位置（由进度条拖动触发）"""
        self.mediaPlayer.setPosition(position)
    
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
            from urllib.parse import unquote
            path = unquote(url_string[5:])  # 移除"file:"前缀
            # 确保路径格式正确
            if path.startswith("///") and sys.platform == "win32":
                path = path[3:]  # 在Windows上移除多余的斜杠
            return path
        return url_string
    
    def setVolume(self, volume):
        """设置音量，取值范围0.0-1.0"""
        self.audioOutput.setVolume(volume)


# 角色管理类
class CharacterManager:
    def __init__(self, prompt_dir="prompts"):
        self.prompt_dir = prompt_dir
        os.makedirs(prompt_dir, exist_ok=True)
    
    def save_character(self, name, voice_path):
        """保存角色到pickle文件，包含音频数据"""
        if not name or not voice_path or not os.path.exists(voice_path):
            return False
        
        try:
            # 读取音频文件的二进制内容
            with open(voice_path, 'rb') as audio_file:
                audio_data = audio_file.read()
            
            # 获取原始文件名和扩展名
            orig_filename = os.path.basename(voice_path)
            file_extension = os.path.splitext(voice_path)[1]
            
            # 创建角色数据结构
            character_data = {
                "name": name,
                "audio_data": audio_data,  # 直接保存音频二进制数据
                "audio_extension": file_extension,  # 保存扩展名以便后续使用
                "original_filename": orig_filename,  # 保存原始文件名
                "created_time": time.time()
            }
            
            # 保存到pickle文件
            pickle_path = os.path.join(self.prompt_dir, f"{name}.pickle")
            with open(pickle_path, "wb") as f:
                pickle.dump(character_data, f)
            
            return True
        except Exception as e:
            print(f"保存角色出错: {str(e)}")
            return False
    
    def load_character(self, name):
        """从pickle文件加载角色数据，包括从二进制数据还原音频文件"""
        try:
            pickle_path = os.path.join(self.prompt_dir, f"{name}.pickle")
            if not os.path.exists(pickle_path):
                return None
            
            with open(pickle_path, "rb") as f:
                character_data = pickle.load(f)
            
            # 从二进制数据创建临时音频文件
            if "audio_data" in character_data and character_data["audio_data"]:
                # 创建临时目录（如果不存在）
                temp_dir = os.path.join(self.prompt_dir, "temp")
                os.makedirs(temp_dir, exist_ok=True)
                
                # 使用原始文件名（如果存在），否则使用角色名加扩展名
                if "original_filename" in character_data and character_data["original_filename"]:
                    # 为防止文件名冲突，添加前缀
                    filename = f"{name}_{character_data['original_filename']}"
                else:
                    extension = character_data.get("audio_extension", ".wav")
                    filename = f"{name}{extension}"
                
                temp_audio_path = os.path.join(temp_dir, filename)
                
                # 写入音频数据到临时文件
                with open(temp_audio_path, "wb") as audio_file:
                    audio_file.write(character_data["audio_data"])
                
                # 将临时文件路径添加到返回数据中
                character_data["voice_path"] = temp_audio_path
            else:
                print(f"警告: 角色 {name} 的音频数据不存在")
                return None
            
            return character_data
        except Exception as e:
            print(f"加载角色出错: {str(e)}")
            return None
    
    def delete_character(self, name):
        """删除角色pickle文件"""
        try:
            pickle_path = os.path.join(self.prompt_dir, f"{name}.pickle")
            if not os.path.exists(pickle_path):
                return False
            
            # 先获取角色数据，检查原始文件名
            try:
                with open(pickle_path, "rb") as f:
                    character_data = pickle.load(f)
                    
                # 尝试删除临时文件
                temp_dir = os.path.join(self.prompt_dir, "temp")
                if os.path.exists(temp_dir):
                    # 如果有原始文件名，尝试删除对应的临时文件
                    if "original_filename" in character_data and character_data["original_filename"]:
                        temp_path = os.path.join(temp_dir, f"{name}_{character_data['original_filename']}")
                        if os.path.exists(temp_path):
                            os.remove(temp_path)
                    else:
                        # 否则尝试删除各种可能的扩展名文件
                        for ext in [".wav", ".mp3", ".flac", ".ogg"]:
                            temp_path = os.path.join(temp_dir, f"{name}{ext}")
                            if os.path.exists(temp_path):
                                os.remove(temp_path)
            except:
                pass  # 即使获取角色数据失败，也继续删除pickle文件
            
            # 删除pickle文件
            os.remove(pickle_path)
            return True
        except Exception as e:
            print(f"删除角色出错: {str(e)}")
            return False
    
    def get_all_characters(self):
        """获取所有角色名称列表"""
        try:
            character_names = []
            for file in os.listdir(self.prompt_dir):
                if file.endswith(".pickle"):
                    name = os.path.splitext(file)[0]
                    character_names.append(name)
            return character_names
        except Exception as e:
            print(f"获取角色列表出错: {str(e)}")
            return []
    
    def export_character(self, name, export_path):
        """将角色导出为单独的文件"""
        try:
            pickle_path = os.path.join(self.prompt_dir, f"{name}.pickle")
            if not os.path.exists(pickle_path):
                return False
            
            import shutil
            shutil.copy2(pickle_path, export_path)
            return True
        except Exception as e:
            print(f"导出角色出错: {str(e)}")
            return False
    
    def import_character(self, import_path):
        """从外部文件导入角色"""
        try:
            if not os.path.exists(import_path) or not import_path.endswith('.pickle'):
                return False, "无效的角色文件"
            
            # 尝试加载文件验证格式
            try:
                with open(import_path, 'rb') as f:
                    data = pickle.load(f)
                if not isinstance(data, dict) or "name" not in data or "audio_data" not in data:
                    return False, "文件格式错误，不是有效的角色文件"
            except:
                return False, "文件损坏或格式错误"
            
            # 提取角色名
            character_name = data["name"]
            
            # 检查是否已存在同名角色
            if os.path.exists(os.path.join(self.prompt_dir, f"{character_name}.pickle")):
                return False, f"已存在同名角色 '{character_name}'"
            
            # 复制文件到prompts目录
            import shutil
            dest_path = os.path.join(self.prompt_dir, f"{character_name}.pickle")
            shutil.copy2(import_path, dest_path)
            
            return True, character_name
        except Exception as e:
            print(f"导入角色出错: {str(e)}")
            return False, str(e)


# 主窗口类
class MainWindow(QMainWindow):
    def __init__(self, tts_model):
        super().__init__()
        
        self.tts = tts_model
        self.character_manager = CharacterManager()
        self.inference_thread = None
        self.inference_worker = None
        
        self.setupUI()
        self.loadHistoryAudio()
        
        # 添加程序退出时的清理工作
        app = QApplication.instance()
        if app:
            app.aboutToQuit.connect(self.cleanupOnExit)
    
    def setupUI(self):
        self.setWindowTitle("IndexTTS 语音生成界面")
        self.setMinimumSize(800, 600)
        
        # 创建主布局
        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)
        self.main_layout = QVBoxLayout(self.main_widget)
        
        # 创建选项卡
        self.tab_widget = QTabWidget()
        self.main_layout.addWidget(self.tab_widget)
        
        # 创建"推理界面"选项卡
        self.inference_tab = QWidget()
        self.setupInferenceTab()
        self.tab_widget.addTab(self.inference_tab, "推理界面")
        
        # 状态栏
        self.statusBar().showMessage("就绪")
    
    def setupInferenceTab(self):
        layout = QVBoxLayout(self.inference_tab)
        
        # 创建一个分割器，上面是主要操作区域，下面是历史记录
        splitter = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(splitter)
        
        # 上半部分 - 主要操作区域
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        
        # 角色选择区域
        char_widget = QWidget()
        char_layout = QHBoxLayout(char_widget)
        
        char_label = QLabel("角色名:")
        self.char_combo = QComboBox()
        self.char_combo.setMinimumWidth(150)
        self.char_combo.currentIndexChanged.connect(self.onCharacterSelected)
        
        self.load_char_btn = QPushButton("加载")
        self.load_char_btn.clicked.connect(self.loadCharacter)
        
        self.save_char_btn = QPushButton("保存/更新")
        self.save_char_btn.clicked.connect(self.saveCharacter)
        
        self.delete_char_btn = QPushButton("删除")
        self.delete_char_btn.clicked.connect(self.deleteCharacter)
        
        # 添加导出和导入按钮
        self.export_char_btn = QPushButton("导出")
        self.export_char_btn.clicked.connect(self.exportCharacter)
        
        self.import_char_btn = QPushButton("导入")
        self.import_char_btn.clicked.connect(self.importCharacter)
        
        char_layout.addWidget(char_label)
        char_layout.addWidget(self.char_combo)
        char_layout.addWidget(self.load_char_btn)
        char_layout.addWidget(self.save_char_btn)
        char_layout.addWidget(self.delete_char_btn)
        char_layout.addWidget(self.export_char_btn)  # 添加导出按钮
        char_layout.addWidget(self.import_char_btn)  # 添加导入按钮
        char_layout.addStretch(1)
        
        top_layout.addWidget(char_widget)
        
        # 参考音频区域
        self.ref_audio_player = AudioPlayer()
        
        self.select_ref_btn = QPushButton("选择参考音频")
        self.select_ref_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))
        self.select_ref_btn.clicked.connect(self.selectReferenceAudio)
        
        # 音频控制区域
        ref_layout = QHBoxLayout()
        ref_layout.addWidget(self.select_ref_btn)  # 选择参考音频按钮放在最前面
        ref_layout.addWidget(self.ref_audio_player, 1)
        
        top_layout.addLayout(ref_layout)
        
        # 推理文本区域
        text_label = QLabel("推理文本:")
        self.text_edit = QTextEdit()
        self.text_edit.setAcceptRichText(False)
        self.text_edit.setPlaceholderText("在此输入要转换为语音的文本...")
        # 设置默认最小高度为5行文本高度（大约每行20像素）
        self.text_edit.setMinimumHeight(100)
        
        top_layout.addWidget(text_label)
        top_layout.addWidget(self.text_edit)
        
        # 推理按钮 - 上移到此处，紧跟文本编辑器
        self.infer_btn = QPushButton("生成语音")
        self.infer_btn.setMinimumHeight(40)
        self.infer_btn.clicked.connect(self.startInference)
        
        top_layout.addWidget(self.infer_btn)
        
        # 推理结果区域 - 删除标签
        self.result_audio_player = AudioPlayer()
        
        result_layout = QHBoxLayout()
        result_layout.addWidget(self.result_audio_player, 1)
        
        top_layout.addLayout(result_layout)
        
        # 下半部分 - 历史记录
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        
        history_label = QLabel("历史结果音频:")
        self.history_list = QListWidget()
        self.history_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.history_list.itemClicked.connect(self.onHistoryItemClicked)
        
        # 添加刷新按钮
        refresh_btn = QPushButton("刷新列表")
        refresh_btn.clicked.connect(self.loadHistoryAudio)
        
        bottom_layout.addWidget(history_label)
        bottom_layout.addWidget(self.history_list)
        bottom_layout.addWidget(refresh_btn)
        
        # 添加到分割器
        splitter.addWidget(top_widget)
        splitter.addWidget(bottom_widget)
        splitter.setSizes([int(self.height() * 0.7), int(self.height() * 0.3)])
        
        # 更新角色下拉列表
        self.updateCharacterComboBox()
    
    def loadHistoryAudio(self):
        """加载历史音频文件列表"""
        self.history_list.clear()
        
        try:
            output_dir = Path("outputs")
            output_dir.mkdir(exist_ok=True)
            
            # 获取所有wav文件并按修改时间排序
            wav_files = [f for f in output_dir.glob("*.wav") if f.is_file()]
            wav_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            for wav_file in wav_files:
                item = QListWidgetItem(wav_file.name)
                item.setData(Qt.ItemDataRole.UserRole, str(wav_file))
                self.history_list.addItem(item)
        except Exception as e:
            QMessageBox.warning(self, "错误", f"加载历史音频时出错: {str(e)}")
    
    def onHistoryItemClicked(self, item):
        """当历史音频列表项被点击时的处理"""
        file_path = item.data(Qt.ItemDataRole.UserRole)
        if file_path:
            if not self.result_audio_player.setAudioFile(file_path):
                QMessageBox.warning(self, "警告", f"无法加载音频文件: {os.path.basename(file_path)}")
            else:
                self.statusBar().showMessage(f"已加载历史音频: {os.path.basename(file_path)}", 3000)
    
    def updateCharacterComboBox(self):
        """更新角色下拉列表"""
        self.char_combo.clear()
        
        # 添加一个空选项
        self.char_combo.addItem("-- 选择角色 --", None)
        
        # 获取所有角色
        characters = self.character_manager.get_all_characters()
        for name in characters:
            self.char_combo.addItem(name, name)
    
    def onCharacterSelected(self, index):
        """角色选择改变时的处理"""
        if index <= 0:  # 空选项
            return
        
        name = self.char_combo.itemData(index)
        if not name:
            return
        
        # 加载角色数据
        character_data = self.character_manager.load_character(name)
        if character_data and "voice_path" in character_data:
            self.ref_audio_player.setAudioFile(character_data["voice_path"])
    
    def loadCharacter(self):
        """加载选中的角色"""
        index = self.char_combo.currentIndex()
        if index <= 0:
            QMessageBox.warning(self, "警告", "请先选择一个角色")
            return
        
        name = self.char_combo.itemData(index)
        character_data = self.character_manager.load_character(name)
        
        if not character_data:
            QMessageBox.warning(self, "错误", f"无法加载角色 '{name}'")
            return
        
        # 更新参考音频
        if "voice_path" in character_data:
            if self.ref_audio_player.setAudioFile(character_data["voice_path"]):
                QMessageBox.information(self, "成功", f"成功加载角色 '{name}'")
            else:
                QMessageBox.warning(self, "警告", f"角色 '{name}' 的音频文件无效或不存在")
    
    def saveCharacter(self):
        """保存/更新角色"""
        # 获取参考音频路径
        voice_path = self.ref_audio_player.getAudioPath()
        if not voice_path:
            QMessageBox.warning(self, "警告", "请先选择参考音频")
            return
        
        # 获取当前选中的角色名，如果有的话
        current_index = self.char_combo.currentIndex()
        current_name = self.char_combo.itemData(current_index) if current_index > 0 else None
        
        # 弹出对话框输入角色名
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(
            self, "保存角色", "请输入角色名称:", 
            text=current_name if current_name else ""
        )
        
        if not ok or not name:
            return
        
        # 保存角色
        if self.character_manager.save_character(name, voice_path):
            QMessageBox.information(self, "成功", f"成功保存角色 '{name}'")
            # 刷新角色列表
            self.updateCharacterComboBox()
            # 选中新保存的角色
            index = self.char_combo.findData(name)
            if index >= 0:
                self.char_combo.setCurrentIndex(index)
        else:
            QMessageBox.warning(self, "错误", f"保存角色 '{name}' 失败")
    
    def deleteCharacter(self):
        """删除选中的角色"""
        index = self.char_combo.currentIndex()
        if index <= 0:
            QMessageBox.warning(self, "警告", "请先选择一个角色")
            return
        
        name = self.char_combo.itemData(index)
        
        # 确认删除
        reply = QMessageBox.question(
            self, "确认删除", 
            f"确定要删除角色 '{name}' 吗？此操作不可恢复。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if self.character_manager.delete_character(name):
                QMessageBox.information(self, "成功", f"成功删除角色 '{name}'")
                # 刷新角色列表
                self.updateCharacterComboBox()
            else:
                QMessageBox.warning(self, "错误", f"删除角色 '{name}' 失败")
    
    def selectReferenceAudio(self):
        """选择参考音频文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择参考音频文件", "", "音频文件 (*.wav *.mp3 *.flac *.ogg)"
        )
        
        if file_path:
            if not self.ref_audio_player.setAudioFile(file_path):
                QMessageBox.warning(self, "警告", "所选文件无效或无法作为音频播放")
            else:
                self.statusBar().showMessage(f"已选择参考音频: {os.path.basename(file_path)}", 3000)
    
    def startInference(self):
        """开始语音生成推理"""
        # 获取参考音频路径
        voice_path = self.ref_audio_player.getAudioPath()
        if not voice_path:
            QMessageBox.warning(self, "警告", "请先选择参考音频")
            return
        
        # 获取输入文本
        text = self.text_edit.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "警告", "请输入推理文本")
            return
        
        # 禁用推理按钮，防止重复点击
        self.infer_btn.setEnabled(False)
        self.infer_btn.setText("生成中...")
        self.statusBar().showMessage("正在生成语音...")
        
        # 创建输出路径
        output_path = os.path.join("outputs", f"spk_{int(time.time())}.wav")
        
        # 创建工作线程
        self.inference_thread = QThread()
        self.inference_worker = InferenceWorker(self.tts, voice_path, text, output_path)
        self.inference_worker.moveToThread(self.inference_thread)
        
        # 连接信号
        self.inference_thread.started.connect(self.inference_worker.run)
        self.inference_worker.finished.connect(self.onInferenceFinished)
        self.inference_worker.progress.connect(self.onInferenceProgress)
        self.inference_worker.error.connect(self.onInferenceError)
        self.inference_worker.finished.connect(self.inference_thread.quit)
        self.inference_worker.finished.connect(self.inference_worker.deleteLater)
        self.inference_thread.finished.connect(self.inference_thread.deleteLater)
        
        # 启动线程
        self.inference_thread.start()
    
    def onInferenceFinished(self, output_path):
        """推理完成时的处理"""
        # 更新界面
        self.infer_btn.setEnabled(True)
        self.infer_btn.setText("生成语音")
        self.statusBar().showMessage("语音生成完成", 5000)
        
        # 播放生成的音频
        self.result_audio_player.setAudioFile(output_path)
        
        # 刷新历史列表
        self.loadHistoryAudio()
    
    def onInferenceProgress(self, message):
        """处理推理进度更新"""
        self.statusBar().showMessage(message)
    
    def onInferenceError(self, error_message):
        """处理推理错误"""
        self.infer_btn.setEnabled(True)
        self.infer_btn.setText("生成语音")
        self.statusBar().showMessage("生成失败", 5000)
        
        QMessageBox.critical(self, "错误", error_message)
    
    def cleanupOnExit(self):
        """程序退出前清理临时文件"""
        try:
            temp_dir = os.path.join(self.character_manager.prompt_dir, "temp")
            if os.path.exists(temp_dir):
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
                print("临时文件清理完成")
        except Exception as e:
            print(f"清理临时文件出错: {str(e)}")
    
    def exportCharacter(self):
        """导出选中的角色为单独文件"""
        index = self.char_combo.currentIndex()
        if index <= 0:
            QMessageBox.warning(self, "警告", "请先选择一个角色")
            return
        
        name = self.char_combo.itemData(index)
        
        # 选择保存路径
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出角色", f"{name}.pickle", "角色文件 (*.pickle)"
        )
        
        if file_path:
            if self.character_manager.export_character(name, file_path):
                QMessageBox.information(self, "成功", f"角色 '{name}' 已成功导出")
            else:
                QMessageBox.warning(self, "错误", f"导出角色 '{name}' 失败")
    
    def importCharacter(self):
        """从外部文件导入角色"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "导入角色", "", "角色文件 (*.pickle)"
        )
        
        if file_path:
            success, message = self.character_manager.import_character(file_path)
            if success:
                QMessageBox.information(self, "成功", f"角色 '{message}' 已成功导入")
                # 刷新角色列表
                self.updateCharacterComboBox()
                # 选中新导入的角色
                index = self.char_combo.findData(message)
                if index >= 0:
                    self.char_combo.setCurrentIndex(index)
            else:
                QMessageBox.warning(self, "导入失败", message)


# 主函数
def main():
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