#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
桌宠 v9 - 仙狐主题 · 明亮丝滑
右键菜单:开始聊天 / 功能概览 / 关闭
"""

import sys, os, json, threading, time as time_module, re
from typing import Optional

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
from PyQt5.QtCore import Qt, QTimer, QPoint, QUrl, pyqtSignal, QThread, QEvent
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
                # 重要：先将 assistant 的 tool_calls 消息回写到主对话历史
                # 这样上下文才完整：assistant 调用工具 -> tool 返回结果
                if self.conversation_ref is not None:
                    self.conversation_ref.append({
                        "role": "assistant",
                        "content": msg.get('content', ''),
                        "tool_calls": msg['tool_calls']
                    })
                
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
        """自定义样式关闭确认弹窗"""
        dlg = QDialog(self)
        dlg.setWindowTitle("关闭仙狐")
        dlg.setFixedSize(360, 220)
        dlg.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        dlg.setAttribute(Qt.WA_TranslucentBackground)

        frame = QFrame(dlg)
        frame.setGeometry(0, 0, 360, 220)
        frame.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 {FOX_LIGHT}, stop:0.5 {FOX_BG1}, stop:1 {FOX_BG2});
                border-radius: 16px;
                border: 1px solid {FOX_BORDER};
            }}
        """)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(10)

        # 图标区域
        icon_label = QLabel("🦊")
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setFont(QFont("Segoe UI", 36))
        icon_label.setStyleSheet("background: transparent;")
        layout.addWidget(icon_label)

        # 文字
        msg = QLabel("真的要走吗... 我会想你的 😢")
        msg.setAlignment(Qt.AlignCenter)
        msg.setFont(QFont("Microsoft YaHei UI", 12))
        msg.setStyleSheet(f"color: {FOX_TEXT}; background: transparent;")
        msg.setWordWrap(True)
        layout.addWidget(msg)

        layout.addStretch()

        # 按钮行
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        no_btn = QPushButton("😊 我开玩笑的")
        no_btn.setFixedHeight(38)
        no_btn.setCursor(Qt.PointingHandCursor)
        no_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(232,196,160,0.3);
                color: {FOX_TEXT};
                border: 1px solid {FOX_BORDER};
                border-radius: 10px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background: rgba(232,196,160,0.5); }}
        """)
        no_btn.clicked.connect(dlg.close)
        btn_row.addWidget(no_btn, stretch=1)

        yes_btn = QPushButton("😢 再见")
        yes_btn.setFixedHeight(38)
        yes_btn.setCursor(Qt.PointingHandCursor)
        yes_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {FOX_ORANGE}, stop:1 {FOX_PEACH});
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {FOX_BTN_HOVER}, stop:1 {FOX_ACCENT});
            }}
        """)
        yes_btn.clicked.connect(lambda: (dlg.close(), self.close()))
        btn_row.addWidget(yes_btn, stretch=1)

        layout.addLayout(btn_row)

        dlg.exec_()

    def closeEvent(self, event):
        """窗口关闭事件 - 清理资源"""
        # 清理 WebView
        if hasattr(self, 'webview'):
            self.webview.deleteLater()
        
        # 清理所有资源
        event.accept()


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
        # 线程管理：保存所有线程引用，确保资源正确释放
        self._background_threads = []
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

        # ---- 淡入动画 ----
        self._fade_opacity = 0.0
        self._fade_in_timer = QTimer(self)
        self._fade_in_timer.timeout.connect(self._fade_in_step)
        self._fade_in_timer.start(16)

    def _fade_in_step(self):
        self._fade_opacity = min(1.0, self._fade_opacity + 0.08)
        self.setWindowOpacity(self._fade_opacity)
        if self._fade_opacity >= 1.0:
            self._fade_in_timer.stop()

    def _fade_out_close(self):
        """淡出后关闭"""
        self._fade_in_timer.stop()
        if hasattr(self, '_fade_out_timer') and self._fade_out_timer.isActive():
            return
        self._fade_out_timer = QTimer(self)
        self._fade_out_timer.timeout.connect(self._fade_out_step)
        self._fade_out_opacity = self.windowOpacity()
        self._fade_out_timer.start(16)

    def _fade_out_step(self):
        self._fade_out_opacity = max(0, self._fade_out_opacity - 0.1)
        self.setWindowOpacity(self._fade_out_opacity)
        if self._fade_out_opacity <= 0:
            self._fade_out_timer.stop()
            self.close()

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
            with open('character.json', 'r', encoding='utf-8') as f:
                char = json.load(f)
            print("[仙狐] 加载性格配置 ✓")
            return char
        except Exception as e:
            print(f"[仙狐] 使用默认性格配置：{e}")
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
        close_btn.setFixedSize(30, 30)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setToolTip("关闭")
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,180,120,0.25);
                color: {FOX_TEXT};
                border: 1px solid rgba(232,196,160,0.3);
                border-radius: 15px;
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: rgba(255,90,70,0.35);
                color: #d44;
                border-color: rgba(255,90,70,0.5);
            }}
            QPushButton:pressed {{
                background: rgba(255,60,40,0.5);
            }}
        """)
        close_btn.clicked.connect(self._fade_out_close)
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

        # 保存线程引用，确保资源管理
        t = threading.Thread(target=listen_keys, daemon=True)
        self._background_threads.append(t)
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

        # 保存线程引用，确保资源管理
        t = threading.Thread(target=do_voice, daemon=True)
        self._background_threads.append(t)
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
        # 修复 3：检查是否有待确认的创建操作
        if hasattr(self, '_pending_create') and self._pending_create:
            pending = self._pending_create
            if '文件' in text or '文件夹' in text:
                # 用户确认了类型
                target = pending['target']
                directory = pending['directory']
                
                if '文件夹' in text:
                    # 创建文件夹
                    r = self.file_manager.create_folder(target, directory=directory or None)
                    if r["success"]:
                        self._add_msg("assistant", f"✅ 已创建文件夹：{target}")
                    else:
                        self._add_msg("assistant", f"❌ {r['message']}")
                else:
                    # 创建文件
                    r = self.file_manager.create_file(target, directory=directory or None)
                    if r["success"]:
                        self._add_msg("assistant", f"✅ 已创建文件：{target}")
                    else:
                        self._add_msg("assistant", f"❌ {r['message']}")
                
                # 清除待确认状态
                delattr(self, '_pending_create')
                self.send_btn.setEnabled(True)
                self.send_btn.setText("🚀 发送")
                return
        
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
        destination = (result.get("destination") or "").strip()  # 修复 1：统一使用 destination
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
                elif target_type == 'unknown':
                    # 类型不明确，询问用户确认
                    self._add_msg("assistant", f"🤔 你想创建「{target}」是文件还是文件夹呢？\n\n• 回复「文件」创建文件\n• 回复「文件夹」创建文件夹")
                    # 设置一个临时状态，等待用户确认
                    self._pending_create = {"target": target, "directory": directory}
                    r = {"success": False, "message": "等待用户确认类型"}
                else:
                    # 如果没有指定目录，使用最近打开的文件夹
                    if not directory and self._last_opened_folder:
                        directory = self._last_opened_folder
                    
                    # 根据 target_type 选择创建文件还是文件夹
                    if target_type == 'folder':
                        r = self.file_manager.create_folder(target, directory=directory or None)
                    else:
                        # target_type 为 file
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
                
                # 修复：不要二次尝试全局搜索，避免误删同名文件
                # 如果没找到，直接给出明确提示
                if not r["success"]:
                    if search_dir:
                        r["message"] = f"在「{search_dir}」中没找到 '{target}' 哦~ 请确认文件名或打开正确的文件夹"
                    else:
                        r["message"] = f"没找到 '{target}' 哦。请先打开一个文件夹，或者说清楚文件位置~"

            elif action == "move":
                if not target:
                    r = {"success": False, "message": "请告诉我要移动的文件"}
                elif not destination:  # 修复 1：使用 destination
                    r = {"success": False, "message": "请告诉我目标位置"}
                else:
                    # 修复 1：使用关键字参数，更清晰
                    r = self.file_manager.move_file(name=target, target_dir=destination)

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

    def _try_direct_tool(self, text: str) -> Optional[str]:
        """三级意图识别漏斗：快速匹配 → 增强匹配 → 兜底返回 None"""
        
        # ========== 第 1 层：快捷命令匹配（<10ms）==========
        # 精确匹配高频命令，直接执行
        quick_commands = {
            "天气": lambda: self._weather_quick(text),
            "查天气": lambda: self._weather_quick(text),
            "系统": lambda: self._sysinfo_quick(),
            "IP": lambda: self._myip_quick(),
            "运势": lambda: self._fortune_quick(),
            "密码": lambda: self._password_quick(text),
            "语录": lambda: _quote(),
            "一言": lambda: _quote(),
        }
        
        for keyword, handler in quick_commands.items():
            if keyword in text:
                try:
                    result = handler()
                    if result and 'error' not in str(result).lower():
                        return result
                except Exception:
                    pass
        
        # ========== 第 2 层：增强关键词匹配（<50ms）==========
        # 扩展正则 + 同义词表，覆盖更多自然表达
        
        # 天气：支持更多自然表达
        weather_patterns = [
            r'([一-龥]{2,4})(?:的)?(?:天气 | 气温 | 温度 | 冷不冷 | 热不热 | 下雨 | 下雪 | 刮风 | 适不适合出门 | 要不要带伞)',
            r'(?:今天 | 明天 | 现在 | 外面)(?:是)?(?:什么)?(?:天气 | 情况)?(?:吗 | 呀 | 吗)?',
            r'(?:冷 | 热 | 暖和 | 凉快)',
            r'(?:查看 | 查询 | 看看 | 告诉我)?(?:一下)?(?:天气 | 气温 | 温度)',  # 新增：查看天气、查询天气等
        ]
        
        for pattern in weather_patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                if m.group(1):  # 有城市名
                    city = m.group(1)
                    if city not in ('今天', '明天', '后天', '昨天', '什么', '怎么', '外面', '现在'):
                        result = _weather(city)
                        return f"{result.get('city','')}天气:{result.get('weather','')},{result.get('temp','')}"
                else:  # 默认天津（用户所在地）
                    result = _weather('天津')
                    return f"{result.get('city','')}天气:{result.get('weather','')},{result.get('temp','')}"
        
        # 系统状态：扩展关键词
        if any(k in text for k in ['电脑状态', '系统状态', 'cpu', 'CPU', '内存', '性能', '电脑怎么样', '运行状态']):
            result = _sysinfo()
            if isinstance(result, dict) and 'error' not in result:
                return f"系统:{result.get('system','')}\\nCPU:{result.get('cpu','')}\\n内存:{result.get('memory','')}"
        
        # IP 查询：扩展关键词
        if any(k in text for k in ['我的 IP', 'IP 在哪', 'ip 地址', '外网', '公网 IP', 'IP 是多少', '网络地址']):
            result = _myip()
            if isinstance(result, dict) and 'error' not in result:
                return f"IP:{result.get('ip','')}\\n归属地:{result.get('country','')} {result.get('region','')} {result.get('city','')}"
        
        # 语录：扩展关键词
        if any(k in text for k in ['来句', '语录', '鸡汤', '一言', '名言', '金句', '励志', '鼓励']):
            return _quote()
        
        # 运势：扩展关键词
        if any(k in text for k in ['运势', '占卜', '运气', '抽签', '今天运气', '运气的怎么样', '吉利']):
            result = _fortune()
            if isinstance(result, dict):
                return f"今日运势:{result.get('level','')}\\n建议:{result.get('advice','')}"
        
        # 密码：扩展关键词
        if any(k in text for k in ['密码', '生成密码', '随机密码', '强密码', '复杂密码']):
            m = re.search(r'(\d+) 位', text)
            length = int(m.group(1)) if m else 16
            result = _password(length)
            return f"生成的密码 ({length} 位):{result.get('password','')}"
        
        # ========== 第 3 层：未匹配，返回 None 由 LLM 处理 ==========
        # 复杂表达、多意图、模糊意图交给 LLM
        return None
    
    # ========== 快捷命令处理器 ==========
    def _weather_quick(self, text: str) -> Optional[str]:
        """快速天气查询"""
        m = re.search(r'([一-龥]{2,4})', text)
        city = m.group(1) if m else '天津'
        if city in ('今天', '明天', '现在', '外面'):
            city = '天津'
        result = _weather(city)
        return f"{result.get('city','')}天气:{result.get('weather','')},{result.get('temp','')}"
    
    def _sysinfo_quick(self) -> str:
        """快速系统信息"""
        result = _sysinfo()
        if isinstance(result, dict) and 'error' not in result:
            return f"系统:{result.get('system','')}\\nCPU:{result.get('cpu','')}\\n内存:{result.get('memory','')}"
        return None
    
    def _myip_quick(self) -> str:
        """快速 IP 查询"""
        result = _myip()
        if isinstance(result, dict) and 'error' not in result:
            return f"IP:{result.get('ip','')}\\n归属地:{result.get('city','')}"
        return None
    
    def _fortune_quick(self) -> str:
        """快速运势查询"""
        result = _fortune()
        if isinstance(result, dict):
            return f"今日运势:{result.get('level','')}\\n建议:{result.get('advice','')}"
        return None
    
    def _password_quick(self, text: str) -> str:
        """快速密码生成"""
        m = re.search(r'(\d+) 位', text)
        length = int(m.group(1)) if m else 16
        result = _password(length)
        return f"生成的密码 ({length} 位):{result.get('password','')}"

    def _chat_with_llm(self, text):
        # 先试直接调工具
        tool_result = self._try_direct_tool(text)
        if tool_result:
            # 用 LLM 润色成自然语言
            # 注意：延迟添加消息，确保上下文一致性
            user_message = {"role": "user", "content": text}
            tool_message = {"role": "tool", "content": tool_result}
            
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
                # 成功后再添加消息到上下文
                self.conversation.append(user_message)
                self.conversation.append(tool_message)
                self.conversation.append({"role": "assistant", "content": cleaned})
                self.send_btn.setEnabled(True)
                self.send_btn.setText("🚀 发送")
            def on_error(err):
                # 错误时也给一个友好的回复
                self._hide_typing_indicator()  # 隐藏打字指示器
                error_msg = f"🦊 {tool_result}\n\n（小狐仙正在努力学习中...）"
                self._add_msg("assistant", error_msg)
                # 出错时也记录上下文
                self.conversation.append(user_message)
                self.conversation.append(tool_message)
                self.conversation.append({"role": "assistant", "content": error_msg})
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
        # 注意：先不 append user 消息，等成功后再添加，避免出错时上下文不一致
        user_message = {"role": "user", "content": text}
        
        def on_response(response):
            cleaned = response.strip()
            self._hide_typing_indicator()  # 隐藏打字指示器
            self._add_msg("assistant", cleaned)
            # 成功后再添加 user 和 assistant 消息到上下文
            self.conversation.append(user_message)
            self.conversation.append({"role": "assistant", "content": cleaned})
            self.send_btn.setEnabled(True)
            self.send_btn.setText("🚀 发送")

        def on_error(err):
            self._hide_typing_indicator()  # 隐藏打字指示器
            error_msg = "😅 小狐仙走神了... 试试直接命令我:\n" +\
                "• 打开 记事本\n• 创建 test.txt\n• 删除 file.txt"
            self._add_msg("assistant", error_msg)
            # 出错时也记录，但标记为错误回复
            self.conversation.append(user_message)
            self.conversation.append({"role": "assistant", "content": error_msg})
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
            
            # 智能上下文管理：确保 system prompt 始终保留
            # 保留 system prompt + 最近 9 条消息（避免 system prompt 被截断）
            system_prompt = self.conversation[0]  # 始终保留系统提示
            recent_messages = self.conversation[-9:] if len(self.conversation) > 10 else self.conversation[1:]
            recent = [system_prompt] + recent_messages
            
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

    # ---- 阻止回车关闭 + Escape 淡出 ----
    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            # 输入框的回车由 returnPressed 处理,不传播到 dialog
            if self.input_edit.hasFocus():
                event.accept()
                return
        if event.key() == Qt.Key_Escape:
            self._fade_out_close()
            event.accept()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event):
        if getattr(self, '_fade_out_completed', False):
            # 淡出已完成,执行真正的清理
            self._cleanup()
            super().closeEvent(event)
            return
        # 拦截关闭,改为淡出
        event.ignore()
        self._fade_out_close()

    def _fade_out_close(self):
        if getattr(self, '_fade_closing', False):
            return
        self._fade_closing = True
        self._fade_out_timer = QTimer(self)
        self._fade_out_timer.timeout.connect(self._fade_out_step)
        self._fade_out_opacity = self.windowOpacity()
        self._fade_out_timer.start(16)

    def _fade_out_step(self):
        self._fade_out_opacity = max(0, self._fade_out_opacity - 0.1)
        self.setWindowOpacity(self._fade_out_opacity)
        if self._fade_out_opacity <= 0:
            self._fade_out_timer.stop()
            self._fade_out_completed = True
            # 直接调用 QDialog.close, bypass 拦截
            QDialog.close(self)

    def _cleanup(self):
        """关闭前的资源清理"""
        self._key_thread_running = False
        
        # 清理 QThread 线程
        _known_threads = ['llm_thread', 'cmd_thread']
        for name in _known_threads:
            attr = getattr(self, name, None)
            if attr is not None and isinstance(attr, QThread) and attr.isRunning():
                attr.quit()
                attr.wait(2000)
        
        # 清理后台线程 (threading.Thread)
        # 等待所有后台线程自然结束 (daemon 线程会在程序退出时自动终止)
        for thread in getattr(self, '_background_threads', []):
            if thread.is_alive():
                # daemon 线程不需要显式 join，等待其自然结束
                pass
        # 清空线程列表
        self._background_threads = []


# ======================================================================
# 功能概览 (Markdown + 精致关闭)
# ======================================================================
class FeatureOverview(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("\U0001f4cb 功能概览")
        self.setFixedSize(480, 620)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # 淡入动画
        self._opacity = 0.0
        self._fade_in_timer = QTimer(self)
        self._fade_in_timer.timeout.connect(self._fade_in_step)

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
        outer_layout.setContentsMargins(20, 16, 20, 12)
        outer_layout.setSpacing(8)

        # ---- 顶栏：标题 + 关闭按钮（右上角） ----
        top_frame = QFrame()
        top_frame.setStyleSheet("background: transparent;")
        top = QHBoxLayout(top_frame)
        top.setContentsMargins(4, 0, 4, 0)

        title = QLabel("\U0001f98a 仙狐功能一览")
        title.setFont(QFont("Microsoft YaHei UI", 17, QFont.Bold))
        title.setStyleSheet(f"color: {FOX_ORANGE}; background: transparent;")
        top.addWidget(title)

        top.addStretch()

        close_btn = QPushButton("\u2715")
        close_btn.setFixedSize(30, 30)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setToolTip("关闭")
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,180,120,0.25);
                color: {FOX_TEXT};
                border: 1px solid rgba(232,196,160,0.3);
                border-radius: 15px;
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: rgba(255,90,70,0.35);
                color: #d44;
                border-color: rgba(255,90,70,0.5);
            }}
            QPushButton:pressed {{
                background: rgba(255,60,40,0.5);
            }}
        """)
        close_btn.clicked.connect(self._fade_out_close)
        top.addWidget(close_btn)

        outer_layout.addWidget(top_frame)

        # ---- Markdown 内容区 ----
        from PyQt5.QtWidgets import QTextEdit
        md_view = QTextEdit()
        md_view.setReadOnly(True)
        md_view.setFrameShape(QFrame.NoFrame)
        md_view.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        md_view.setStyleSheet(f"""
            QTextEdit {{
                background: rgba(255,248,240,0.35);
                border: none;
                border-radius: 12px;
                padding: 16px 20px;
                color: {FOX_TEXT};
                font-size: 13px;
            }}
            QScrollBar:vertical {{
                background: rgba(0,0,0,0.03);
                width: 6px;
                border-radius: 3px;
            }}
            QScrollBar::handle:vertical {{
                background: rgba(255,140,66,0.3);
                border-radius: 3px;
                min-height: 30px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)

        md_content = f"""## 💬 智能对话

和 **仙狐** 自由聊天，她认识所有工具。
说 `北京天气`、`查IP`、`今日运势` 自动调用。

---

## 🛠️ 实用工具

| 功能 | 触发词 |
|------|--------|
| 🌤 天气查询 | 「`北京天气`」「`天津冷不冷`」 |
| 📊 系统状态 | 「`电脑状态`」「`内存`」 |
| 📍 IP 查询 | 「`我的IP`」「`外网地址`」 |
| 🎲 今日运势 | 「`今天运势`」「`抽签`」 |
| 💬 每日一言 | 「`来句鸡汤`」「`名言`」 |
| 🔐 密码生成 | 「`生成密码`」 |
| ⏰ 定时提醒 | 「`提醒我10分钟后喝水`」 |

---

## 📁 文件 & 程序

| 操作 | 示例 |
|------|------|
| 打开文件夹 | 「`打开下载`」「`打开D盘`」 |
| 打开程序 | 「`打开计算器`」「`打开微信`」 |
| 创建文件 | 「`创建 test.txt`」 |
| 删除文件 | 「`删除 temp.log`」 |
| 移动文件 | 「`把a.txt移动到桌面`」 |

---

## 🗣️ 语音

点击输入框左边的 **🎤** 按钮进入语音模式，长按 **T 键** 说话。

---

## 🎨 操作提示

- **右键** 点击我打开菜单
- **左键拖拽** 移动窗口
- **右下角** 拖拽缩放
"""

        md_view.setMarkdown(md_content)
        outer_layout.addWidget(md_view, stretch=1)

        # ---- 底部关闭按钮 ----
        close_all = QPushButton("\U0001f98a 知道啦")
        close_all.setFixedHeight(42)
        close_all.setCursor(Qt.PointingHandCursor)
        close_all.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {FOX_ORANGE}, stop:1 {FOX_PEACH});
                color: white;
                border: none;
                border-radius: 12px;
                font-weight: bold;
                font-size: 14px;
                font-family: 'Microsoft YaHei UI', 'Microsoft YaHei', sans-serif;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {FOX_BTN_HOVER}, stop:1 {FOX_ACCENT});
            }}
            QPushButton:pressed {{
                background: {FOX_BTN_HOVER};
            }}
        """)
        close_all.clicked.connect(self._fade_out_close)
        outer_layout.addWidget(close_all)

        # ---- 拖拽 ----
        self._dragging = False
        self._drag_start = None

        # 启动淡入
        self._fade_in_timer.start(16)

    # ---- 淡入 ----
    def _fade_in_step(self):
        self._opacity = min(1.0, self._opacity + 0.08)
        self.setWindowOpacity(self._opacity)
        if self._opacity >= 1.0:
            self._fade_in_timer.stop()

    # ---- 淡出关闭 ----
    def _fade_out_close(self):
        self._fade_in_timer.stop()
        self._fade_out_timer = QTimer(self)
        self._fade_out_timer.timeout.connect(self._fade_out_step)
        self._fade_out_opacity = self.windowOpacity()
        self._fade_out_timer.start(16)

    def _fade_out_step(self):
        self._fade_out_opacity = max(0, self._fade_out_opacity - 0.1)
        self.setWindowOpacity(self._fade_out_opacity)
        if self._fade_out_opacity <= 0:
            self._fade_out_timer.stop()
            self.close()

    # ---- 拖拽 ----
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._drag_start = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._dragging:
            self.move(event.globalPos() - self._drag_start)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = False
            event.accept()
        super().mouseReleaseEvent(event)

    # ---- 支持 Alt+F4 / 系统关闭淡出 ----
    def closeEvent(self, event):
        if getattr(self, '_fade_out_opacity', 1.0) <= 0:
            super().closeEvent(event)
            return
        event.ignore()
        self._fade_out_close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._fade_out_close()
            event.accept()
            return
        super().keyPressEvent(event)


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

input("按回车键退出...")