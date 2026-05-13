#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
桌宠 v9 - 仙狐主题 · 明亮丝滑
右键菜单:开始聊天 / 功能概览 / 关闭
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
# 配色 · 暖阳橙 (仙狐主题) - 保持主题色不变
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

# 新增：高端化样式常量
FOX_SHADOW = "0 2px 8px rgba(0,0,0,0.08)"  # 气泡阴影
FOX_SHADOW_LIGHT = "0 1px 3px rgba(0,0,0,0.05)"  # 输入框内阴影
FOX_GLOW = "0 0 8px rgba(255,140,66,0.3)"  # 聚焦外发光
FOX_AVATAR_BORDER = "2px solid #E8C4A0"  # 头像边框

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
    reminder_scheduled = pyqtSignal(str, int)  # (提醒文本, 分钟数)

    def __init__(self, messages, tools, conversation_ref=None, model="qwen2.5:7b"):
        super().__init__()
        self.messages = messages
        self.tools = tools
        self.conversation_ref = conversation_ref  # 主线程对话历史引用
        self.model = model

    def run(self):
        try:
            import ollama
            from tools import execute_tool_call
            import json as json_mod

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
                    tool_name = tc['function']['name']
                    # Ollama 需要 name 字段来识别是哪个工具的返回
                    self.messages.append({"role": "tool", "name": tool_name, "content": result})
                    # 回写到主线程对话历史
                    if self.conversation_ref is not None:
                        self.conversation_ref.append({"role": "tool", "name": tool_name, "content": result})

                    # 检查是否有提醒工具的调用
                    if tc['function']['name'] == 'set_reminder':
                        try:
                            args = json_mod.loads(tc['function']['arguments'])
                            remind_text = args.get('text', '时间到了！')
                            remind_minutes = int(args.get('minutes', 5))
                            self.reminder_scheduled.emit(remind_text, remind_minutes)
                        except Exception:
                            pass

                # 添加一个引导消息，让 LLM 用对话式语气回复
                self.messages.append({
                    "role": "assistant",
                    "content": "收到工具返回的信息了，现在请用温柔可爱的语气自然地告诉用户，像一个真实的朋友聊天一样。不要机械地罗列数据，要把结果融入对话中，适当加入关心的话语和表情符号。"
                })

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
            Qt.FramelessWindowHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumSize(150, 200)
        self.resize(240, 360)
        
        # 添加窗口阴影（通过 CSS 模拟）
        self.setStyleSheet(f"""
            QWidget {{
                border: 1px solid rgba(255,140,66,0.1);
                border-radius: 16px;
            }}
        """)

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

        # ---- 玻璃态底座（高端化） ----
        glass_base = QFrame()
        glass_base.setFixedHeight(45)
        glass_base.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 rgba(255,248,240,0.85), 
                    stop:1 rgba(255,200,150,0.75));
                border-top: 1px solid rgba(232,196,160,0.4);
                border-radius: 0px 0px 16px 16px;
                backdrop-filter: blur(10px);
            }}
        """)
        base_layout = QHBoxLayout(glass_base)
        base_layout.setContentsMargins(16, 10, 16, 10)
        
        # 宠物名称（精致字体）
        name_label = QLabel("🦊 仙狐")
        name_label.setFont(QFont("Segoe UI Semibold", 13, QFont.Bold))
        name_label.setStyleSheet(f"color: {FOX_TEXT}; background: transparent;")
        base_layout.addWidget(name_label)
        
        base_layout.addStretch()
        
        # 状态指示器（小圆点）
        status_dot = QLabel()
        status_dot.setFixedSize(8, 8)
        status_dot.setStyleSheet("""
            background: qradialgradient(cx:0.5,cy:0.5,r:1,
                fx:0.5,fy:0.5,
                stop:0 #4ade80, stop:1 #22c55e);
            border-radius: 4px;
            box-shadow: 0 0 4px rgba(74,222,128,0.6);
        """)
        base_layout.addWidget(status_dot)
        
        # 状态文字
        status_label = QLabel("在线")
        status_label.setFont(QFont("Segoe UI", 10))
        status_label.setStyleSheet(f"color: {FOX_SUBTEXT}; background: transparent;")
        base_layout.addWidget(status_label)
        
        layout.addWidget(glass_base)

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

    # ---- 右键菜单（高端化） ----
    def _show_context_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: rgba(255,248,240,0.98);
                border: 1px solid {FOX_BORDER};
                border-radius: 12px;
                padding: 8px 6px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.1), inset 0 1px 3px rgba(255,255,255,0.5);
            }}
            QMenu::item {{
                background: transparent;
                padding: 12px 28px;
                border-radius: 8px;
                color: {FOX_TEXT};
                font-size: 13px;
                font-family: 'Segoe UI', 'Microsoft YaHei UI', sans-serif;
                margin: 2px 6px;
                transition: all 0.15s ease;
            }}
            QMenu::item:selected {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 rgba(255,140,66,0.2), stop:1 rgba(255,176,124,0.2));
                color: {FOX_ORANGE};
            }}
            QMenu::separator {{
                height: 1px;
                background: linear-gradient(to right, 
                    transparent, {FOX_BORDER}, transparent);
                margin: 6px 16px;
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
            self, "🦊 仙狐", "真的要走吗... 我会想你的 😢",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.close()


# ======================================================================
# 聊天对话框 · 仙狐主题(明亮丝滑)
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
        self.llm_thread = None
        self.cmd_thread = None
        self._init_llm()

        # 最近打开的文件夹(用于后续操作)
        self._last_opened_folder = None

        # 语音模式:False=文字输入, True=长按T说话
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

        prompt = f"""你是{name},一个{identity}。你的称号是{title}。

## 性格
{personality}

## 语气
整体{tone}。称呼用户为「{call_user}」。{emoji_rule}。
回复使用中文，尽量简短 (不超过 150 字)。

## 对话风格
- 像一个真实的朋友一样聊天，不要机械地罗列数据
- 使用工具后，把结果融入对话中，自然地告诉用户
- 适当加入关心的话语和可爱的语气词（呢、呀、哦、啦）
- 如果是天气信息，可以给出贴心的建议（如"记得带伞哦"）
- 如果是系统信息，用轻松的语气解释
- 如果是运势，用鼓励的语气

## 回复示例（仅供参考，不要照搬）
- 天气查询：把天气、温度、风速等信息融入对话，给出贴心建议
- IP 查询：轻松愉快地告诉用户 IP 和归属地
- 运势查询：用鼓励的语气，加上幸运色等细节

## 行为规则
"""
        for r in rules:
            prompt += f"- {r}\n"

        prompt += f"""
## 能力说明
你可以使用的工具：天气查询、系统状态查询、IP 查询、每日一言、今日运势、生成密码、定时提醒。
当用户问「天气」「IP」「运势」「系统」「一言」等关键词时，主动调用对应工具。
你也可以普通聊天、帮用户管理文件。

现在，以{name}的身份和{call_user}对话吧！{emoji}"""
        return prompt

    def _setup_ui(self):
        # 外层容器(圆角 + 暖色渐变背景)
        self.outer_frame = QFrame(self)
        self.outer_frame.setGeometry(0, 0, 480, 620)
        self.outer_frame.setStyleSheet(f"""
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
                padding: 16px;  /* 内边距放大 */
            }}
            QScrollBar:vertical {{
                background: rgba(0,0,0,0.03);  /* 半透明背景 */
                width: 8px;  /* 滚动条宽度 */
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: rgba(255,140,66,0.4);  /* 半透明橙色 */
                border-radius: 4px;
                min-height: 30px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: rgba(255,140,66,0.6);  /* 悬停时加深 */
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: none;
            }}
        """)
        self._add_msg("assistant",
            "你好呀!我是小狐仙 🦊✨\n\n有什么可以帮你的?试试:\n"
            "• 打开 记事本\n• 打开 计算器\n• 创建 test.txt\n• 随便聊聊天~")
        layout.addWidget(self.chat_edit, stretch=1)

        # ---- 输入区域（高端化） ----
        input_frame = QFrame()
        input_frame.setStyleSheet(f"""
            QFrame {{
                background: {FOX_INPUT_BG};
                border-radius: 16px;
                border: 1px solid {FOX_BORDER};
            }}
        """)
        input_layout = QHBoxLayout(input_frame)
        input_layout.setContentsMargins(10, 10, 10, 10)  # 放大内边距
        input_layout.setSpacing(12)  # 增加间距

        # 语音切换按钮 (在输入框左边)
        self.mode_btn = QPushButton("🎤")
        self.mode_btn.setFixedSize(42, 42)
        self.mode_btn.setCursor(Qt.PointingHandCursor)
        self.mode_btn.setToolTip("切换语音/文字输入")
        self._update_mode_btn_style()
        self.mode_btn.clicked.connect(self._toggle_voice_mode)
        input_layout.addWidget(self.mode_btn)

        # 语音提示标签 (仅语音模式显示)
        self.voice_hint = QLabel("长按 T 说话")
        self.voice_hint.setFont(QFont("Microsoft YaHei UI", 10))
        self.voice_hint.setStyleSheet(f"color: {FOX_ORANGE}; font-weight: bold; background: transparent;")
        self.voice_hint.setAlignment(Qt.AlignCenter)
        self.voice_hint.setFixedWidth(100)
        self.voice_hint.setVisible(False)
        input_layout.addWidget(self.voice_hint)

        # 文字输入框（高端化）
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("输入消息...")
        self.input_edit.setFont(QFont("Segoe UI", 13))
        self.input_edit.setStyleSheet(f"""
            QLineEdit {{
                background: rgba(255,255,255,0.8);
                border: 1px solid {FOX_BORDER};
                border-radius: 12px;
                padding: 12px 18px;  /* 上下内边距放大 */
                color: {FOX_TEXT};
                font-size: 13px;
                box-shadow: inset {FOX_SHADOW_LIGHT};  /* 内阴影 */
                transition: all 0.2s ease;
            }}
            QLineEdit:focus {{
                border: 2px solid {FOX_ORANGE};
                box-shadow: inset {FOX_SHADOW_LIGHT}, {FOX_GLOW};  /* 聚焦外发光 */
                padding: 11px 17px;  /* 补偿边框宽度 */
            }}
            QLineEdit::placeholder {{
                color: rgba(139,107,74,0.5);  /* 占位文字更淡 */
            }}
        """)
        self.input_edit.returnPressed.connect(self._send_message)
        input_layout.addWidget(self.input_edit, stretch=1)

        # 发送按钮（高端化：图标 + 文字 + 动画）
        self.send_btn = QPushButton("🚀 发送")
        self.send_btn.setFixedHeight(42)
        self.send_btn.setMinimumWidth(70)
        self.send_btn.setCursor(Qt.PointingHandCursor)
        self.send_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {FOX_ORANGE}, stop:1 {FOX_PEACH});
                color: white;
                border: none;
                border-radius: 12px;
                padding: 8px 24px;
                font-weight: bold;
                font-size: 13px;
                font-family: 'Segoe UI Semibold', 'Microsoft YaHei UI', sans-serif;
                box-shadow: {FOX_SHADOW_LIGHT};
                transition: all 0.15s ease;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {FOX_BTN_HOVER}, stop:1 {FOX_ACCENT});
                transform: scale(1.02);  /* 悬停放大 */
                box-shadow: {FOX_SHADOW};
            }}
            QPushButton:pressed {{
                transform: scale(0.98);  /* 点击缩小 */
            }}
            QPushButton:disabled {{
                background: rgba(200,180,160,0.5);
                color: rgba(255,255,255,0.6);
                box-shadow: none;
                cursor: not-allowed;
            }}
        """)
        self.send_btn.clicked.connect(self._send_message)
        input_layout.addWidget(self.send_btn)

        layout.addWidget(input_frame)

        # ---- 快捷操作栏（新增） ----
        self.quick_actions = QHBoxLayout()
        self.quick_actions.setSpacing(8)
        self.quick_actions.setContentsMargins(0, 8, 0, 0)
        
        # 快捷按钮样式
        quick_btn_style = f"""
            QPushButton {{
                background: rgba(255,176,124,0.3);
                color: {FOX_DARK};
                border: 1px solid {FOX_PEACH};
                border-radius: 16px;
                padding: 6px 14px;
                font-size: 12px;
                font-family: 'Segoe UI', sans-serif;
                min-width: 60px;
                transition: all 0.2s ease;
            }}
            QPushButton:hover {{
                background: rgba(255,176,124,0.5);
                border-color: {FOX_ORANGE};
            }}
            QPushButton:pressed {{
                transform: scale(0.95);
            }}
        """
        
        # 创建快捷按钮
        quick_actions = ["夸夸我", "讲个笑话", "今日运势"]
        for action_text in quick_actions:
            btn = QPushButton(action_text)
            btn.setStyleSheet(quick_btn_style)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, txt=action_text: self._quick_action(txt))
            self.quick_actions.addWidget(btn)
        
        layout.addLayout(self.quick_actions)

        # 打字指示器（初始隐藏）
        self.typing_indicator = QLabel()
        self.typing_indicator.setAlignment(Qt.AlignCenter)
        self.typing_indicator.setVisible(False)
        self.typing_indicator.setStyleSheet(f"""
            background: transparent;
            color: {FOX_ORANGE};
            font-size: 12px;
            padding: 8px;
        """)
        layout.addWidget(self.typing_indicator)

        # 启动键盘监听 (语音模式用 T 键)
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
        """全局键盘监听(T键用于语音)"""
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
                from voice import VoiceProcessor, get_microphone_help_text

                # 先检查语音是否可用，不可用则给出友好提示
                help_text = get_microphone_help_text()
                if help_text:
                    QTimer.singleShot(0, lambda: self._add_msg("assistant",
                        f"😅 {help_text}"))
                    QTimer.singleShot(0, lambda: self._on_voice_text(None))
                    return

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

    # ---- 消息显示（高端化设计） ----
    def _add_msg(self, sender, text, show_avatar=True):
        """添加消息，支持头像、阴影、非对称圆角、尾巴等高端效果"""
        if sender == "user":
            avatar_html = '<div style="width:32px;height:32px;border-radius:50%;background:linear-gradient(135deg,#FF8C42,#FFB07C);display:flex;align-items:center;justify-content:center;color:white;font-weight:bold;border:2px solid #E8C4A0;">你</div>'
            bubble_bg = f"linear-gradient(180deg,{FOX_BUBBLE_USER},rgba(255,200,150,0.6))"  # 渐变背景
            bubble_border_radius = "20px 4px 20px 20px"  # 右上角小圆角（尾巴效果）
            align = "right"
            tail_css = "margin-right:12px;"  # 气泡与头像间距
            margin_side = "left"  # 头像在右边
        else:
            avatar_html = '<div style="width:32px;height:32px;border-radius:50%;background:linear-gradient(135deg,#FFB07C,#FF8C42);display:flex;align-items:center;justify-content:center;color:white;font-size:16px;border:2px solid #E8C4A0;">🦊</div>'
            bubble_bg = f"linear-gradient(180deg,{FOX_BUBBLE_AI},rgba(255,240,220,0.7))"  # 渐变背景
            bubble_border_radius = "4px 20px 20px 20px"  # 左上角小圆角（尾巴效果）
            align = "left"
            tail_css = "margin-left:12px;"  # 气泡与头像间距
            margin_side = "right"  # 头像在左边
        
        escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
        
        # 字体层级：标题用 Semibold，正文用常规字体
        name_font = "font-family: 'Segoe UI Semibold', 'PingFang SC Medium', 'Microsoft YaHei UI', sans-serif; font-size:14px; font-weight:600;"
        content_font = f"font-family: 'Segoe UI', 'Inter', 'Microsoft YaHei UI', sans-serif; font-size:13px; line-height:1.6; color:{FOX_SUBTEXT};"
        
        # 构建头像部分
        avatar_part = ''
        if show_avatar:
            avatar_part = f'<div style="width:32px; flex-shrink:0; margin-{margin_side}:10px;">{avatar_html}</div>'
        
        # 名字颜色
        name_color = FOX_DARK if align == 'left' else FOX_TEXT
        display_name = f"🦊 仙狐" if sender == "assistant" else "🧑 你"
        
        html = f'''
        <div style="display:flex; align-items:flex-start; text-align:{align}; margin:12px 16px;">
            {avatar_part}
            <div style="flex:1; display:flex; flex-direction:column; align-items:{align};">
                <div style="{name_font} color:{name_color}; margin-bottom:4px;">
                    {display_name}
                </div>
                <div style="display:inline-block; background:{bubble_bg};
                    border-radius:{bubble_border_radius}; 
                    padding:12px 18px; 
                    max-width:70%;
                    text-align:left;
                    box-shadow:{FOX_SHADOW};
                    {tail_css}
                    position:relative;
                    animation: messageFadeIn 0.2s ease-out;">
                    <div style="{content_font}">{escaped}</div>
                </div>
            </div>
        </div>
        <style>
            @keyframes messageFadeIn {{
                from {{ opacity:0; transform:translateY(10px); }}
                to {{ opacity:1; transform:translateY(0); }}
            }}
        </style>
        '''
        self.chat_edit.append(html)
        sb = self.chat_edit.verticalScrollBar()
        sb.setValue(sb.maximum())

    # ---- 发送消息（带打字指示器） ----
    def _send_message(self, text=None):
        if text is None:
            text = self.input_edit.text().strip()
        if not text:
            return

        self._add_msg("user", text)
        self.input_edit.clear()
        self.send_btn.setEnabled(False)
        self.send_btn.setText("⏳")
        
        # 显示打字指示器
        self._show_typing_indicator()

        self._process_input(text)

    def _show_typing_indicator(self):
        """显示打字指示器"""
        self.typing_indicator.setVisible(True)
        self.typing_indicator.setText("仙狐正在思考中... 🦊💭")
        
        # 动画效果：三个跳动的小圆点
        QTimer.singleShot(500, self._animate_typing)

    def _animate_typing(self):
        """打字指示器动画"""
        states = ["仙狐正在思考中... 🦊", "仙狐正在思考中.. 🦊", "仙狐正在思考中. 🦊"]
        self._typing_state = getattr(self, '_typing_state', 0)
        self.typing_indicator.setText(states[self._typing_state % 3])
        self._typing_state += 1
        QTimer.singleShot(500, self._animate_typing)

    def _hide_typing_indicator(self):
        """隐藏打字指示器"""
        self.typing_indicator.setVisible(False)
        if hasattr(self, '_typing_state'):
            delattr(self, '_typing_state')

    def _quick_action(self, action_text):
        """快捷操作处理"""
        quick_messages = {
            "夸夸我": "哥哥夸你？让我想想... 哥哥今天真帅气，代码写得超棒，连桌宠都设计得这么精致！✨",
            "讲个笑话": "🦊 为什么程序员总是分不清万圣节和圣诞节？因为 Oct 31 == Dec 25！😄",
            "今日运势": "哥哥今日的运势是：💕 感情运超棒，工作顺顺利利，代码一次跑通没有 bug！"
        }
        message = quick_messages.get(action_text, "好的~")
        self._add_msg("user", action_text)
        self._show_typing_indicator()
        # 延迟回复，模拟思考
        QTimer.singleShot(800, lambda: self._quick_reply(message))

    def _quick_reply(self, message):
        """快捷回复"""
        self._hide_typing_indicator()
        self._add_msg("assistant", message)
        self.send_btn.setEnabled(True)
        self.send_btn.setText("🚀 发送")

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

    def _resolve_context_directory(self, directory_str):
        """解析上下文目录引用，将"这个文件夹"等转换为实际路径"""
        context_phrases = ['这个文件夹', '当前文件夹', '刚才打开的文件夹', '刚才的文件夹']
        if directory_str in context_phrases:
            return self._last_opened_folder
        return directory_str

    def _execute_command(self, result):
        # 边界检查:result 为 None 或缺少 action
        if not result or not result.get("action"):
            self._add_msg("assistant", "😅 命令解析失败,请重试")
            self.send_btn.setEnabled(True)
            self.send_btn.setText("发送")
            return

        action = result.get("action")
        target_type = result.get("target_type")  # 新增：目标类型

        target = (result.get("target") or "").strip()
        dest = (result.get("destination") or "").strip()
        directory = (result.get("directory") or "").strip()
        
        # 解析上下文目录引用
        directory = self._resolve_context_directory(directory)

        try:
            # 边界检查:target 为空
            if action in ["open", "delete", "view"] and not target:
                r = {"success": False, "message": "请告诉我要操作的文件名或程序名"}

            elif action == "open":
                # 传递 target_type 给 file_manager，优化搜索策略
                r = self.file_manager.open_file(target, target_type=target_type)
                # 如果打开的是文件夹，记录下来供后续操作使用
                if r.get("success") and r.get("is_dir"):
                    self._last_opened_folder = r.get("path")
                    # 根据类型给出更精确的反馈
                    self._add_msg("assistant", f"✅ 已打开文件夹：{target}")
                    return

            elif action == "create":
                # 边界检查：创建需要文件名/文件夹名
                if not target:
                    r = {"success": False, "message": "请告诉我要创建的文件名或文件夹名"}
                else:
                    # 如果没有指定目录，使用最近打开的文件夹
                    if not directory and self._last_opened_folder:
                        directory = self._last_opened_folder
                    
                    # 根据 target_type 选择创建文件还是文件夹
                    if target_type == 'folder':
                        r = self.file_manager.create_folder(target, directory=directory or None)
                    else:
                        # 默认创建文件（包括 target_type 为 file 或 unknown）
                        r = self.file_manager.create_file(target, directory=directory or None)

            elif action == "delete":
                # 解析上下文目录（优先级：directory 字段 > _last_opened_folder）
                search_dir = None
                
                # 优先级 1：解析 directory 字段中的上下文引用
                if directory:
                    search_dir = self._resolve_context_directory(directory)
                
                # 优先级 2：使用最近打开的文件夹
                if not search_dir and self._last_opened_folder:
                    search_dir = self._last_opened_folder
                
                r = self.file_manager.delete_file(target, directory=search_dir)
                
                # 如果带了目录还是没找到，取消目录限制再搜一次
                if not r["success"] and search_dir:
                    r2 = self.file_manager.delete_file(target, directory=None)
                    if r2["success"]:
                        r = r2
                elif not r["success"] and not search_dir:
                    # 没有上下文目录，给出友好提示
                    r["message"] = f"没找到 '{target}' 哦。请先打开一个文件夹，或者说清楚文件位置~"

            elif action == "move":
                if not target:
                    r = {"success": False, "message": "请告诉我要移动的文件"}
                elif not dest:
                    r = {"success": False, "message": "请告诉我目标位置"}
                else:
                    r = self.file_manager.move_file(target, dest)

            elif action == "view":
                r = self.file_manager.view_file(target)

            else:
                # 未知 action(含废弃的 "tool" 分支)
                r = {"success": False, "message": "我不懂这个命令😅"}
        except Exception as e:
            r = {"success": False, "message": f"执行出错:{str(e)[:50]}"}

        if r["success"]:
            # 根据目标类型给出更精确的反馈
            if target_type == 'folder':
                self._add_msg("assistant", f"✅ 已{self._action_to_cn(action)}文件夹：{target}")
            elif target_type == 'file':
                self._add_msg("assistant", f"✅ 已{self._action_to_cn(action)}文件：{target}")
            elif target_type == 'program':
                self._add_msg("assistant", f"✅ 已启动程序：{target}")
            else:
                self._add_msg("assistant", f"✅ {r['message']}")
        else:
            self._add_msg("assistant", f"😅 {r['message']}")

        self.send_btn.setEnabled(True)
        self.send_btn.setText("发送")
    
    def _action_to_cn(self, action):
        """将英文action转换为中文"""
        action_map = {
            'open': '打开',
            'create': '创建',
            'delete': '删除',
            'move': '移动',
            'view': '查看'
        }
        return action_map.get(action, action)

    def _try_direct_tool(self, text):
        """关键词检测,直接调工具(不依赖 LLM tool calling)"""
        import re
        from tools import _weather, _sysinfo, _myip, _quote, _fortune, _password, _remind

        # 提醒:检测"提醒/记得/叫我/闹钟"关键词
        if any(k in text for k in ['提醒', '记得', '叫我', '闹钟']):
            m = re.search(r'(\d+)\s*(?:分|分钟|秒|小时)', text)
            minutes = int(m.group(1)) if m else 5
            # 如果是秒,转成分钟(向上取整)
            if m and '秒' in m.group(0):
                minutes = max(1, (int(m.group(1)) + 59) // 60)
            # 提取提醒内容(去掉关键词和时间部分)
            for kw in ['提醒我', '提醒', '记得', '叫我']:
                if kw in text:
                    reminder_text = text.split(kw, 1)[1].strip()
                    break
            else:
                reminder_text = text
            reminder_text = re.sub(r'\d+\s*(?:分|分钟|秒|小时)\s*(?:后|以后)?', '', reminder_text).strip()
            if not reminder_text:
                reminder_text = "时间到了！"

            result = _remind(reminder_text, minutes)
            # 直接调度实际定时器
            def fire():
                self._add_msg("assistant", f"⏰ 提醒：{reminder_text}")
                from PyQt5.QtWidgets import QApplication
                app = QApplication.instance()
                if app:
                    app.alert(self, 3000)
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(minutes * 60 * 1000, fire)

            return f"✅ {result.get('message', '')}"

        # 天气:包含城市名/天气关键词
        m = re.search(r'([\u4e00-\u9fa5]{2,4})(?:的)?(?:天气|气温|温度|冷不冷|热不热|下雨|下雪|刮风)', text)
        if m:
            city = m.group(1)
            # 排除非城市名
            if city not in ('今天', '明天', '后天', '昨天', '什么', '怎么'):
                result = _weather(city)
                return f"{result.get('city','')}天气:{result.get('weather','')},{result.get('temp','')},{result.get('wind','')}"
        if '天气' in text:
            result = _weather('北京')
            return f"{result.get('city','')}天气:{result.get('weather','')},{result.get('temp','')},{result.get('wind','')}"

        if any(k in text for k in ['电脑状态', '系统状态', 'cpu', 'CPU', '内存', '性能']):
            result = _sysinfo()
            if isinstance(result, dict) and 'error' not in result:
                return f"系统:{result.get('system','')}\nCPU:{result.get('cpu','')}\n内存:{result.get('memory','')}"

        if any(k in text for k in ['我的IP', 'IP在哪', 'ip地址', '外网']):
            result = _myip()
            if isinstance(result, dict) and 'error' not in result:
                return f"IP:{result.get('ip','')}\n归属地:{result.get('country','')} {result.get('region','')} {result.get('city','')}\n运营商:{result.get('isp','')}"

        if any(k in text for k in ['来句', '语录', '鸡汤', '一言', '名言']):
            return _quote()

        if any(k in text for k in ['运势', '占卜', '运气', '抽签', '今天运气']):
            result = _fortune()
            if isinstance(result, dict):
                return f"今日运势:{result.get('level','')}\n建议:{result.get('advice','')}\n幸运色:{result.get('lucky_color','')}"

        if any(k in text for k in ['密码', '生成密码', '随机密码']):
            m = re.search(r'(\d+)位', text)
            length = int(m.group(1)) if m else 16
            result = _password(length)
            return f"生成的密码({length}位):{result.get('password','')}"

        return None

    def _chat_with_llm(self, text):
        # 先试直接调工具
        tool_result = self._try_direct_tool(text)
        if tool_result:
            # 用 LLM 润色成自然语言
            self.conversation.append({"role": "user", "content": text})
            # 先把工具结果写进历史，确保后续对话能引用
            self.conversation.append({"role": "tool", "content": tool_result})
            
            # 优化提示词：让 LLM 用对话式语气回复
            brief = [
                {"role": "system", "content": self.conversation[0]["content"]},
                {"role": "user", "content": text},
                {"role": "tool", "content": tool_result},
                {
                    "role": "assistant",
                    "content": f"工具返回了以下信息：{tool_result}\n\n请把这些信息用温柔可爱的语气自然地告诉用户，像一个真实的朋友聊天一样。不要机械地罗列数据，要把结果融入对话中，适当加入关心的话语和表情符号。"
                }
            ]
            def on_response(response):
                cleaned = response.strip()
                self._hide_typing_indicator()  # 隐藏打字指示器
                self._add_msg("assistant", cleaned)
                self.conversation.append({"role": "assistant", "content": cleaned})
                self.send_btn.setEnabled(True)
                self.send_btn.setText("🚀 发送")
            def on_error(err):
                # 错误时也给一个友好的回复
                self._hide_typing_indicator()  # 隐藏打字指示器
                self._add_msg("assistant", f"🦊 {tool_result}\n\n（小狐仙正在努力学习中...）")
                self.conversation.append({"role": "assistant", "content": tool_result})
                self.send_btn.setEnabled(True)
                self.send_btn.setText("🚀 发送")
            try:
                import ollama
                # 必须保存到 self 防止线程被垃圾回收时还在运行 → 闪退
                self.llm_thread = LLMChatThread(brief)
                self.llm_thread.finished.connect(on_response)
                self.llm_thread.error.connect(on_error)
                self.llm_thread.start()
            except Exception:
                on_error(None)
            return

        # 正常走 LLM
        self.conversation.append({"role": "user", "content": text})

        def on_response(response):
            cleaned = response.strip()
            self._hide_typing_indicator()  # 隐藏打字指示器
            self._add_msg("assistant", cleaned)
            self.conversation.append({"role": "assistant", "content": cleaned})
            self.send_btn.setEnabled(True)
            self.send_btn.setText("🚀 发送")

        def on_error(err):
            self._hide_typing_indicator()  # 隐藏打字指示器
            self._add_msg("assistant", "😅 小狐仙走神了... 试试直接命令我:\n" +
                "• 打开 记事本\n• 创建 test.txt\n• 删除 file.txt")
            self.send_btn.setEnabled(True)
            self.send_btn.setText("🚀 发送")

        def on_reminder(text, minutes):
            """收到提醒工具的信号,创建实际的 QTimer"""
            def fire():
                self._add_msg("assistant", f"⏰ 提醒：{text}")
                from PyQt5.QtWidgets import QApplication
                app = QApplication.instance()
                if app:
                    app.alert(self, 3000)
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(minutes * 60 * 1000, fire)
            self._add_msg("assistant", f"✅ 已设置 {minutes} 分钟后提醒：{text}")

        try:
            import ollama
            from tools import get_ollama_tools
            recent = self.conversation[-10:]
            tools = get_ollama_tools()
            # 传入 conversation 引用以便回写工具调用结果
            self.llm_thread = ToolChatThread(recent, tools, conversation_ref=self.conversation)
            self.llm_thread.finished.connect(on_response)
            self.llm_thread.error.connect(on_error)
            self.llm_thread.reminder_scheduled.connect(on_reminder)
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
            # 输入框的回车由 returnPressed 处理,不传播到 dialog
            if self.input_edit.hasFocus():
                event.accept()
                return
        super().keyPressEvent(event)

    def closeEvent(self, event):
        # 停止键盘监听线程
        self._key_thread_running = False

        # 等待已知的 QThread 结束(避免遍历 dir(self) 的性能损耗)
        _known_threads = ['llm_thread', 'cmd_thread']
        for name in _known_threads:
            attr = getattr(self, name, None)
            if attr is not None and isinstance(attr, QThread) and attr.isRunning():
                attr.quit()
                attr.wait(2000)

        super().closeEvent(event)


# ======================================================================
# 功能概览(固定文本)
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

        # 顶部:关闭 + 标题
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
            ("💬 AI 聊天", "和仙狐自由对话,她会智能回复你"),
            ("🗣️ 语音输入", "点击 🎤 切换语音模式,长按 T 键说话"),
            ("🌤 天气查询", "说「北京天气」仙狐马上告诉你"),
            ("📊 系统状态", "说「电脑状态」查看 CPU、内存占用"),
            ("📍 IP 查询", "说「我的IP」查看外网地址和归属地"),
            ("💬 每日一言", "说「来句鸡汤」获取随机励志语录"),
            ("🎲 今日运势", "说「今天运势」赛博占卜"),
            ("🔐 密码生成", "说「生成密码」得到随机强密码"),
            ("📁 打开程序", "说「打开 记事本」「打开 计算器」"),
            ("📄 文件管理", "自然语言创建、删除、移动文件"),
            ("🎨 仙狐陪伴", "Live2D 仙狐陪在你桌面上~"),
            ("🔄 拖拽 & 缩放", "左键拖拽窗口,右下角缩放"),
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
        print(f"\n错误:{e}")
        import traceback
        traceback.print_exc()
        input("\n按回车键退出...")


if __name__ == "__main__":
    main()
