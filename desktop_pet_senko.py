#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
桌面宠物 v8.0 - Live2D WebView + AI 对话 + 文件管理
"""

import sys, os, math, random, json, threading, time as time_module

os.chdir(os.path.dirname(os.path.abspath(__file__)))

# 处理 Windows 控制台编码
if sys.stdout and sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    import io
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QMenu, QAction,
    QDialog, QTextEdit, QLineEdit, QPushButton, QFrame, QLabel,
    QSizeGrip,
)
from PyQt5.QtCore import Qt, QTimer, QPoint, QUrl, pyqtSignal, QThread
from PyQt5.QtGui import QFont, QColor, QPainter, QPixmap
from PyQt5.QtWebEngineWidgets import QWebEngineView

from file_manager import FileManager


# ======================================================================
# LLM 对话线程
# ======================================================================
class LLMChatThread(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, messages, model="llama3.2:3b"):
        super().__init__()
        self.messages = messages
        self.model = model

    def run(self):
        try:
            import ollama
            response = ollama.chat(
                model=self.model,
                messages=self.messages,
                stream=False,
                options={"temperature": 0.7, "num_predict": 512}
            )
            self.finished.emit(response['message']['content'])
        except Exception as e:
            self.error.emit(str(e))


# ======================================================================
# 命令执行线程
# ======================================================================
class CommandThread(QThread):
    finished = pyqtSignal(dict)

    def __init__(self, command_text, llm_parser):
        super().__init__()
        self.command_text = command_text
        self.llm_parser = llm_parser

    def run(self):
        result = self.llm_parser.parse_command(self.command_text)
        self.finished.emit(result)


# ======================================================================
# Live2D 桌宠主窗口
# ======================================================================
class Live2DPet(QWidget):
    def __init__(self):
        super().__init__()
        self.file_manager = FileManager()
        self.is_dragging = False
        self.drag_start_pos = QPoint()
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.PointingHandCursor)
        # 可缩放窗口
        self.setMinimumSize(150, 200)
        self.resize(220, 340)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Live2D WebView - online viewer + Senko CDN
        self.webview = QWebEngineView()
        self.webview.setMinimumSize(150, 160)
        self.webview.setStyleSheet("background: transparent; border: none;")
        self.webview.page().setBackgroundColor(QColor(0, 0, 0, 0))
        self.webview.setContextMenuPolicy(Qt.PreventContextMenu)

        model_url = "https://cdn.jsdelivr.net/gh/Eikanya/Live2d-model/Live2D/Senko_Normals/senko.model3.json"
        viewer_url = f"https://guansss.github.io/live2d-viewer-web/#/model?url={model_url}"
        self.webview.setUrl(QUrl(viewer_url))
        self.webview.loadFinished.connect(lambda ok: self._on_load(ok))

        layout.addWidget(self.webview, stretch=1)

        # 名称标签
        name_label = QLabel("Senko")
        name_label.setAlignment(Qt.AlignCenter)
        name_label.setFont(QFont("Microsoft YaHei UI", 10, QFont.Bold))
        name_label.setStyleSheet("""
            background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                stop:0 rgba(13,17,23,200), stop:1 rgba(20,15,35,200));
            border-radius: 10px;
            padding: 2px 12px;
            color: #c493fd;
            margin: 0 60px;
        """)
        layout.addWidget(name_label)

        # 缩放手柄
        self.grip = QSizeGrip(self)
        self.grip.setStyleSheet("background: transparent; width: 12px; height: 12px;")
        self.grip.resize(12, 12)
        # 把 grip 放到右下角
        self.grip.raise_()

    def resizeEvent(self, event):
        """Keep grip at bottom-right when window resizes."""
        super().resizeEvent(event)
        if hasattr(self, 'grip'):
            g = self.grip
            g.move(self.width() - g.width(), self.height() - g.height())

    def _on_load(self, ok):
        """Page loaded, inject JS to auto-load model."""
        if not ok:
            print("[Senko] Page load failed!")
            return
        QTimer.singleShot(3000, self._inject_js)
        QTimer.singleShot(8000, self._inject_js)
        QTimer.singleShot(15000, self._inject_js)

    def _inject_js(self):
        """Hide UI after model loads."""
        js = """(function(){
  // Hide UI but keep canvas + model
  var app = document.getElementById('app');
  if(app) app.style.setProperty('display','none','important');
  document.body.style.setProperty('background','transparent','important');
  // Make all canvases visible
  document.querySelectorAll('canvas').forEach(function(c){
    c.style.setProperty('display','block','important');
    c.style.setProperty('visibility','visible','important');
  });
  document.querySelectorAll('.v-application').forEach(function(e){
    e.style.setProperty('background','transparent','important');
  });
  // Hide toolbar too if model is loaded
  var toolbar = document.querySelector('.v-toolbar');
  if(toolbar) toolbar.style.setProperty('display','none','important');
  console.log('[Senko] UI hidden');
})();"""
        self.webview.page().runJavaScript(js)
        print("[Senko] JS injected")

    def closeEvent(self, event):
        super().closeEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_dragging = True
            self.drag_start_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
        elif event.button() == Qt.RightButton:
            self._show_context_menu(event.globalPos())
            event.accept()

    def mouseMoveEvent(self, event):
        if self.is_dragging:
            self.move(event.globalPos() - self.drag_start_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_dragging = False
            if hasattr(self, '_last_click_time'):
                now = time_module.time()
                if now - self._last_click_time < 0.4:
                    self._open_chat()
            self._last_click_time = time_module.time()
            event.accept()

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: rgba(15,15,30,240);
                border: 1px solid rgba(150,120,220,0.4);
                border-radius: 10px;
                padding: 6px 4px;
            }
            QMenu::item {
                background: transparent;
                padding: 10px 24px;
                border-radius: 6px;
                color: #d0c8e8;
                font-size: 13px;
            }
            QMenu::item:selected {
                background: rgba(150,120,220,0.25);
                color: #fff;
            }
            QMenu::separator {
                height: 1px;
                background: rgba(150,120,220,0.15);
                margin: 4px 16px;
            }
        """)

        actions = []
        for text, callback in [
            ("💬 开始聊天", self._open_chat),
            ("🎤 语音识别", self._start_voice),
            None,
            ("📋 可用功能", self._show_functions),
            None,
            ("👋 关闭", self._confirm_exit),
        ]:
            if text is None:
                menu.addSeparator()
            else:
                a = QAction(text, self)
                a.triggered.connect(callback)
                menu.addAction(a)
                actions.append(a)

        menu.exec_(pos)

    def _open_chat(self):
        dialog = ChatDialog(self)
        dialog.exec_()

    def _start_voice(self):
        try:
            from voice import VoiceProcessor
            voice = VoiceProcessor()

            def do_voice():
                text = voice.listen(timeout=8)
                if text:
                    dialog = ChatDialog(self, initial_text=text)
                    dialog.exec_()
                else:
                    from PyQt5.QtWidgets import QMessageBox
                    QMessageBox.information(self, "语音识别", "没听清，请重试或使用文字输入")

            t = threading.Thread(target=do_voice, daemon=True)
            t.start()
        except Exception as e:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self, "语音错误", f"语音识别不可用：{e}")

    def _show_functions(self):
        dialog = FunctionListDialog(self)
        dialog.exec_()

    def _confirm_exit(self):
        from PyQt5.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self, "关闭", "😢 要关掉我吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.close()


