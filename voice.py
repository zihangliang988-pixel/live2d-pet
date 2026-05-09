#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
语音处理模块 - 语音转文字和文字转语音
"""

import speech_recognition as sr
import os
import sys
from typing import Optional


class VoiceProcessor:
    def __init__(self, language: str = "zh-CN"):
        self.language = language
        self.recognizer = sr.Recognizer()
        self.microphone = None
        self._init_microphone()
    
    def _init_microphone(self):
        """初始化麦克风"""
        try:
            self.microphone = sr.Microphone()
            # 调整灵敏度
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
            print("✅ 麦克风已就绪")
        except Exception as e:
            print(f"⚠️ 麦克风初始化失败：{e}")
            print("💡 提示：如果 pyaudio 安装失败，可以跳过语音识别功能")
            print("   桌宠仍可使用文字输入和 LLM 命令理解")
            self.microphone = None
    
    def listen(self, timeout: int = 5) -> Optional[str]:
        """
        监听语音输入并转换为文字
        
        Args:
            timeout: 超时时间（秒）
        
        Returns:
            识别的文字，失败返回 None
        """
        if not self.microphone:
            print("⚠️ 麦克风未就绪")
            return None
        
        try:
            print("🎤 正在监听...（说'打开'、'创建'、'删除'等命令）")
            
            with self.microphone as source:
                # 监听语音
                audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=10)
            
            print("🔄 正在识别...")
            
            # 尝试使用 Google 语音识别（需要网络）
            try:
                text = self.recognizer.recognize_google(audio, language=self.language)
                print(f"✅ 识别成功：{text}")
                return text
            except sr.UnknownValueError:
                print("❌ 无法识别语音")
                return None
            except sr.RequestError as e:
                print(f"❌ Google API 错误：{e}")
                return None
        
        except sr.WaitTimeoutError:
            print("⏱️ 超时，未检测到语音")
            return None
        except sr.UnknownValueError:
            print("❌ 无法识别语音内容")
            return None
        except Exception as e:
            print(f"❌ 语音识别错误：{e}")
            return None
    
    def speak(self, text: str, rate: int = 150):
        """
        文字转语音（使用系统 TTS）
        
        Args:
            text: 要朗读的文字
            rate: 语速（100-300）
        """
        try:
            # Windows 系统 TTS（推荐）
            if sys.platform == 'win32':
                try:
                    import win32com.client
                    speaker = win32com.client.Dispatch("SAPI.SpVoice")
                    speaker.Speak(text)
                    return
                except ImportError:
                    # 如果 win32com 不可用，使用 pyttsx3
                    pass
            
            # 使用 pyttsx3（跨平台，离线可用）
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty('rate', rate)
            engine.say(text)
            engine.runAndWait()
            
        except Exception as e:
            print(f"❌ 语音播放失败：{e}")
            print(f"🔊 {text}")
    
    def test_microphone(self) -> bool:
        """测试麦克风是否正常"""
        if not self.microphone:
            return False
        
        try:
            print("🎤 请说话测试麦克风...")
            text = self.listen(timeout=3)
            if text:
                print(f"✅ 识别成功：{text}")
                return True
            else:
                print("❌ 未检测到语音")
                return False
        except Exception as e:
            print(f"❌ 测试失败：{e}")
            return False
