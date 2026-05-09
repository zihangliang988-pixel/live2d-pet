#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
桌宠 v9 - 仙狐主题 · 明亮丝滑
右键菜单：开始聊天 / 功能概览 / 关闭
"""

import sys, os, json, threading, time as time_module

os.chdir(os.path.dirname(os.path.abspath(__file__)))

# 修正编码
if sys.stdout and sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    import io
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QMenu, QAction,
    QDialog, QTextEdit, QLineEdit, QPushButton, QFrame, QLabel,
    QSizeGrip, QStackedWidget
)
from PyQt5.QtCore import Qt, QTimer, QPoint, QUrl, pyqtSignal, QThread
from PyQt5.QtGui import QFont, QColor, QPixmap, QIcon
from PyQt5.QtWebEngineWidgets import QWebEngineView

from file_manager import FileManager

# ======================================================================
# 配色 · 暖阳橙（仙狐主题）
# ======================================================================
FOX_ORANGE = "#FF8C42"
FOX_PEACH = "#FFB07C"
FOX_LIGHT = "#FFECD2"
FOX_BG1 = "#FFF5E6"
FOX_BG2 = "#FFE4C4"
FOX_WHITE = "#FFFAF0"
FOX_DARK = "#D2691E"
FOX_ACCENT = "#FFA07A"
FOX_TEXT = "#5C3A1E"
FOX_SUBTEXT = "#8B6B4A"
FOX_CHAT_BG = "rgba(255,248,240,0.95)"
FOX_BUBBLE_USER = "rgba(255,200,150,0.7)"
FOX_BUBBLE_AI = "rgba(255,240,220,0.8)"
FOX_INPUT_BG = "rgba(255,248,240,0.9)"
FOX_BTN = "#FF8C42"
FOX_BTN_HOVER = "#FF7A2E"
FOX_BORDER = "#E8C4A0"

# ======================================================================
# LLM 对话线程
# ======================================================================
class LLMChatThread(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, messages, model="qwen2.5:7b"):
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
# 带工具调用的 LLM 对话线程
# ======================================================================
class ToolChatThread(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, messages, tools, model="qwen2.5:7b"):
        super().__init__()
        self.messages = messages
        self.tools = tools
        self.model = model

    def run(self):
        try:
            import ollama
            from tools import execute_tool_call

            # 第一轮：带工具调用
            response = ollama.chat(
                model=self.model,
                messages=self.messages,
                tools=self.tools,
                stream=False,
                options={"temperature": 0.7, "num_predict": 512}
            )

            msg = response['message']

            # 如果有工具调用，执行并返回结果
            if msg.get('tool_calls'):
                for tc in msg['tool_calls']:
                    result = execute_tool_call(tc)
                    self.messages.append({"role": "tool", "content": result})

                # 第二轮：拿最终回复
                response2 = ollama.chat(
                    model=self.model,
                    messages=self.messages,
                    stream=False,
                    options={"temperature": 0.7, "num_predict": 512}
                )
                self.finished.emit(response2['message']['content'])
            else:
                self.finished.emit(msg['content'])

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
# 桌宠主窗口
# ======================================================================
class FoxPet(QWidget):
    def __init__(self):
        super().__init__()
        self.file_manager = FileManager()
        self.is_dragging = False
        self.drag_start_pos = QPoint()
        self._last_click_time = 0
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumSize(150, 200)
        self.resize(240, 360)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Live2D WebView
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

        # 名称标签（仙狐风格）
        name_label = QLabel("🦊 仙狐")
        name_label.setAlignment(Qt.AlignCenter)
        name_label.setFont(QFont("Microsoft YaHei UI", 11, QFont.Bold))
        name_label.setStyleSheet(f"""
            background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                stop:0 rgba(255,140,66,200), stop:1 rgba(255,160,124,200));
            border-radius: 12px;
            padding: 3px 16px;
            color: white;
            margin: 0 50px;
        """)
        layout.addWidget(name_label)

        # 缩放手柄
        self.grip = QSizeGrip(self)
        self.grip.setStyleSheet("background: transparent; width: 14px; height: 14px;")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'grip'):
            g = self.grip
            g.move(self.width() - g.width(), self.height() - g.height())

    def _on_load(self, ok):
        if not ok:
            print("[仙狐] 页面加载失败")
            return
        QTimer.singleShot(3000, self._inject_js)
        QTimer.singleShot(8000, self._inject_js)
        QTimer.singleShot(15000, self._inject_js)

    def _inject_js(self):
        js = """(function(){
  if(window.App && window.App.addModel && !window.App.models.length) {
    try {
      var url = 'https://cdn.jsdelivr.net/gh/Eikanya/Live2d-model/Live2D/Senko_Normals/senko.model3.json';
      window.App.addModel(url);
    } catch(e) {}
  }
  var app = document.getElementById('app');
  if(app) app.style.setProperty('display','none','important');
  document.body.style.setProperty('background','transparent','important');
  document.querySelectorAll('canvas').forEach(function(c){
    c.style.setProperty('display','block','important');
    c.style.setProperty('visibility','visible','important');
  });
  document.querySelectorAll('.v-application').forEach(function(e){
    e.style.setProperty('background','transparent','important');
  });
  var toolbar = document.querySelector('.v-toolbar');
  if(toolbar) toolbar.style.setProperty('display','none','important');
})();"""
        self.webview.page().runJavaScript(js)

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

    # ---- 右键菜单（3项） ----
    def _show_context_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: rgba(255,248,240,245);
                border: 1px solid {FOX_BORDER};
                border-radius: 10px;
                padding: 6px 4px;
            }}
            QMenu::item {{
                background: transparent;
                padding: 10px 24px;
                border-radius: 6px;
                color: {FOX_TEXT};
                font-size: 13px;
            }}
            QMenu::item:selected {{
                background: rgba(255,140,66,0.15);
                color: {FOX_ORANGE};
            }}
            QMenu::separator {{
                height: 1px;
                background: {FOX_BORDER};
                margin: 4px 16px;
            }}
        """)

        for item in [
            ("💬 开始聊天", self._open_chat),
            ("📋 功能概览", self._show_functions),
            None,
            ("👋 关闭", self._confirm_exit),
        ]:
            if item is None:
                menu.addSeparator()
            else:
                text, callback = item
                a = QAction(text, self)
                a.triggered.connect(callback)
                menu.addAction(a)

        menu.exec_(pos)

    def _open_chat(self):
        dlg = FoxChatDialog(self)
        dlg.exec_()

    def _show_functions(self):
        dlg = FeatureOverview(self)
        dlg.exec_()

    def _confirm_exit(self):
        from PyQt5.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self, "🦊 仙狐", "真的要走吗… 我会想你的 😢",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.close()


