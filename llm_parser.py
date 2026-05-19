#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
大模型命令解析器 - 支持 Ollama 本地模型
"""

import os
import sys
import re

# ============================================================
# [MOD 2026-05-19] 命令预处理 - 清洗用户输入，提高解析准确率
# 去除废话词、转换常见句式，让 LLM/正则看到干净的命令
# 如果要回滚，删除本函数 + pet.py 中调用它的那行即可
# ============================================================
def preprocess_input(text: str) -> str:
    """
    把日常口语清理成 LLM 好处理的形式。
    例如："帮助我打开丑橘这个文件夹" → "打开丑橘文件夹"
    """
    # 1. 去除开头整段废话：帮我/请帮我/帮助我/帮我一下/麻烦你帮我 等
    # === [FIX] 使用字符串方法代替正则，避免转义问题 ===
    prefixes = ['帮我', '请帮我', '帮助我', '麻烦你', '麻烦你了', '帮我一下', '帮我个忙']
    for prefix in prefixes:
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
            break
    
    # 2. 去除句中残余的敬语词：一下、给我、帮我
    text = text.replace('帮我', '').replace('给我', '').replace('一下', '')
    
    # 3. === [FIX] 只去除开头的"这个/那个"，保留句中的（如"在这里"）===
    # 只删除开头的"这个 XX"、"那个 XX"（XX 是名词）
    if text.startswith('这个'):
        text = text[2:].strip()
    elif text.startswith('那个'):
        text = text[2:].strip()
    
    # 4. 去除结尾的客气词
    suffixes = ['好吗', '好嘛', '行吗', '谢谢', '谢谢你', '谢谢啦', '可以吗', '行不行']
    for suffix in suffixes:
        if text.endswith(suffix):
            text = text[:-len(suffix)].strip()
            break
    
    # 5. 处理"把 XX 打开/删除/移动"句式 → "打开/删除/移动 XX"
    # 使用正则
    text = re.sub(r'把\s*(\S+)\s*(打开 | 删除 | 删掉 | 移动 | 创建 | 新建)', r'\2 \1', text)
    
    # 6. 处理"给 XX"句式 → "打开 XX"
    text = re.sub(r'给\s*我\s*(打开 | 删除 | 删掉 | 看看 | 查看)', r'\1', text)
    
    # 7. === [FIX] 将"这里/这里面/这里头"等转换为"当前文件夹" ===
    # 使用简单字符串替换，避免正则匹配问题
    # === [FIX] 注意顺序：先替换长的，再替换短的 ===
    replacements = [
        ('在桌宠文件夹这里', '在当前文件夹'),
        ('在桌宠文件夹里面', '在当前文件夹'),
        ('在桌宠文件夹这儿', '在当前文件夹'),
        ('在这里', '在当前文件夹'),
        ('在里面', '在当前文件夹'),
        ('在这儿', '在当前文件夹'),
        ('这里面', '当前文件夹'),  # 放在"这里"和"里面"之前
        ('这里头', '当前文件夹'),
        ('这儿的里面', '当前文件夹'),
        ('这里', '当前文件夹'),
        ('里面', '当前文件夹'),
        ('这儿', '当前文件夹'),
    ]
    for old, new in replacements:
        text = text.replace(old, new)
    
    # 8. 多个空格归一
    text = ' '.join(text.split())
    
    return text


class LLMCommandParser:
    """基于大模型的命令解析器"""

    def __init__(self, model_name="qwen2.5:7b"):
        self.model_name = model_name
        self.ollama = None
        self._init_ollama()

        # 系统提示词
        self.system_prompt = """你是一个桌宠助手，专门帮助用户管理文件和打开程序。

你的任务是将用户的自然语言指令转换为具体的操作。
只返回 JSON 格式，不要其他内容。

JSON 格式:
{
    "action": "open|create|delete|move|view|unknown",
    "target": "操作对象 (文件名或程序名)",
    "target_type": "file|folder|program|unknown",
    "destination": "目标路径 (仅 move 操作需要)",
    "directory": "操作所在目录 (如"这个文件夹"、"这里"、"这里面"指最近打开的文件夹)",
    "message": "返回给用户的友好提示"
}