# ======================================================================
# 聊天对话框
# ======================================================================
class ChatDialog(QDialog):
    def __init__(self, parent=None, initial_text=None):
        super().__init__(parent)
        self.setWindowTitle("💬 Alice 聊天")
        self.setFixedSize(440, 580)
        self.setStyleSheet("""
            QDialog {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 #0d0d1e, stop:1 #181830);
                border: 1px solid rgba(150,120,220,0.3);
                border-radius: 12px;
            }
        """)

        self.file_manager = FileManager()
        self.llm_parser = None
        self._init_llm()

        self.conversation = [{"role": "system",
            "content": "你是桌宠助手 Alice，一个可爱亲切的虚拟角色。你可以帮用户管理文件（打开、创建、删除、移动），也可以日常聊天。用可爱活泼的语气，适当用表情符号，回复尽量简短（不超过100字）。如果用户请求的操作你做不到，友好地解释。回复请使用中文。"}]

        self._setup_ui()

        if initial_text:
            self.input_edit.setText(initial_text)
            self._send_message()

    def _init_llm(self):
        try:
            from llm_parser import LLMCommandParser
            self.llm_parser = LLMCommandParser(model_name="llama3.2:3b")
        except Exception as e:
            print(f"LLM init: {e}")

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # 标题
        header = QLabel("💬 与 Alice 聊天")
        header.setFont(QFont("Microsoft YaHei UI", 14, QFont.Bold))
        header.setStyleSheet("color: #c8b8f0; padding: 4px 0;")
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)

        # 聊天记录
        self.chat_edit = QTextEdit()
        self.chat_edit.setReadOnly(True)
        self.chat_edit.setFont(QFont("Microsoft YaHei UI", 11))
        self.chat_edit.setStyleSheet("""
            QTextEdit {
                background: transparent;
                border: none;
                color: #d0d0e0;
                padding: 6px;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 6px;
            }
            QScrollBar::handle:vertical {
                background: rgba(150,120,220,0.3);
                border-radius: 3px;
                min-height: 30px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
        """)
        self._add_msg("assistant", "你好呀！我是 Alice ✨\n\n可以直接跟我聊天，或者试试：\n• \"打开 记事本\"\n• \"打开 计算器\"\n• \"创建 test.txt\"\n• \"删除 file.txt\"\n• \"移动 a.txt 到 D:/\"")
        layout.addWidget(self.chat_edit, stretch=1)

        # 输入区域
        input_frame = QFrame()
        input_frame.setStyleSheet("""
            QFrame {
                background: rgba(20,20,40,0.8);
                border-radius: 12px;
                border: 1px solid rgba(150,120,220,0.12);
            }
        """)
        input_layout = QVBoxLayout(input_frame)
        input_layout.setContentsMargins(10, 8, 10, 8)
        input_layout.setSpacing(6)

        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("输入消息... 试试：打开 记事本")
        self.input_edit.setFont(QFont("Microsoft YaHei UI", 12))
        self.input_edit.setStyleSheet("""
            QLineEdit {
                background: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 10px;
                padding: 10px 14px;
                color: #d0d0e0;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid rgba(150,120,220,0.5);
            }
        """)
        self.input_edit.returnPressed.connect(self._send_message)
        input_layout.addWidget(self.input_edit)

        # 按钮行
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.voice_btn = QPushButton("🎤 语音")
        self.voice_btn.setFixedHeight(36)
        self.voice_btn.setCursor(Qt.PointingHandCursor)
        self.voice_btn.setStyleSheet("""
            QPushButton {
                background: rgba(100,200,150,0.12);
                color: #66d9a0;
                border: 1px solid rgba(100,200,150,0.25);
                border-radius: 8px;
                padding: 6px 14px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover { background: rgba(100,200,150,0.2); }
        """)
        self.voice_btn.clicked.connect(self._voice_input)
        btn_layout.addWidget(self.voice_btn)

        btn_layout.addStretch()

        self.send_btn = QPushButton("发送")
        self.send_btn.setFixedHeight(36)
        self.send_btn.setCursor(Qt.PointingHandCursor)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 rgba(150,120,220,0.5), stop:1 rgba(120,90,200,0.4));
                color: #e8e0ff;
                border: none;
                border-radius: 8px;
                padding: 6px 24px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 rgba(160,130,230,0.6), stop:1 rgba(130,100,210,0.5));
            }
        """)
        self.send_btn.clicked.connect(self._send_message)
        btn_layout.addWidget(self.send_btn)

        input_layout.addLayout(btn_layout)
        layout.addWidget(input_frame)

    def _add_msg(self, sender, text):
        if sender == "user":
            prefix = "<span style='color: #8090e0; font-weight: bold;'>🧑 你</span>"
            bg = "rgba(60,50,100,0.6)"
            align = "right"
        else:
            prefix = "<span style='color: #c8a0f0; font-weight: bold;'>🌸 Alice</span>"
            bg = "rgba(35,35,65,0.6)"
            align = "left"

        html = f"""
        <div style="text-align:{align}; margin:6px 0;">
            <div style="display:inline-block; background:{bg};
                border-radius:12px; padding:8px 14px; max-width:85%;
                text-align:left;">
                <div style="margin-bottom:2px;">{prefix}</div>
                <div>{text.replace(chr(10), '<br>')}</div>
            </div>
        </div>
        """
        self.chat_edit.append(html)
        sb = self.chat_edit.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _send_message(self, text=None):
        if text is None:
            text = self.input_edit.text().strip()
        if not text:
            return

        self._add_msg("user", text)
        self.input_edit.clear()
        self.send_btn.setEnabled(False)
        self.send_btn.setText("⏳")

        self._process_input(text)

    def _process_input(self, text):
        def on_command(result):
            if result.get("success") and result.get("action") != "unknown":
                self._execute_command(result)
            else:
                self._chat_with_llm(text)

        if self.llm_parser:
            self.cmd_thread = CommandThread(text, self.llm_parser)
            self.cmd_thread.finished.connect(on_command)
            self.cmd_thread.start()
        else:
            self._chat_with_llm(text)

    def _execute_command(self, result):
        action = result["action"]
        target = result.get("target", "")
        dest = result.get("destination", "")
        directory = result.get("directory", "")

        try:
            if action == "open":
                r = self.file_manager.open_file(target)
            elif action == "create":
                r = self.file_manager.create_file(target, directory=directory or None)
            elif action == "delete":
                r = self.file_manager.delete_file(target)
            elif action == "move" and dest:
                r = self.file_manager.move_file(target, dest)
            elif action == "view":
                r = self.file_manager.view_file(target)
            else:
                r = {"success": False, "message": "我不知道这个命令"}
        except Exception as e:
            r = {"success": False, "message": f"执行出错：{str(e)[:50]}"}

        if r["success"]:
            self._add_msg("assistant", f"✅ {r['message']}")
        else:
            self._add_msg("assistant", f"😅 {r['message']}\n\n试试以下命令：\n• 打开 记事本\n• 创建 test.txt\n• 删除 file.txt\n• 移动 a.txt 到 D:/")

        self.send_btn.setEnabled(True)
        self.send_btn.setText("发送")

    def _chat_with_llm(self, text):
        self.conversation.append({"role": "user", "content": text})

        def on_response(response):
            # 清理多余的 JSON
            cleaned = response.strip()
            if cleaned.startswith("{") and cleaned.endswith("}"):
                try:
                    d = json.loads(cleaned)
                    cleaned = d.get("message", cleaned)
                except:
                    pass
            self._add_msg("assistant", cleaned)
            self.conversation.append({"role": "assistant", "content": cleaned})
            self.send_btn.setEnabled(True)
            self.send_btn.setText("发送")

        def on_error(err):
            self._add_msg("assistant", "😅 AI 暂时没响应... 不过你可以直接用命令哦：\n• 打开 记事本\n• 创建 test.txt\n• 删除 file.txt\n• 移动 a.txt 到 D:/")
            self.send_btn.setEnabled(True)
            self.send_btn.setText("发送")

        try:
            import ollama
            recent = self.conversation[-10:]
            self.llm_thread = LLMChatThread(recent)
            self.llm_thread.finished.connect(on_response)
            self.llm_thread.error.connect(on_error)
            self.llm_thread.start()
        except ImportError:
            on_error("ollama 未安装")

    def _voice_input(self):
        self.voice_btn.setEnabled(False)
        self.voice_btn.setText("🎤 听ing...")

        try:
            from voice import VoiceProcessor
            voice = VoiceProcessor()

            def do_voice():
                text = voice.listen(timeout=8)
                if text:
                    QTimer.singleShot(0, lambda: self._on_voice_result(text))
                else:
                    QTimer.singleShot(0, lambda: self._on_voice_result(None))

            t = threading.Thread(target=do_voice, daemon=True)
            t.start()
        except Exception as e:
            self._on_voice_result(None)

    def _on_voice_result(self, text):
        self.voice_btn.setEnabled(True)
        self.voice_btn.setText("🎤 语音")
        if text:
            self.input_edit.setText(text)
            self._send_message()


# ======================================================================
# 功能列表对话框
# ======================================================================
class FunctionListDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📋 功能列表")
        self.setFixedSize(420, 400)
        self.setStyleSheet("""
            QDialog {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 #0d0d1e, stop:1 #181830);
                border: 1px solid rgba(150,120,220,0.3);
                border-radius: 12px;
            }
        """)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel("🌸 Alice 可以帮你做的事")
        title.setFont(QFont("Microsoft YaHei UI", 15, QFont.Bold))
        title.setStyleSheet("color: #c8b8f0;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        items = [
            ("💬 日常聊天", "和 Alice 闲聊、问好，她会亲切回应"),
            ("📁 打开程序/文件", "说「打开 记事本」或「打开 计算器」「打开 画图」"),
            ("📄 创建文件", "说「创建 test.txt」可在默认目录创建文件"),
            ("🗑️ 删除文件", "说「删除 file.txt」能把文件移到回收站"),
            ("📦 移动文件", "说「移动 a.txt 到 D:/backup」移动文件"),
            ("👀 查看文件", "说「查看 图片.png」看文件信息"),
            ("🎤 语音输入", "点击语音按钮，说话就能下命令"),
        ]

        for name, desc in items:
            card = QFrame()
            card.setStyleSheet("""
                QFrame {
                    background: rgba(25,25,45,0.6);
                    border-radius: 8px;
                    border: 1px solid rgba(150,120,220,0.08);
                }
            """)
            cl = QHBoxLayout(card)
            cl.setContentsMargins(12, 8, 12, 8)

            n = QLabel(name)
            n.setFont(QFont("Microsoft YaHei UI", 11, QFont.Bold))
            n.setStyleSheet("color: #8898f0; background: transparent; min-width: 80px;")

            d = QLabel(desc)
            d.setFont(QFont("Microsoft YaHei UI", 9))
            d.setStyleSheet("color: #9890b0; background: transparent;")
            d.setWordWrap(True)

            cl.addWidget(n)
            cl.addWidget(d, stretch=1)
            layout.addWidget(card)

        layout.addStretch()

        btn = QPushButton("知道了 ✨")
        btn.setFixedHeight(38)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet("""
            QPushButton {
                background: rgba(120,100,200,0.3);
                color: #d0c8f0;
                border: 1px solid rgba(150,120,220,0.2);
                border-radius: 8px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover { background: rgba(130,110,210,0.4); }
        """)
        btn.clicked.connect(self.close)
        layout.addWidget(btn)


# ======================================================================
# 桌宠管理器
# ======================================================================
class DesktopPet:
    def __init__(self):
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("AlicePet")

        # Set QtWebEngine cache to ASCII path (fixes Chinese path crashes)
        qwc_dir = os.path.join(os.environ.get('TEMP', 'C:\\temp'), 'SenkoPet_Cache')
        os.makedirs(qwc_dir, exist_ok=True)
        from PyQt5.QtWebEngineWidgets import QWebEngineProfile
        try:
            profile = QWebEngineProfile.defaultProfile()
            profile.setCachePath(qwc_dir)
            profile.setPersistentStoragePath(qwc_dir)
        except Exception:
            pass

        self.pet = Live2DPet()
        screen = self.app.primaryScreen()
        if screen:
            rect = screen.availableGeometry()
            self.pet.move(rect.right() - self.pet.width() - 20, rect.top() + 40)
        else:
            self.pet.move(100, 100)

    def run(self):
        self.pet.show()
        return self.app.exec_()


# ======================================================================
# 入口
# ======================================================================
def main():
    print("=" * 50)
    print("[Alice] 桌宠助手 v8.0")
    print("=" * 50)
    print()
    print("正在启动...")

    try:
        pet = DesktopPet()
        sys.exit(pet.run())
    except KeyboardInterrupt:
        print("\n桌宠已退出")
    except Exception as e:
        print(f"\n错误：{e}")
        import traceback
        traceback.print_exc()
        input("\n按回车键退出...")


if __name__ == "__main__":
    main()