# ======================================================================
# 聊天对话框 · 仙狐主题（明亮丝滑）
# ======================================================================
class FoxChatDialog(QDialog):
    def __init__(self, parent=None, initial_text=None):
        super().__init__(parent)
        self.setWindowTitle("💬 仙狐聊天")
        self.setFixedSize(480, 620)
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        # 拖拽状态
        self._drag_pos = QPoint()
        self._dragging = False

        # 主背景
        self.setStyleSheet(f"""
            FoxChatDialog {{
                background: transparent;
            }}
        """)

        self.file_manager = FileManager()
        self.llm_parser = None
        self._init_llm()

        # 语音模式：False=文字输入, True=长按T说话
        self.voice_mode = False
        self._voice_pressed = False

        # 加载性格配置
        self.character = self._load_character()
        system_prompt = self._build_system_prompt()
        self.conversation = [{"role": "system", "content": system_prompt}]

        self._setup_ui()

        if initial_text:
            self.input_edit.setText(initial_text)
            self._send_message()

    def _init_llm(self):
        try:
            from llm_parser import LLMCommandParser
            self.llm_parser = LLMCommandParser(model_name="qwen2.5:7b")
        except Exception as e:
            print(f"LLM init: {e}")

    def _load_character(self):
        """加载性格配置"""
        default = {
            "name": "仙狐",
            "emoji": "🦊",
            "title": "小狐仙",
            "称呼用户": "主人",
            "性格": {"类型": "温柔元气", "描述": "像小狐狸一样温柔可爱"},
            "语气风格": {"语调": "活泼可爱", "表情符号": True},
            "知识设定": {"身份": "住在电脑里的小狐狸精"}
        }
        try:
            char = json.load(open('character.json', 'r', encoding='utf-8'))
            print("[仙狐] 加载性格配置 ✓")
            return char
        except Exception as e:
            print(f"[仙狐] 使用默认性格配置: {e}")
            return default

    def _build_system_prompt(self):
        """基于性格配置构建系统提示词"""
        c = self.character
        name = c.get('name', '仙狐')
        emoji = c.get('emoji', '🦊')
        title = c.get('title', '小狐仙')
        call_user = c.get('称呼用户', '主人')
        personality = c.get('性格', {}).get('描述', '温柔可爱')
        tone = c.get('语气风格', {}).get('语调', '活泼可爱')
        use_emoji = c.get('语气风格', {}).get('表情符号', True)
        identity = c.get('知识设定', {}).get('身份', '桌宠助手')
        rules = c.get('行为规则', [])
        emoji_rule = "适当使用表情符号" if use_emoji else "不要使用表情符号"

        prompt = f"""你是{name}，一个{identity}。你的称号是{title}。

## 性格
{personality}

## 语气
整体{tone}。称呼用户为「{call_user}」。{emoji_rule}。
回复使用中文，尽量简短（不超过100字）。

## 行为规则
"""
        for r in rules:
            prompt += f"- {r}\n"

        prompt += f"""
## 能力说明
你可以使用的工具：天气查询、系统状态查询、IP查询、每日一言、今日运势、生成密码。
当用户问「天气」「IP」「运势」「系统」「一言」等关键词时，主动调用对应工具。
你也可以普通聊天、帮用户管理文件。

现在，以{name}的身份和{call_user}对话吧！{emoji}"""
        return prompt

    def _setup_ui(self):
        # 外层容器（圆角 + 暖色渐变背景）
        self.outer_frame = QFrame(self)
        self.outer_frame.setGeometry(0, 0, 480, 620)
        outer.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 {FOX_LIGHT}, stop:0.5 {FOX_BG1}, stop:1 {FOX_BG2});
                border-radius: 16px;
                border: 1px solid {FOX_BORDER};
            }}
        """)

        layout = QVBoxLayout(self.outer_frame)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # ---- 标题栏 ----
        header_frame = QFrame()
        header_frame.setStyleSheet("background: transparent;")
        hdr_layout = QHBoxLayout(header_frame)
        hdr_layout.setContentsMargins(0, 0, 0, 0)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,180,120,0.3);
                color: {FOX_TEXT};
                border: none;
                border-radius: 14px;
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background: rgba(255,100,80,0.4); color: #d44; }}
        """)
        close_btn.clicked.connect(self.close)
        hdr_layout.addWidget(close_btn)

        hdr_layout.addStretch()

        title = QLabel("🦊 和仙狐聊天")
        title.setFont(QFont("Microsoft YaHei UI", 15, QFont.Bold))
        title.setStyleSheet(f"color: {FOX_ORANGE}; background: transparent;")
        hdr_layout.addWidget(title)

        hdr_layout.addStretch()

        layout.addWidget(header_frame)

        # ---- 聊天记录 ----
        self.chat_edit = QTextEdit()
        self.chat_edit.setReadOnly(True)
        self.chat_edit.setFont(QFont("Microsoft YaHei UI", 11))
        self.chat_edit.setFrameShape(QFrame.NoFrame)
        self.chat_edit.setStyleSheet(f"""
            QTextEdit {{
                background: {FOX_CHAT_BG};
                border: none;
                border-radius: 12px;
                color: {FOX_TEXT};
                padding: 10px;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 6px;
            }}
            QScrollBar::handle:vertical {{
                background: rgba(255,140,66,0.3);
                border-radius: 3px;
                min-height: 30px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
        """)
        self._add_msg("assistant",
            "你好呀！我是小狐仙 🦊✨\n\n有什么可以帮你的？试试：\n"
            "• 打开 记事本\n• 打开 计算器\n• 创建 test.txt\n• 随便聊聊天~")
        layout.addWidget(self.chat_edit, stretch=1)

        # ---- 输入区域 ----
        input_frame = QFrame()
        input_frame.setStyleSheet(f"""
            QFrame {{
                background: {FOX_INPUT_BG};
                border-radius: 14px;
                border: 1px solid {FOX_BORDER};
            }}
        """)
        input_layout = QHBoxLayout(input_frame)
        input_layout.setContentsMargins(6, 6, 6, 6)
        input_layout.setSpacing(6)

        # 语音切换按钮（在输入框左边）
        self.mode_btn = QPushButton("🎤")
        self.mode_btn.setFixedSize(38, 38)
        self.mode_btn.setCursor(Qt.PointingHandCursor)
        self.mode_btn.setToolTip("切换语音/文字输入")
        self._update_mode_btn_style()
        self.mode_btn.clicked.connect(self._toggle_voice_mode)
        input_layout.addWidget(self.mode_btn)

        # 语音提示标签（仅语音模式显示）
        self.voice_hint = QLabel("长按 T 说话")
        self.voice_hint.setFont(QFont("Microsoft YaHei UI", 10))
        self.voice_hint.setStyleSheet(f"color: {FOX_ORANGE}; font-weight: bold; background: transparent;")
        self.voice_hint.setAlignment(Qt.AlignCenter)
        self.voice_hint.setFixedWidth(100)
        self.voice_hint.setVisible(False)
        input_layout.addWidget(self.voice_hint)

        # 文字输入框
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("输入消息…")
        self.input_edit.setFont(QFont("Microsoft YaHei UI", 12))
        self.input_edit.setStyleSheet(f"""
            QLineEdit {{
                background: rgba(255,255,255,0.6);
                border: 1px solid {FOX_BORDER};
                border-radius: 10px;
                padding: 10px 14px;
                color: {FOX_TEXT};
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border: 1px solid {FOX_ORANGE};
            }}
        """)
        self.input_edit.returnPressed.connect(self._send_message)
        input_layout.addWidget(self.input_edit, stretch=1)

        # 发送按钮
        self.send_btn = QPushButton("发送")
        self.send_btn.setFixedHeight(38)
        self.send_btn.setMinimumWidth(60)
        self.send_btn.setCursor(Qt.PointingHandCursor)
        self.send_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {FOX_ORANGE}, stop:1 {FOX_PEACH});
                color: white;
                border: none;
                border-radius: 10px;
                padding: 6px 20px;
                font-weight: bold;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {FOX_BTN_HOVER}, stop:1 {FOX_ACCENT});
            }}
            QPushButton:disabled {{
                background: rgba(200,180,160,0.5);
                color: rgba(255,255,255,0.6);
            }}
        """)
        self.send_btn.clicked.connect(self._send_message)
        input_layout.addWidget(self.send_btn)

        layout.addWidget(input_frame)

        # 启动键盘监听（语音模式用 T 键）
        self._start_key_listener()

    def _update_mode_btn_style(self):
        if self.voice_mode:
            self.mode_btn.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(255,140,66,0.2);
                    color: {FOX_ORANGE};
                    border: 2px solid {FOX_ORANGE};
                    border-radius: 19px;
                    font-size: 16px;
                }}
                QPushButton:hover {{
                    background: rgba(255,140,66,0.35);
                }}
            """)
        else:
            self.mode_btn.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(255,200,180,0.25);
                    color: {FOX_DARK};
                    border: 1px solid {FOX_BORDER};
                    border-radius: 19px;
                    font-size: 14px;
                }}
                QPushButton:hover {{
                    background: rgba(255,180,120,0.3);
                }}
            """)

    def _toggle_voice_mode(self):
        self.voice_mode = not self.voice_mode
        self.voice_hint.setVisible(self.voice_mode)
        self.input_edit.setVisible(not self.voice_mode)
        self.send_btn.setVisible(not self.voice_mode)
        self._update_mode_btn_style()

        if self.voice_mode:
            self.voice_hint.setText("🎤 长按 T 说话")
            self.mode_btn.setText("⌨️")
            self.mode_btn.setToolTip("切换到文字输入")
        else:
            self.mode_btn.setText("🎤")
            self.mode_btn.setToolTip("切换到语音输入")

    def _start_key_listener(self):
        """全局键盘监听（T键用于语音）"""
        self._key_thread_running = True

        def listen_keys():
            try:
                import keyboard as kb
                while self._key_thread_running:
                    if self.voice_mode:
                        try:
                            if kb.is_pressed('t') and not self._voice_pressed:
                                self._voice_pressed = True
                                QTimer.singleShot(0, self._start_voice_capture)
                            elif not kb.is_pressed('t') and self._voice_pressed:
                                self._voice_pressed = False
                                QTimer.singleShot(0, self._stop_voice_capture)
                        except:
                            pass
                    time_module.sleep(0.05)
            except ImportError:
                pass
            except Exception:
                pass

        t = threading.Thread(target=listen_keys, daemon=True)
        t.start()

    def _start_voice_capture(self):
        """开始语音捕获"""
        self.voice_hint.setText("🎤 正在听…")
        self.voice_hint.setStyleSheet(f"color: #e74c3c; font-weight: bold; background: transparent;")
        self._voice_recognizing = True

        def do_voice():
            try:
                from voice import VoiceProcessor
                voice = VoiceProcessor()
                text = voice.listen(timeout=5)
                QTimer.singleShot(0, lambda: self._on_voice_text(text))
            except Exception as e:
                QTimer.singleShot(0, lambda: self._on_voice_text(None))

        t = threading.Thread(target=do_voice, daemon=True)
        t.start()

    def _stop_voice_capture(self):
        """结束语音捕获"""
        if hasattr(self, '_voice_recognizing') and self._voice_recognizing:
            self._voice_recognizing = False

    def _on_voice_text(self, text):
        self.voice_hint.setText("🎤 长按 T 说话")
        self.voice_hint.setStyleSheet(f"color: {FOX_ORANGE}; font-weight: bold; background: transparent;")
        if text:
            self._add_msg("user", f"[语音] {text}")
            self._process_input(text)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_T and self.voice_mode:
            if not self._voice_pressed:
                self._voice_pressed = True
                self._start_voice_capture()
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_T and self.voice_mode:
            self._voice_pressed = False
            self._stop_voice_capture()
        super().keyReleaseEvent(event)

    # ---- 消息显示 ----
    def _add_msg(self, sender, text):
        if sender == "user":
            name_span = f"<span style='color: {FOX_DARK}; font-weight: bold;'>🧑 你</span>"
            bubble_bg = FOX_BUBBLE_USER
            align = "right"
        else:
            name_span = f"<span style='color: {FOX_ORANGE}; font-weight: bold;'>🦊 仙狐</span>"
            bubble_bg = FOX_BUBBLE_AI
            align = "left"

        escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")

        html = f"""
        <div style="text-align:{align}; margin:8px 0;">
            <div style="display:inline-block; background:{bubble_bg};
                border-radius:14px; padding:10px 16px; max-width:80%;
                text-align:left;">
                <div style="margin-bottom:3px; font-size:12px;">{name_span}</div>
                <div style="font-size:13px; line-height:1.5;">{escaped}</div>
            </div>
        </div>
        """
        self.chat_edit.append(html)
        sb = self.chat_edit.verticalScrollBar()
        sb.setValue(sb.maximum())

    # ---- 发送消息 ----
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
                r = {"success": False, "message": "我不知道这个命令😅"}
        except Exception as e:
            r = {"success": False, "message": f"执行出错：{str(e)[:50]}"}

        if r["success"]:
            self._add_msg("assistant", f"✅ {r['message']}")
        else:
            self._add_msg("assistant", f"😅 {r['message']}")

        self.send_btn.setEnabled(True)
        self.send_btn.setText("发送")

    def _chat_with_llm(self, text):
        self.conversation.append({"role": "user", "content": text})

        def on_response(response):
            cleaned = response.strip()
            self._add_msg("assistant", cleaned)
            self.conversation.append({"role": "assistant", "content": cleaned})
            self.send_btn.setEnabled(True)
            self.send_btn.setText("发送")

        def on_error(err):
            self._add_msg("assistant", "😅 小狐仙走神了… 试试直接命令我：\n" + 
                "• 打开 记事本\n• 创建 test.txt\n• 删除 file.txt")
            self.send_btn.setEnabled(True)
            self.send_btn.setText("发送")

        try:
            import ollama
            from tools import get_ollama_tools
            recent = self.conversation[-10:]
            tools = get_ollama_tools()
            self.llm_thread = ToolChatThread(recent, tools)
            self.llm_thread.finished.connect(on_response)
            self.llm_thread.error.connect(on_error)
            self.llm_thread.start()
        except ImportError:
            on_error("ollama 未安装")

    # ---- 拖拽支持 ----
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._dragging:
            self.move(event.globalPos() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = False
            event.accept()

    # ---- 阻止回车关闭对话框 ----
    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            # 输入框的回车由 returnPressed 处理，不传播到 dialog
            if self.input_edit.hasFocus():
                event.accept()
                return
        super().keyPressEvent(event)

    def closeEvent(self, event):
        self._key_thread_running = False
        super().closeEvent(event)


# ======================================================================
# 功能概览（固定文本）
# ======================================================================
class FeatureOverview(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📋 功能概览")
        self.setFixedSize(480, 620)
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        outer = QFrame(self)
        outer.setGeometry(0, 0, 480, 620)
        outer.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 {FOX_LIGHT}, stop:0.5 {FOX_BG1}, stop:1 {FOX_BG2});
                border-radius: 16px;
                border: 1px solid {FOX_BORDER};
            }}
        """)

        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(24, 20, 24, 12)
        outer_layout.setSpacing(10)

        # 顶部：关闭 + 标题
        top_frame = QFrame()
        top_frame.setStyleSheet("background: transparent;")
        top = QHBoxLayout(top_frame)
        top.setContentsMargins(0, 0, 0, 0)
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(26, 26)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,180,120,0.3);
                color: {FOX_TEXT};
                border: none;
                border-radius: 13px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background: rgba(255,100,80,0.4); color: #d44; }}
        """)
        close_btn.clicked.connect(self.close)
        top.addWidget(close_btn)
        top.addStretch()

        title = QLabel("🦊 仙狐桌宠功能一览")
        title.setFont(QFont("Microsoft YaHei UI", 16, QFont.Bold))
        title.setStyleSheet(f"color: {FOX_ORANGE}; background: transparent;")
        title.setAlignment(Qt.AlignCenter)
        top.addWidget(title)
        top.addStretch()
        outer_layout.addWidget(top_frame)

        # 可滚动区域
        from PyQt5.QtWidgets import QScrollArea
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(f"""
            QScrollArea {{ background: transparent; border: none; }}
            QScrollBar:vertical {{
                background: transparent; width: 6px;
            }}
            QScrollBar::handle:vertical {{
                background: rgba(255,140,66,0.3);
                border-radius: 3px; min-height: 30px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)

        cards_widget = QWidget()
        cards_widget.setStyleSheet("background: transparent;")
        cl = QVBoxLayout(cards_widget)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(8)

        cards = [
            ("💬 AI 聊天", "和仙狐自由对话，她会智能回复你"),
            ("🗣️ 语音输入", "点击 🎤 切换语音模式，长按 T 键说话"),
            ("🌤 天气查询", "说「北京天气」仙狐马上告诉你"),
            ("📊 系统状态", "说「电脑状态」查看 CPU、内存占用"),
            ("📍 IP 查询", "说「我的IP」查看外网地址和归属地"),
            ("💬 每日一言", "说「来句鸡汤」获取随机励志语录"),
            ("🎲 今日运势", "说「今天运势」赛博占卜"),
            ("🔐 密码生成", "说「生成密码」得到随机强密码"),
            ("📁 打开程序", "说「打开 记事本」「打开 计算器」"),
            ("📄 文件管理", "自然语言创建、删除、移动文件"),
            ("🎨 仙狐陪伴", "Live2D 仙狐陪在你桌面上~"),
            ("🔄 拖拽 & 缩放", "左键拖拽窗口，右下角缩放"),
        ]

        for icon_title, desc in cards:
            card = QFrame()
            card.setStyleSheet(f"""
                QFrame {{
                    background: rgba(255,248,240,0.6);
                    border-radius: 10px;
                    border: 1px solid {FOX_BORDER};
                }}
            """)
            card_cl = QVBoxLayout(card)
            card_cl.setContentsMargins(14, 8, 14, 8)
            card_cl.setSpacing(2)
            n = QLabel(icon_title)
            n.setFont(QFont("Microsoft YaHei UI", 12, QFont.Bold))
            n.setStyleSheet(f"color: {FOX_ORANGE}; background: transparent;")
            d = QLabel(desc)
            d.setFont(QFont("Microsoft YaHei UI", 10))
            d.setStyleSheet(f"color: {FOX_SUBTEXT}; background: transparent;")
            d.setWordWrap(True)
            card_cl.addWidget(n)
            card_cl.addWidget(d)
            cl.addWidget(card)

        cl.addStretch()
        scroll.setWidget(cards_widget)
        outer_layout.addWidget(scroll, stretch=1)

        close_all = QPushButton("知道啦 ✨")
        close_all.setFixedHeight(40)
        close_all.setCursor(Qt.PointingHandCursor)
        close_all.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {FOX_ORANGE}, stop:1 {FOX_PEACH});
                color: white;
                border: none;
                border-radius: 10px;
                font-weight: bold;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {FOX_BTN_HOVER}, stop:1 {FOX_ACCENT});
            }}
        """)
        close_all.clicked.connect(self.close)
        outer_layout.addWidget(close_all)

    # ---- 拖拽支持 ----
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._drag_start = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if getattr(self, '_dragging', False):
            self.move(event.globalPos() - self._drag_start)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = False
            event.accept()
        super().mouseReleaseEvent(event)


# ======================================================================
# 桌宠管理器
# ======================================================================
class DesktopPetApp:
    def __init__(self):
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("FoxPet")

        # QtWebEngine cache
        qwc_dir = os.path.join(os.environ.get('TEMP', 'C:\\temp'), 'FoxPet_Cache')
        os.makedirs(qwc_dir, exist_ok=True)
        from PyQt5.QtWebEngineWidgets import QWebEngineProfile
        try:
            profile = QWebEngineProfile.defaultProfile()
            profile.setCachePath(qwc_dir)
            profile.setPersistentStoragePath(qwc_dir)
        except Exception:
            pass

        self.pet = FoxPet()
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
    print("[仙狐] 桌宠 v9 - 暖阳仙狐")
    print("=" * 50)
    print()

    try:
        pet = DesktopPetApp()
        sys.exit(pet.run())
    except KeyboardInterrupt:
        print("\n桌宠退出")
    except Exception as e:
        print(f"\n错误：{e}")
        import traceback
        traceback.print_exc()
        input("\n按回车键退出...")


if __name__ == "__main__":
    main()
