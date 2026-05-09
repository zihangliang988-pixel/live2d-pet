#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
桌宠类 - 桌面宠物 UI
"""

import sys
from PyQt5.QtWidgets import (QApplication, QLabel, QMainWindow, QMessageBox,
                             QMenu, QAction, QDialog, QVBoxLayout, QTextEdit,
                             QPushButton, QLineEdit, QWidget)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QIcon, QPixmap
from file_manager import FileManager
from voice import VoiceProcessor


class PetDialog(QDialog):
    """桌宠对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("桌宠助手 🐾")
        self.setFixedSize(400, 500)
        self.file_manager = FileManager()
        self.voice_processor = VoiceProcessor()
        
        self._setup_ui()
    
    def _setup_ui(self):
        """设置 UI"""
        layout = QVBoxLayout(self)
        
        # 标题
        title = QLabel("🐾 桌宠助手")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("微软雅黑", 16, QFont.Bold))
        layout.addWidget(title)
        
        # 语音按钮
        self.voice_btn = QPushButton("🎤 语音输入")
        self.voice_btn.clicked.connect(self._start_voice_input)
        layout.addWidget(self.voice_btn)
        
        # 文本输入框
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("输入命令，如：打开 游戏")
        self.input_edit.returnPressed.connect(self._execute_command)
        layout.addWidget(self.input_edit)
        
        # 执行按钮
        self.execute_btn = QPushButton("执行")
        self.execute_btn.clicked.connect(self._execute_command)
        layout.addWidget(self.execute_btn)
        
        # 输出区域
        self.output_edit = QTextEdit()
        self.output_edit.setReadOnly(True)
        self.output_edit.setFont(QFont("微软雅黑", 10))
        self.output_edit.append("欢迎使用桌宠助手！🎉")
        self.output_edit.append("")
        self.output_edit.append("可用命令：")
        self.output_edit.append("• 打开 [文件名] - 打开文件或程序")
        self.output_edit.append("• 创建 [文件名] - 创建新文件")
        self.output_edit.append("• 删除 [文件名] - 删除文件")
        self.output_edit.append("• 移动 [文件名] 到 [目录] - 移动文件")
        self.output_edit.append("• 查看 [文件名] - 查看文件信息")
        layout.addWidget(self.output_edit)
    
    def _start_voice_input(self):
        """开始语音输入"""
        self.output_edit.append("\n🎤 正在启动语音识别...")
        
        # 在后台线程中监听
        import threading
        thread = threading.Thread(target=self._voice_thread)
        thread.daemon = True
        thread.start()
    
    def _voice_thread(self):
        """语音识别线程"""
        text = self.voice_processor.listen(timeout=10)
        
        if text:
            self.output_edit.append(f"🗣️ 识别结果：{text}")
            # 自动执行命令
            self._execute_command(text)
        else:
            self.output_edit.append("❌ 语音识别失败，请重试")
    
    def _execute_command(self, text=None):
        """执行命令"""
        if text is None:
            text = self.input_edit.text().strip()
        
        if not text:
            return
        
        self.output_edit.append(f"\n📝 命令：{text}")
        self.input_edit.clear()
        
        # 解析并执行命令
        result = self._parse_and_execute(text)
        
        # 显示结果
        if result["success"]:
            self.output_edit.append(f"✅ {result['message']}")
        else:
            self.output_edit.append(f"❌ {result['message']}")
    
    def _parse_and_execute(self, text: str) -> dict:
        """解析并执行命令"""
        text = text.lower()
        
        # 打开命令
        for keyword in ["打开", "进入", "启动", "运行"]:
            if keyword in text:
                target = text.replace(keyword, "").strip()
                if not target:
                    return {"success": False, "message": "请指定要打开的文件"}
                return self.file_manager.open_file(target)
        
        # 创建命令
        for keyword in ["创建", "新建", "建一个"]:
            if keyword in text:
                target = text.replace(keyword, "").strip()
                if not target:
                    return {"success": False, "message": "请指定要创建的文件名"}
                return self.file_manager.create_file(target)
        
        # 删除命令
        for keyword in ["删除", "删掉", "删了"]:
            if keyword in text:
                target = text.replace(keyword, "").strip()
                if not target:
                    return {"success": False, "message": "请指定要删除的文件"}
                
                # 二次确认
                confirm = QMessageBox.question(
                    self, "确认删除",
                    f"确定要删除 '{target}' 吗？",
                    QMessageBox.Yes | QMessageBox.No
                )
                
                if confirm == QMessageBox.Yes:
                    return self.file_manager.delete_file(target)
                else:
                    return {"success": True, "message": "已取消删除"}
        
        # 移动命令
        for keyword in ["移动", "移到", "放到"]:
            if keyword in text:
                parts = text.split(keyword, 1)
                if len(parts) != 2:
                    return {"success": False, "message": "格式错误：移动 [文件名] 到 [目录]"}
                
                target = parts[1].strip()
                if "到" in target:
                    file_name, dir_path = target.split("到", 1)
                    file_name = file_name.strip()
                    dir_path = dir_path.strip()
                    
                    # 二次确认
                    confirm = QMessageBox.question(
                        self, "确认移动",
                        f"确定要将 '{file_name}' 移动到 '{dir_path}' 吗？",
                        QMessageBox.Yes | QMessageBox.No
                    )
                    
                    if confirm == QMessageBox.Yes:
                        return self.file_manager.move_file(file_name, dir_path)
                    else:
                        return {"success": True, "message": "已取消移动"}
                else:
                    return {"success": False, "message": "格式错误：移动 [文件名] 到 [目录]"}
        
        # 查看命令
        for keyword in ["查看", "看看", "显示"]:
            if keyword in text:
                target = text.replace(keyword, "").strip()
                if not target:
                    return {"success": False, "message": "请指定要查看的文件"}
                return self.file_manager.view_file(target)
        
        return {"success": False, "message": "未知命令，请使用：打开、创建、删除、移动、查看"}


class PetWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self):
        super().__init__()
        self.pet_dialog = None
        self._setup_ui()
    
    def _setup_ui(self):
        """设置 UI"""
        self.setWindowTitle("桌宠 🐾")
        self.setFixedSize(100, 100)
        
        # 创建中央部件
        central = QWidget()
        self.setCentralWidget(central)
        
        # 桌宠图标（可以用图片替换）
        self.pet_label = QLabel("🐾")
        self.pet_label.setAlignment(Qt.AlignCenter)
        self.pet_label.setFont(QFont("Segoe UI Emoji", 48))
        self.pet_label.setStyleSheet("background: transparent; border: none;")
        
        from PyQt5.QtWidgets import QVBoxLayout
        layout = QVBoxLayout(central)
        layout.addWidget(self.pet_label)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 鼠标事件
        self.pet_label.installEventFilter(self)
        
        # 右键菜单
        self._setup_context_menu()
    
    def _setup_context_menu(self):
        """设置右键菜单"""
        menu = QMenu(self)
        
        action_open = QAction("打开助手", self)
        action_open.triggered.connect(self._open_assistant)
        menu.addAction(action_open)
        
        action_voice = QAction("语音测试", self)
        action_voice.triggered.connect(self._test_voice)
        menu.addAction(action_voice)
        
        menu.addSeparator()
        
        action_exit = QAction("退出", self)
        action_exit.triggered.connect(self.close)
        menu.addAction(action_exit)
        
        self.context_menu = menu
    
    def eventFilter(self, obj, event):
        """事件过滤器"""
        from PyQt5.QtCore import QEvent
        
        if obj == self.pet_label:
            if event.type() == QEvent.MouseButtonPress:
                from PyQt5.QtGui import QMouseEvent
                mouse_event = event
                
                if mouse_event.button() == Qt.LeftButton:
                    # 左键双击打开助手
                    if hasattr(self, '_click_count'):
                        self._click_count += 1
                        if self._click_count >= 2:
                            self._open_assistant()
                            self._click_count = 0
                    else:
                        self._click_count = 1
                
                elif mouse_event.button() == Qt.RightButton:
                    # 右键显示菜单
                    self.context_menu.exec_(self.pet_label.mapToGlobal(mouse_event.pos()))
            
            elif event.type() == QEvent.MouseButtonRelease:
                QTimer.singleShot(500, lambda: setattr(self, '_click_count', 0))
        
        return super().eventFilter(obj, event)
    
    def _open_assistant(self):
        """打开助手对话框"""
        if not self.pet_dialog:
            self.pet_dialog = PetDialog(self)
        self.pet_dialog.show()
        self.pet_dialog.raise_()
        self.pet_dialog.activateWindow()
    
    def _test_voice(self):
        """测试语音"""
        voice = VoiceProcessor()
        if voice.test_microphone():
            QMessageBox.information(self, "测试成功", "✅ 麦克风工作正常！")
        else:
            QMessageBox.warning(self, "测试失败", "❌ 麦克风有问题，请检查")


def main():
    """主函数"""
    app = QApplication(sys.argv)
    app.setApplicationName("桌宠助手")
    
    window = PetWindow()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
