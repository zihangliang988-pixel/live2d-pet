#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
语音处理模块 - 语音转文字和文字转语音

常见安装问题：
  pip install pyaudio 失败？试试：
    pip install pipwin
    pipwin install pyaudio
  或直接安装：https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio
"""

import speech_recognition as sr
import os
import sys
from typing import Optional


# 运行状态：记录麦克风不可用的原因，供 UI 层提示
MICROPHONE_ERROR = None


class VoiceProcessor:
    def __init__(self, language: str = "zh-CN"):
        global MICROPHONE_ERROR
        self.language = language
        self.recognizer = sr.Recognizer()
        self.microphone = None
        self._microphone_error = None
        self._init_microphone()

    def _init_microphone(self):
        """初始化麦克风，失败时记录详细原因"""
        global MICROPHONE_ERROR
        try:
            self.microphone = sr.Microphone()
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            MICROPHONE_ERROR = None
            self._microphone_error = None
        except OSError as e:
            msg = "找不到麦克风设备，请检查麦克风是否已连接"
            MICROPHONE_ERROR = msg
            self._microphone_error = msg
            print(f"[Voice] {msg}")
        except AttributeError as e:
            msg = ("语音识别库不完整，可能缺少 pyaudio。\n"
                   "安装方式：pip install pyaudio\n"
                   "安装失败可尝试：pip install pipwin && pipwin install pyaudio")
            MICROPHONE_ERROR = msg
            self._microphone_error = msg
            print(f"[Voice] {msg}")
        except Exception as e:
            msg = f"麦克风初始化失败：{str(e)[:80]}"
            MICROPHONE_ERROR = msg
            self._microphone_error = msg
            print(f"[Voice] {msg}")

    def is_available(self) -> tuple:
        """检查语音功能是否可用，返回 (ok: bool, reason: str|None)"""
        if not self.microphone:
            return (False, self._microphone_error or "麦克风不可用")
        return (True, None)

    def listen(self, timeout: int = 5) -> Optional[str]:
        """
        监听语音输入并转换为文字

        Args:
            timeout: 超时时间（秒）

        Returns:
            识别的文字，失败返回 None
        """
        ok, err = self.is_available()
        if not ok:
            print(f"[Voice] {err}")
            return None

        try:
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.3)
                audio = self.recognizer.listen(
                    source, timeout=timeout, phrase_time_limit=10
                )

            # 优先 Google（需要网络，中文识别好）
            try:
                text = self.recognizer.recognize_google(audio, language=self.language)
                return text
            except sr.UnknownValueError:
                return None
            except sr.RequestError:
                # Google 不可用时尝试百度
                # （百度需要 API key，跳过）
                return None

        except sr.WaitTimeoutError:
            return None
        except Exception as e:
            print(f"[Voice] 识别异常：{e}")
            return None

    def speak(self, text: str, rate: int = 150):
        """
        文字转语音（使用系统 TTS）

        Args:
            text: 要朗读的文字
            rate: 语速（100-300）
        """
        try:
            if sys.platform == 'win32':
                try:
                    import win32com.client
                    speaker = win32com.client.Dispatch("SAPI.SpVoice")
                    speaker.Speak(text)
                    return
                except ImportError:
                    pass

            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty('rate', rate)
            engine.say(text)
            engine.runAndWait()

        except Exception as e:
            print(f"[Voice] TTS 失败：{e}")

    def test_microphone(self) -> bool:
        """测试麦克风是否正常"""
        ok, err = self.is_available()
        if not ok:
            return False
        try:
            text = self.listen(timeout=3)
            return text is not None
        except Exception:
            return False


# 便捷函数：供 UI 层调用，获取语音不可用的友好提示
def get_microphone_help_text() -> Optional[str]:
    """返回麦克风问题的用户友好提示（用于弹窗展示）"""
    if MICROPHONE_ERROR:
        return (
            "🎤 语音功能暂不可用\n\n"
            f"原因：{MICROPHONE_ERROR}\n\n"
            "💡 你可以：\n"
            "1. 继续使用文字输入聊天\n"
            "2. 安装 pyaudio 后重试：\n"
            "   pip install pyaudio\n"
            "3. 如果安装失败，试试：\n"
            "   pip install pipwin\n"
            "   pipwin install pyaudio"
        )
    return None
