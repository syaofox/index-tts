"""主窗口视图
提供IndexTTS的主界面。
"""

import os
import time
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QThread
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QTextEdit, QComboBox, QFileDialog, QListWidget, 
    QListWidgetItem, QMessageBox, QSplitter, QStyle, QInputDialog, QCheckBox,
    QMenu
)

from ui.views.audio_player import AudioPlayer
from ui.views.custom_widgets import DropFileButton
from ui.models.character_manager import CharacterManager
from ui.utils.text_processor import TextProcessor
from ui.controllers.single_role_worker import SingleRoleInferenceWorker
from ui.controllers.multi_role_worker import MultiRoleInferenceWorker
from ui.config import REPLACE_RULES_CONFIG_PATH, AUDIO_PLAYER_PATH, DEFAULT_PUNCT_CHARS, DEFAULT_PAUSE_TIME


class MainWindow(QMainWindow):
    """IndexTTS主窗口类"""
    def __init__(self, tts_model):
        super().__init__()
        
        self.tts = tts_model
        self.character_manager = CharacterManager()
        self.inference_thread = None
        self.inference_worker = None
        
        # 替换规则配置文件路径
        self.replace_config_path = REPLACE_RULES_CONFIG_PATH
        
        self.setupUI()
        self.loadHistoryAudio()
        
        # 添加程序退出时的清理工作
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            app.aboutToQuit.connect(self.cleanupOnExit)
    
    def setupUI(self):
        self.setWindowTitle("IndexTTS 语音生成界面")
        self.setMinimumSize(500, 900)
        
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
        
        # 创建"替换规则"选项卡
        self.replace_rules_tab = QWidget()
        self.setupReplaceRulesTab()
        self.tab_widget.addTab(self.replace_rules_tab, "替换规则")
        
        # 状态栏
        self.statusBar().showMessage("就绪")
    
    def setupReplaceRulesTab(self):
        """创建替换规则编辑选项卡"""
        layout = QVBoxLayout(self.replace_rules_tab)
        
        # 添加说明标签
        help_label = QLabel("编辑文本替换规则配置\n格式：查找字符串|需修改字符串|替换后的字符串\n示例：你好呀|你好|sa3 bi1")
        help_label.setWordWrap(True)
        layout.addWidget(help_label)
        
        # 创建上下分割器
        splitter = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(splitter)
        
        # 上部分 - 规则编辑区域
        edit_widget = QWidget()
        edit_layout = QVBoxLayout(edit_widget)
        
        # 添加文本编辑器
        self.rules_edit = QTextEdit()
        self.rules_edit.setAcceptRichText(False)
        self.rules_edit.setPlaceholderText("请输入替换规则，每行一条...")
        edit_layout.addWidget(self.rules_edit)
        
        # 创建按钮区域
        buttons_layout = QHBoxLayout()
        
        # 添加加载按钮
        self.load_rules_btn = QPushButton("加载规则")
        self.load_rules_btn.clicked.connect(self.loadReplaceRules)
        buttons_layout.addWidget(self.load_rules_btn)
        
        # 添加保存按钮
        self.save_rules_btn = QPushButton("保存规则")
        self.save_rules_btn.clicked.connect(self.saveReplaceRules)
        buttons_layout.addWidget(self.save_rules_btn)
        
        # 添加刷新按钮
        self.refresh_rules_btn = QPushButton("重置")
        self.refresh_rules_btn.clicked.connect(self.resetReplaceRules)
        buttons_layout.addWidget(self.refresh_rules_btn)
        
        # 添加按钮布局
        buttons_layout.addStretch(1)
        edit_layout.addLayout(buttons_layout)
        
        # 下部分 - 规则测试区域
        test_widget = QWidget()
        test_layout = QVBoxLayout(test_widget)
        
        # 测试区域标题
        test_label = QLabel("规则测试")
        test_label.setStyleSheet("font-weight: bold;")
        test_layout.addWidget(test_label)
        
        # 测试输入
        test_input_label = QLabel("测试文本:")
        self.test_input = QTextEdit()
        self.test_input.setPlaceholderText("输入要测试的文本...")
        self.test_input.setMaximumHeight(80)
        test_layout.addWidget(test_input_label)
        test_layout.addWidget(self.test_input)
        
        # 测试结果
        test_result_label = QLabel("替换结果:")
        self.test_result = QTextEdit()
        self.test_result.setReadOnly(True)
        self.test_result.setPlaceholderText("替换后的文本将显示在这里...")
        self.test_result.setMaximumHeight(80)
        test_layout.addWidget(test_result_label)
        test_layout.addWidget(self.test_result)
        
        # 测试按钮
        self.test_rules_btn = QPushButton("测试替换规则")
        self.test_rules_btn.clicked.connect(self.testReplaceRules)
        test_layout.addWidget(self.test_rules_btn)
        
        # 添加到分割器
        splitter.addWidget(edit_widget)
        splitter.addWidget(test_widget)
        splitter.setSizes([int(self.height() * 0.7), int(self.height() * 0.3)])
        
        # 自动加载文件内容
        self.loadReplaceRules()
    
    def testReplaceRules(self):
        """测试替换规则效果"""
        try:
            # 获取测试文本
            test_text = self.test_input.toPlainText()
            if not test_text:
                QMessageBox.warning(self, "警告", "请输入测试文本")
                return
            
            # 获取规则文本
            rules_text = self.rules_edit.toPlainText()
            if not self.validateReplaceRules(rules_text):
                return
            
            # 解析规则
            rules = []
            for line in rules_text.split('\n'):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split('|')
                if len(parts) == 3:
                    search_str, replace_from, replace_to = parts
                    rules.append((search_str, replace_from, replace_to))
            
            # 应用规则
            result_text = test_text
            for search_str, replace_from, replace_to in rules:
                if search_str in result_text:
                    modified_search_str = search_str.replace(replace_from, replace_to)
                    result_text = result_text.replace(search_str, modified_search_str)
            
            # 显示结果
            self.test_result.setPlainText(result_text)
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"测试替换规则时出错: {str(e)}")
    
    def loadReplaceRules(self):
        """加载替换规则配置文件"""
        try:
            if os.path.exists(self.replace_config_path):
                with open(self.replace_config_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.rules_edit.setPlainText(content)
                self.statusBar().showMessage("替换规则已加载", 3000)
            else:
                self.rules_edit.setPlainText("# 格式：查找字符串|需修改字符串|替换后的字符串")
                self.statusBar().showMessage("配置文件不存在，已创建默认模板", 3000)
        except Exception as e:
            QMessageBox.warning(self, "错误", f"加载替换规则配置文件失败: {str(e)}")
    
    def saveReplaceRules(self):
        """保存替换规则配置文件"""
        try:
            # 验证规则格式
            content = self.rules_edit.toPlainText()
            if not self.validateReplaceRules(content):
                return
            
            # 确保目录存在
            os.makedirs(os.path.dirname(self.replace_config_path), exist_ok=True)
            
            # 保存文件
            with open(self.replace_config_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            QMessageBox.information(self, "成功", "替换规则已成功保存")
            self.statusBar().showMessage("替换规则已保存", 3000)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存替换规则配置文件失败: {str(e)}")
    
    def validateReplaceRules(self, content):
        """验证替换规则格式是否正确"""
        lines = content.split('\n')
        errors = []
        line_number = 0
        
        for line in lines:
            line_number += 1
            line = line.strip()
            
            # 跳过空行和注释行
            if not line or line.startswith('#'):
                continue
            
            # 验证格式是否为 "查找字符串|需修改字符串|替换后的字符串"
            parts = line.split('|')
            if len(parts) != 3:
                errors.append(f"第 {line_number} 行: 格式错误，应为 '查找字符串|需修改字符串|替换后的字符串'")
                continue
            
            # 验证所有部分都不为空
            search_str, replace_from, replace_to = parts
            if not search_str.strip():
                errors.append(f"第 {line_number} 行: '查找字符串' 不能为空")
            
            if not replace_from.strip():
                errors.append(f"第 {line_number} 行: '需修改字符串' 不能为空")
            
            # 验证需修改字符串是查找字符串的子串
            if replace_from not in search_str:
                errors.append(f"第 {line_number} 行: '需修改字符串' 必须是 '查找字符串' 的子串")
        
        # 如果有错误，显示错误信息
        if errors:
            error_message = "替换规则格式有误:\n" + "\n".join(errors)
            QMessageBox.warning(self, "格式错误", error_message)
            return False
        
        return True
    
    def resetReplaceRules(self):
        """重置编辑器内容为原始文件内容"""
        reply = QMessageBox.question(
            self, "确认重置", 
            "确定要重置编辑器内容吗？未保存的更改将丢失。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.loadReplaceRules()
    
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
        
        # 添加右键菜单
        self.text_edit.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.text_edit.customContextMenuRequested.connect(self.showTextEditContextMenu)
        
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
        self.punct_edit.setText(DEFAULT_PUNCT_CHARS)
        
        text_split_layout.addWidget(punct_label)
        text_split_layout.addWidget(self.punct_edit)
        
        # 停顿时间设置
        pause_label = QLabel("停顿时间(秒):")
        self.pause_edit = QTextEdit()
        self.pause_edit.setFixedHeight(28)  # 设置为单行高度
        self.pause_edit.setPlaceholderText(f"默认: {DEFAULT_PAUSE_TIME}")
        self.pause_edit.setText(DEFAULT_PAUSE_TIME)
        
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
        # 添加双击事件
        self.history_list.itemDoubleClicked.connect(self.onHistoryItemDoubleClicked)
        
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
                # 获取文件的创建/修改时间并格式化
                file_mtime = wav_file.stat().st_mtime
                mtime_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(file_mtime))
                
                # 显示日期和文件名
                display_text = f"{mtime_str} - {wav_file.name}"
                
                item = QListWidgetItem(display_text)
                item.setData(Qt.ItemDataRole.UserRole, str(wav_file))
                self.history_list.addItem(item)
                
                # 增加提示信息，显示完整路径
                item.setToolTip(str(wav_file.absolute()))
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
    
    def onHistoryItemDoubleClicked(self, item):
        """当历史音频列表项被双击时的处理，使用外部播放器打开音频文件"""
        file_path = item.data(Qt.ItemDataRole.UserRole)
        if file_path:
            try:
                # 检查文件是否存在
                if not os.path.exists(file_path):
                    QMessageBox.warning(self, "警告", f"文件不存在: {os.path.basename(file_path)}")
                    return
                
                # 使用配置的外部播放器打开文件
                if AUDIO_PLAYER_PATH:
                    # 检测是否是Adobe Audition
                    if "Adobe Audition" in AUDIO_PLAYER_PATH:
                        # 对于Audition，使用完整路径并处理可能的引号问题
                        abs_file_path = os.path.abspath(file_path)
                        try:
                            # 方法1：尝试直接使用进程启动
                            subprocess.Popen([AUDIO_PLAYER_PATH, abs_file_path])
                            self.statusBar().showMessage(f"正在尝试使用Audition打开: {os.path.basename(file_path)}", 3000)
                        except Exception as e:
                            # 方法2：如果方法1失败，尝试使用shell方式
                            cmd = f'"{AUDIO_PLAYER_PATH}" "{abs_file_path}"'
                            subprocess.Popen(cmd, shell=True)
                            self.statusBar().showMessage(f"使用shell方式打开Audition: {os.path.basename(file_path)}", 3000)
                    else:
                        # 使用指定的播放器
                        subprocess.Popen([AUDIO_PLAYER_PATH, file_path])
                        self.statusBar().showMessage(f"使用指定播放器打开: {os.path.basename(file_path)}", 3000)
                else:
                    # 使用系统默认关联的播放器
                    if os.name == 'nt':  # Windows
                        os.startfile(file_path)
                    else:  # Linux, macOS
                        # 对于Linux和macOS，使用xdg-open或open命令
                        open_cmd = 'open' if sys.platform == 'darwin' else 'xdg-open'
                        subprocess.Popen([open_cmd, file_path], shell=False)
                    
                    self.statusBar().showMessage(f"使用系统默认播放器打开: {os.path.basename(file_path)}", 3000)
            except Exception as e:
                QMessageBox.warning(self, "错误", f"打开音频文件时出错: {str(e)}")
                # 出错时仍尝试使用内置播放器播放
                if not self.result_audio_player.setAudioFile(file_path):
                    QMessageBox.warning(self, "警告", f"无法使用内置播放器加载音频文件: {os.path.basename(file_path)}")
                else:
                    self.statusBar().showMessage(f"已使用内置播放器加载: {os.path.basename(file_path)}", 3000)
    
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
    
    def parseMultiRoleText(self, text):
        """
        解析多角色推理文本
        
        格式：
        <角色名1>
        角色1的文本内容
        <角色名2>
        角色2的文本内容
        
        Args:
            text (str): 输入的多角色文本
            
        Returns:
            list: 包含(角色名, 文本内容)元组的列表
        """
        return TextProcessor.parse_multi_role_text(text)
    
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
        
        # 解析多角色文本
        role_text_pairs = self.parseMultiRoleText(text)
        
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
        
        # 加载文本替换规则
        replace_rules = self.loadReplacementRules()
        
        # 单角色推理 - 原始流程
        if len(role_text_pairs) == 1 and role_text_pairs[0][0] is None:
            # 获取参考音频路径
            voice_path = self.ref_audio_player.getAudioPath()
            if not voice_path:
                QMessageBox.warning(self, "警告", "请先选择参考音频")
                return
            
            # 禁用所有按钮，除了合成按钮（现在是停止按钮）
            self.disableUIControls(True)
            
            # 将合成按钮变成停止按钮
            self.infer_btn.setText("停止生成")
            self.statusBar().showMessage("正在生成语音...")
            
            # 获取当前说话人名称
            current_index = self.char_combo.currentIndex()
            speaker_name = self.char_combo.itemData(current_index) if current_index > 0 else "未知说话人"
            
            # 创建输出文件名（说话人_文本前50字）
            filename = self.formatFilename(speaker_name, text)
            
            # 创建输出路径
            output_path = os.path.join("outputs", f"{filename}.wav")
            
            # 创建并启动推理线程
            self.inference_thread = QThread()
            self.inference_worker = SingleRoleInferenceWorker(
                self.tts, 
                voice_path, 
                text,
                output_path=output_path,
                punct_chars=punct_chars,
                pause_time=pause_time,
                replace_rules=replace_rules  # 添加替换规则参数
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
            
        # 多角色推理 - 新流程
        else:
            # 创建一个新的多角色推理处理器
            self.handleMultiRoleInference(role_text_pairs, punct_chars, pause_time)
    
    def handleMultiRoleInference(self, role_text_pairs, punct_chars, pause_time):
        """
        处理多角色推理
        
        Args:
            role_text_pairs (list): 包含(角色名, 文本内容)元组的列表
            punct_chars (str): 分割标点符号
            pause_time (float): 停顿时间(秒)
        """
        # 禁用UI控件
        self.disableUIControls(True)
        self.infer_btn.setText("停止生成")
        
        # 检查所有角色是否存在
        missing_roles = []
        for role_name, _ in role_text_pairs:
            if not self.character_manager.character_exists(role_name):
                missing_roles.append(role_name)
        
        # 如果有缺失角色，显示错误并返回
        if missing_roles:
            self.disableUIControls(False)
            self.infer_btn.setText("生成语音")
            missing_roles_str = "、".join(missing_roles)
            QMessageBox.warning(self, "角色不存在", 
                               f"以下角色不存在: {missing_roles_str}\n请先创建这些角色或检查角色名称拼写。")
            return
        
        # 加载文本替换规则
        replace_rules = self.loadReplacementRules()
        
        # 生成输出文件名
        first_role = role_text_pairs[0][0]
        combined_name = f"{first_role}"
        if len(role_text_pairs) > 1:
            combined_name += f"等{len(role_text_pairs)}人对话"
        
        timestamp = time.strftime("%Y%m%d%H%M%S", time.localtime())
        output_filename = f"[多角色][{timestamp}]{combined_name}"
        output_path = os.path.join("outputs", f"{output_filename}.wav")
        
        # 创建并启动多角色推理线程
        self.inference_thread = QThread()
        self.inference_worker = MultiRoleInferenceWorker(
            self.tts,
            self.character_manager,
            role_text_pairs,
            output_path=output_path,
            punct_chars=punct_chars,
            pause_time=pause_time,
            replace_rules=replace_rules  # 添加替换规则参数
        )
        
        # 连接信号
        self.inference_worker.moveToThread(self.inference_thread)
        self.inference_thread.started.connect(self.inference_worker.run)
        
        # 使用相同的信号处理器处理完成和错误信号
        self.inference_worker.finished.connect(self.onInferenceFinished)
        self.inference_worker.progress.connect(self.onInferenceProgress)
        self.inference_worker.error.connect(self.onInferenceError)
        
        # 确保线程正确退出
        self.inference_worker.finished.connect(self.inference_thread.quit)
        self.inference_worker.error.connect(self.inference_thread.quit)
        
        # 启动线程
        self.inference_thread.start()
        self.statusBar().showMessage("正在进行多角色语音生成...")
        print(f"多角色推理线程已启动: {self.inference_thread}")
    
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
        
        # 检查是否为部分结果
        basename = os.path.basename(output_path)
        is_partial = "_部分" in basename or "_最后片段" in basename
        if is_partial:
            self.statusBar().showMessage("用户中断，已保存部分生成结果", 5000)
        else:
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
        
        # 启用所有按钮
        self.disableUIControls(False)
        
        # 如果不是用户主动中断，则显示错误消息
        # 注意：部分结果会通过onInferenceFinished处理，而不会调用此方法
        if error_message != "推理已被用户中断":
            self.statusBar().showMessage("生成失败", 5000)
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
    
    def formatFilename(self, speaker_name, text_content):
        """
        格式化音频文件名，确保不包含非法字符
        
        Args:
            speaker_name (str): 说话人名称
            text_content (str): 文本内容
            
        Returns:
            str: 格式化后的文件名（不包含扩展名）
        """
        # 获取当前时间戳
        timestamp = time.strftime("%Y%m%d%H%M%S", time.localtime())
        
        # 默认说话人名称
        if not speaker_name or speaker_name == "-- 选择角色 --":
            speaker_name = "未知说话人"
        
        # 清理文本内容（去除换行符、空格和文件名非法字符）
        text = text_content.strip()
        # 替换换行符和空格
        text = text.replace("\n", "").replace("\r", "").replace(" ", "").replace("\t", "")
        # 替换Windows文件名中的非法字符（\ / : * ? " < > |）
        invalid_chars = '\\/:"*?<>|'
        for char in invalid_chars:
            text = text.replace(char, "_")
        
        # 限制文本长度（取前50个字符）
        text = text[:50]
        
        # 创建文件名 [时间戳][说话人]文本
        return f"[{speaker_name}][{timestamp}]{text}"
    
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
    
    def loadReplacementRules(self):
        """加载文本替换规则"""
        replace_rules = []
        
        try:
            if os.path.exists(self.replace_config_path):
                with open(self.replace_config_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith('#'):
                            continue
                        parts = line.split('|')
                        if len(parts) == 3:
                            search_str, replace_from, replace_to = parts
                            replace_rules.append((search_str, replace_from, replace_to))
                
                print(f"已加载 {len(replace_rules)} 条文本替换规则")
            else:
                print("替换规则配置文件不存在或为空")
        except Exception as e:
            print(f"加载替换规则出错: {str(e)}")
        
        return replace_rules
    
    def showTextEditContextMenu(self, position):
        """显示文本编辑器的自定义右键菜单"""
        context_menu = self.text_edit.createStandardContextMenu()
        
        # 添加分隔线
        context_menu.addSeparator()
        
        # 创建插入角色子菜单
        characters_menu = QMenu("插入角色", self)
        
        # 获取所有角色
        characters = self.character_manager.get_all_characters()
        
        if characters:
            # 按字母顺序排序角色
            characters.sort()
            
            # 添加角色到子菜单
            for char_name in characters:
                action = QAction(char_name, self)
                # 使用lambda函数时，必须使用name=char_name传递参数，否则所有动作都会使用最后一个char_name值
                action.triggered.connect(lambda checked, name=char_name: self.insertCharacterTag(name))
                characters_menu.addAction(action)
        else:
            # 如果没有角色，则添加禁用的菜单项
            no_chars_action = QAction("无可用角色", self)
            no_chars_action.setEnabled(False)
            characters_menu.addAction(no_chars_action)
        
        # 添加插入角色子菜单到上下文菜单
        context_menu.addMenu(characters_menu)
        
        # 显示上下文菜单
        context_menu.exec(self.text_edit.mapToGlobal(position))
    
    def insertCharacterTag(self, character_name):
        """在文本编辑器中插入角色标签"""
        # 获取当前光标位置
        cursor = self.text_edit.textCursor()
        
        # 获取当前光标所在行的文本
        cursor.select(cursor.SelectionType.LineUnderCursor)
        line_text = cursor.selectedText()
        
        # 确保当前位置处于行首或在一个空行，以便正确插入角色标签
        # 如果当前行不为空且光标不在行首，则先插入一个换行
        if line_text.strip() and not cursor.atBlockStart():
            cursor.clearSelection()
            cursor.insertText("\n")
        
        # 插入角色标签
        cursor.insertText(f"<{character_name}>\n")
        
        # 设置焦点回到文本编辑器
        self.text_edit.setFocus() 