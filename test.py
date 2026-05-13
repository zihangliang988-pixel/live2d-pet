#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试脚本 - 测试各个功能模块
"""

import os
import sys

# 确保在当前目录运行
os.chdir(os.path.dirname(os.path.abspath(__file__)))


def test_file_manager():
    """测试文件管理器"""
    print("\n" + "=" * 50)
    print("📁 测试文件管理器")
    print("=" * 50)
    
    from file_manager import FileManager
    fm = FileManager()
    
    # 测试创建文件
    print("\n[测试 1] 创建文件")
    result = fm.create_file("test.txt", "Hello, 桌宠！")
    print(f"结果：{result}")
    
    # 测试查看文件
    print("\n[测试 2] 查看文件")
    result = fm.view_file("test.txt")
    print(f"结果：{result}")
    
    # 测试列出文件
    print("\n[测试 3] 列出文件")
    result = fm.list_files()
    print(f"结果：找到 {result.get('count', 0)} 个文件")
    
    # 测试删除文件（不实际执行）
    print("\n[测试 4] 查找文件")
    result = fm._find_file("test.txt")
    print(f"结果：{result}")
    
    print("\n✅ 文件管理器测试完成")


def test_voice():
    """测试语音模块"""
    print("\n" + "=" * 50)
    print("🎤 测试语音模块")
    print("=" * 50)
    
    from voice import VoiceProcessor
    voice = VoiceProcessor()
    
    # 测试麦克风
    print("\n[测试] 麦克风测试")
    if voice.test_microphone():
        print("✅ 麦克风测试通过")
    else:
        print("⚠️ 麦克风测试失败（可以跳过）")
    
    # 测试语音播放
    print("\n[测试] 语音播放测试")
    voice.speak("你好，我是桌宠助手")
    
    print("\n✅ 语音模块测试完成")


def test_command_parsing():
    """测试命令解析"""
    print("\n" + "=" * 50)
    print("📝 测试命令解析")
    print("=" * 50)
    
    from pet import PetDialog
    from PyQt5.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    dialog = PetDialog()
    
    test_commands = [
        "打开 记事本",
        "创建 test2.txt",
        "查看 test.txt",
        "删除 test.txt",
    ]
    
    for cmd in test_commands:
        print(f"\n[测试] 命令：{cmd}")
        result = dialog._parse_and_execute(cmd)
        print(f"结果：{result}")
    
    print("\n✅ 命令解析测试完成")


def main():
    """运行所有测试"""
    print("\n" + "=" * 50)
    print("🐾 桌宠助手 - 功能测试")
    print("=" * 50)
    
    # 测试文件管理器
    test_file_manager()
    
    # 测试语音模块
    try:
        test_voice()
    except Exception as e:
        print(f"\n⚠️ 语音测试跳过：{e}")
    
    # 测试命令解析
    try:
        test_command_parsing()
    except Exception as e:
        print(f"\n⚠️ 命令解析测试跳过：{e}")
    
    print("\n" + "=" * 50)
    print("🎉 所有测试完成！")
    print("=" * 50)


if __name__ == "__main__":
    main()