类型说明:
- file: 文件 (如 test.txt, 图片.png)
- folder: 文件夹/目录 (如 丑橘，文档)
- program: 应用程序 (如 记事本，计算器)
- unknown: 无法确定类型

示例:
用户说"打开记事本" → {"action": "open", "target": "记事本", "target_type": "program", "destination": null, "directory": null, "message": "正在打开记事本..."}
用户说"打开丑橘文件夹" → {"action": "open", "target": "丑橘", "target_type": "folder", "destination": null, "directory": null, "message": "正在打开丑橘文件夹..."}
用户说"打开丑橘" → {"action": "open", "target": "丑橘", "target_type": "folder", "destination": null, "directory": null, "message": "正在打开丑橘文件夹..."}
用户说"创建 test.txt" → {"action": "create", "target": "test.txt", "target_type": "file", "destination": null, "directory": null, "message": "已创建 test.txt"}
用户说"删除 file.txt" → {"action": "delete", "target": "file.txt", "target_type": "file", "destination": null, "directory": null, "message": "已删除 file.txt"}
用户说"删除这个文件夹里面的大愁居文件" → {"action": "delete", "target": "大愁居", "target_type": "file", "destination": null, "directory": "这个文件夹", "message": "已删除大愁居文件"}
用户说"删除这个文件夹里面的大愁居" → {"action": "delete", "target": "大愁居", "target_type": "file", "destination": null, "directory": "这个文件夹", "message": "已删除大愁居"}
用户说"移动 a.txt 到 D:/backup" → {"action": "move", "target": "a.txt", "target_type": "file", "destination": "D:/backup", "directory": null, "message": "已移动文件"}
用户说"查看图片.png" → {"action": "view", "target": "图片.png", "target_type": "file", "destination": null, "directory": null, "message": "正在查看..."}

=== [FIX] 新增上下文引用示例 ===
用户说"在这里创建 test.txt" → {"action": "create", "target": "test.txt", "target_type": "file", "destination": null, "directory": "这里", "message": "已创建 test.txt"}
用户说"在里面创建 test.py" → {"action": "create", "target": "test.py", "target_type": "file", "destination": null, "directory": "这里面", "message": "已创建 test.py"}
用户说"在桌宠文件夹这里创建 test.txt" → {"action": "create", "target": "test.txt", "target_type": "file", "destination": null, "directory": "这里", "message": "已创建 test.txt"}
用户说"当前目录创建 data.json" → {"action": "create", "target": "data.json", "target_type": "file", "destination": null, "directory": "当前目录", "message": "已创建 data.json"}
用户说"这里面删除 old.txt" → {"action": "delete", "target": "old.txt", "target_type": "file", "destination": null, "directory": "这里面", "message": "已删除 old.txt"}

支持的程序名：记事本、计算器、Chrome、Edge、微信、QQ、游戏等
支持的文件操作:.txt, .doc, .docx, .pdf, .jpg, .png, .mp4, .mp3 等

注意:
1. 如果用户说"这个文件夹"、"当前文件夹"、"刚才打开的文件夹"、"这里"、"这里面"、"这儿"、"当前目录"等，请在 directory 字段中保留原文
2. 如果目标名称包含"文件夹"、"目录"字样，target_type 应为 folder
3. 如果目标名称包含文件扩展名 (如 .txt, .png),target_type 应为 file
4. 如果目标是常见程序名，target_type 应为 program

如果无法理解，返回:{"action": "unknown", "target": null, "target_type": "unknown", "destination": null, "directory": null, "message": "我不太明白，请试试：打开、创建、删除、移动、查看"}"""

    def _init_ollama(self):
        """初始化 Ollama"""
        try:
            import ollama
            self.ollama = ollama
            print(f"[INFO] Ollama 已连接，模型：{self.model_name}")
        except Exception as e:
            print(f"[ERROR] Ollama 连接失败：{e}")
            print("[INFO] 请确保 Ollama 服务已启动：ollama serve")
            self.ollama = None
