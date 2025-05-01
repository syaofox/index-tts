"""主窗口视图
提供IndexTTS的主界面。
"""

import os
import time
from pathlib import Path

from PySide6.QtCore import Qt, QThread
from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QTextEdit, QComboBox, QFileDialog, QListWidget, 
    QListWidgetItem, QMessageBox, QSplitter, QStyle, QInputDialog, QCheckBox
)

from ui.views.audio_player import AudioPlayer
from ui.views.custom_widgets import DropFileButton
from ui.models.character_manager import CharacterManager
from ui.controllers.inference_worker import InferenceWorker


class MainWindow(QMainWindow):
    """IndexTTS主窗口类"""
    def __init__(self, tts_model):
        super().__init__()
        
        self.tts = tts_model
        self.character_manager = CharacterManager()
        self.inference_thread = None
        self.inference_worker = None
        
        self.setupUI()
        self.loadHistoryAudio()
        
        # 添加程序退出时的清理工作
        from PySide6.QtWidgets import QApplication
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
        char_layout.addWidget(self.export_char_btn)
        char_layout.addWidget(self.import_char_btn)
        char_layout.addStretch(1)
        
        top_layout.addWidget(char_widget)
        
        # 参考音频区域
        self.ref_audio_player = AudioPlayer()
        
        # 使用支持拖放的按钮替换原来的按钮
        self.select_ref_btn = DropFileButton("选择参考音频")
        self.select_ref_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))
        self.select_ref_btn.clicked.connect(self.selectReferenceAudio)
        # 连接文件拖放信号
        self.select_ref_btn.fileDropped.connect(self.onReferenceAudioDropped)
        
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
        
        # 文本分割设置区域
        text_split_widget = QWidget()
        text_split_layout = QHBoxLayout(text_split_widget)
        
        # 标点符号设置
        punct_label = QLabel("分割标点:")
        self.punct_edit = QTextEdit()
        self.punct_edit.setFixedHeight(28)  # 设置为单行高度
        self.punct_edit.setPlaceholderText("例如: 。？！，；")
        self.punct_edit.setText("。？！")
        
        text_split_layout.addWidget(punct_label)
        text_split_layout.addWidget(self.punct_edit)
        
        # 停顿时间设置
        pause_label = QLabel("停顿时间(秒):")
        self.pause_edit = QTextEdit()
        self.pause_edit.setFixedHeight(28)  # 设置为单行高度
        self.pause_edit.setPlaceholderText("默认: 0.3")
        self.pause_edit.setText("0.3")
        
        text_split_layout.addWidget(pause_label)
        text_split_layout.addWidget(self.pause_edit)
        text_split_layout.addStretch(1)
        
        top_layout.addWidget(text_split_widget)
        
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
            self, "选择参考音频", "", "音频文件 (*.wav *.mp3 *.flac *.ogg *.aac)"
        )
        
        if file_path:
            if not self.ref_audio_player.setAudioFile(file_path):
                QMessageBox.warning(self, "警告", "所选文件无效或无法作为音频播放")
            else:
                self.statusBar().showMessage(f"已选择参考音频: {os.path.basename(file_path)}", 3000)
    
    def onReferenceAudioDropped(self, file_path):
        """处理拖放到选择参考音频按钮上的文件"""
        # 检查文件是否为支持的音频格式
        file_ext = os.path.splitext(file_path)[1].lower()
        supported_exts = ['.wav', '.mp3', '.flac', '.ogg', '.aac']
        
        if file_ext not in supported_exts:
            QMessageBox.warning(self, "警告", "不支持的音频格式，请使用WAV、MP3、FLAC、OGG或AAC格式")
            return
        
        # 直接加载音频文件
        if not self.ref_audio_player.setAudioFile(file_path):
            QMessageBox.warning(self, "警告", "所选文件无效或无法作为音频播放")
        else:
            self.statusBar().showMessage(f"已加载拖放的参考音频: {os.path.basename(file_path)}", 3000)
    
    def startInference(self):
        """开始推理处理"""
        print("开始推理过程...")
        
        # 检查是否有推理任务正在进行
        # 使用更安全的方式检查线程状态，避免访问可能已被删除的对象
        try:
            thread_running = self.inference_thread is not None and self.inference_thread.isRunning()
        except (RuntimeError, ReferenceError):
            # 如果对象已被删除，将线程引用设为None并继续
            print("检测到线程对象已被删除，重置引用")
            self.inference_thread = None
            self.inference_worker = None
            thread_running = False
            
        if thread_running:
            # 如果当前有推理任务在运行，则停止推理
            print("推理任务正在运行，准备停止")
            self.stopInference()
            return
        else:
            print("当前无活动推理线程，可以开始新任务")
            
        text = self.text_edit.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "警告", "请输入要转换为语音的文本")
            return
        
        # 获取参考音频路径
        voice_path = self.ref_audio_player.getAudioPath()
        if not voice_path:
            QMessageBox.warning(self, "警告", "请先选择参考音频")
            return
        
        # 获取标点符号和停顿时间
        punct_chars = self.punct_edit.toPlainText()
        
        # 获取停顿时间并验证
        try:
            pause_time = float(self.pause_edit.toPlainText())
            if pause_time < 0:
                raise ValueError("停顿时间不能为负数")
        except ValueError:
            QMessageBox.warning(self, "警告", "请输入有效的停顿时间（秒）")
            return
        
        # 停止所有音频播放
        self.ref_audio_player.stop()
        self.result_audio_player.stop()
        
        # 禁用所有按钮，除了合成按钮（现在是停止按钮）
        self.disableUIControls(True)
        
        # 将合成按钮变成停止按钮
        self.infer_btn.setText("停止生成")
        self.statusBar().showMessage("正在生成语音...")
        
        # 创建输出路径
        output_path = os.path.join("outputs", f"spk_{int(time.time())}.wav")
        
        # 创建并启动推理线程
        self.inference_thread = QThread()
        self.inference_worker = InferenceWorker(
            self.tts, 
            voice_path, 
            text,
            output_path=output_path,
            punct_chars=punct_chars,
            pause_time=pause_time
        )
        
        # 连接信号
        self.inference_worker.moveToThread(self.inference_thread)
        self.inference_thread.started.connect(self.inference_worker.run)
        self.inference_worker.finished.connect(self.onInferenceFinished)
        self.inference_worker.progress.connect(self.onInferenceProgress)
        self.inference_worker.error.connect(self.onInferenceError)
        # 确保推理完成或出错时线程退出
        self.inference_worker.finished.connect(self.inference_thread.quit)
        self.inference_worker.error.connect(self.inference_thread.quit)
        
        # 启动线程
        self.inference_thread.start()
        print(f"推理线程已启动: {self.inference_thread}")
    
    def stopInference(self):
        """停止当前正在进行的推理任务"""
        if self.inference_worker is not None:
            # 发送停止请求
            self.inference_worker.stop()
            self.statusBar().showMessage("正在停止语音生成...")
    
    def disableUIControls(self, disable=True):
        """禁用或启用UI控件"""
        # 禁用/启用角色选择区域按钮
        self.char_combo.setEnabled(not disable)
        self.load_char_btn.setEnabled(not disable)
        self.save_char_btn.setEnabled(not disable)
        self.delete_char_btn.setEnabled(not disable)
        self.export_char_btn.setEnabled(not disable)
        self.import_char_btn.setEnabled(not disable)
        
        # 禁用/启用参考音频区域
        self.select_ref_btn.setEnabled(not disable)
        self.ref_audio_player.setEnabled(not disable)
        
        # 禁用/启用文本编辑区域
        self.text_edit.setEnabled(not disable)
        self.punct_edit.setEnabled(not disable)
        self.pause_edit.setEnabled(not disable)
        
        # 禁用/启用历史列表
        self.history_list.setEnabled(not disable)
        
        # 结果音频播放器
        self.result_audio_player.setEnabled(not disable)
        
        # 注意：不禁用推理按钮，它用作停止按钮
    
    def onInferenceFinished(self, output_path):
        """推理完成时的处理"""
        print(f"推理完成，输出路径: {output_path}")
        # 更新界面
        self.infer_btn.setText("生成语音")
        self.statusBar().showMessage("语音生成完成", 5000)
        
        # 启用所有按钮
        self.disableUIControls(False)
        
        # 播放生成的音频
        self.result_audio_player.setAudioFile(output_path)
        
        # 刷新历史列表
        self.loadHistoryAudio()
        
        # 安全重置线程状态
        print(f"推理完成，开始重置线程状态...")
        self.safeResetInferenceThread()
    
    def onInferenceProgress(self, message):
        """处理推理进度更新"""
        self.statusBar().showMessage(message)
    
    def onInferenceError(self, error_message):
        """处理推理错误"""
        print(f"推理出错: {error_message}")
        self.infer_btn.setText("生成语音")
        self.statusBar().showMessage("生成失败", 5000)
        
        # 启用所有按钮
        self.disableUIControls(False)
        
        # 如果不是用户主动中断，则显示错误消息
        if error_message != "推理已被用户中断":
            QMessageBox.critical(self, "错误", error_message)
        else:
            self.statusBar().showMessage("用户已中断语音生成", 5000)
        
        # 安全重置线程状态
        print(f"推理出错，开始重置线程状态...")
        self.safeResetInferenceThread()
    
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
    
    def safeResetInferenceThread(self):
        """安全地重置推理线程和工作器的状态"""
        try:
            # 如果线程还在运行，尝试先退出
            if self.inference_thread is not None and self.inference_thread.isRunning():
                print("线程仍在运行，尝试退出...")
                self.inference_thread.quit()
                # 等待最多2秒钟线程退出
                if not self.inference_thread.wait(2000):
                    print("线程退出超时，尝试强制终止")
                    self.inference_thread.terminate()
                    self.inference_thread.wait()
        except (RuntimeError, ReferenceError) as e:
            print(f"重置线程时出错: {e}")
        
        # 重置引用
        self.inference_thread = None
        self.inference_worker = None
        print("线程状态已安全重置") 