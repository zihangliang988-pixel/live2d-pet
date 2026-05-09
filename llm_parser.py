#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
大模型命令解析器 - 支持 Ollama 本地模型
"""

import os
import sys

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

JSON 格式：
{
    "action": "open|create|delete|move|view|unknown",
    "target": "操作对象（文件名或程序名）",
    "destination": "目标路径（仅 move 操作需要）",
    "message": "返回给用户的友好提示"
}

示例：
用户说"打开记事本" → {"action": "open", "target": "记事本", "destination": null, "message": "正在打开记事本..."}
用户说"创建 test.txt" → {"action": "create", "target": "test.txt", "destination": null, "message": "已创建 test.txt"}
用户说"删除 file.txt" → {"action": "delete", "target": "file.txt", "destination": null, "message": "已删除 file.txt"}
用户说"移动 a.txt 到 D:/backup" → {"action": "move", "target": "a.txt", "destination": "D:/backup", "message": "已移动文件"}
用户说"查看图片.png" → {"action": "view", "target": "图片.png", "destination": null, "message": "正在查看..."}

支持的程序名：记事本、计算器、Chrome、Edge、微信、QQ、游戏等
支持的文件操作：.txt, .doc, .docx, .pdf, .jpg, .png, .mp4, .mp3 等

如果无法理解，返回：{"action": "unknown", "target": null, "destination": null, "message": "我不太明白，请试试：打开、创建、删除、移动、查看"}"""
    
    def _init_ollama(self):
        """初始化 Ollama"""
        try:
            import ollama
            self.ollama = ollama
            print("✅ Ollama 连接成功")
        except ImportError:
            print("❌ ollama 库未安装，请运行：pip install ollama")
            self.ollama = None
        except Exception as e:
            print(f"❌ Ollama 初始化失败：{e}")
            self.ollama = None
    
    def parse_command(self, text: str) -> dict:
        """解析用户命令"""
        if not self.ollama:
            # 回退到规则匹配
            return self._fallback_parse(text)
        
        try:
            # 调用大模型
            response = self.ollama.chat(
                model=self.model_name,
                messages=[
                    {'role': 'system', 'content': self.system_prompt},
                    {'role': 'user', 'content': text}
                ],
                stream=False,
                options={"temperature": 0.3}  # 降低随机性
            )
            
            content = response['message']['content']
            
            # 提取 JSON（可能包含 markdown 代码块）
            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                content = json_match.group()
            
            # 解析 JSON
            import json
            result = json.loads(content)
            
            # 验证结果
            if 'action' not in result:
                return {"success": False, "message": "解析失败"}
            
            return {
                "success": result['action'] != 'unknown',
                "action": result['action'],
                "target": result.get('target'),
                "destination": result.get('destination'),
                "directory": result.get('directory'),  # 新增：指定目录
                "content": result.get('content'),      # 新增：文件内容
                "message": result.get('message', '')
            }
            
        except Exception as e:
            print(f"❌ 大模型解析失败：{e}")
            return self._fallback_parse(text)
    
    def _fallback_parse(self, text: str) -> dict:
        """回退到规则匹配"""
        text_lower = text.lower()
        
        # 打开
        for kw in ["打开", "进入", "启动", "运行"]:
            if kw in text_lower:
                target = text.replace(kw, "").strip()
                if target:
                    return {
                        "success": True,
                        "action": "open",
                        "target": target,
                        "message": f"正在打开 {target}..."
                    }
        
        # 创建
        for kw in ["创建", "新建"]:
            if kw in text_lower:
                target = text.replace(kw, "").strip()
                if target:
                    return {
                        "success": True,
                        "action": "create",
                        "target": target,
                        "message": f"已创建 {target}"
                    }
        
        # 删除
        for kw in ["删除", "删掉"]:
            if kw in text_lower:
                target = text.replace(kw, "").strip()
                if target:
                    return {
                        "success": True,
                        "action": "delete",
                        "target": target,
                        "message": f"已删除 {target}"
                    }
        
        # 移动
        if "移动" in text_lower and "到" in text_lower:
            parts = text.split("移动", 1)[1].split("到", 1)
            if len(parts) == 2:
                return {
                    "success": True,
                    "action": "move",
                    "target": parts[0].strip(),
                    "destination": parts[1].strip(),
                    "message": "已移动文件"
                }
        
        # 查看
        for kw in ["查看", "看看"]:
            if kw in text_lower:
                target = text.replace(kw, "").strip()
                if target:
                    return {
                        "success": True,
                        "action": "view",
                        "target": target,
                        "message": "正在查看..."
                    }
        
        return {
            "success": False,
            "action": "unknown",
            "target": None,
            "message": "我不太明白，请试试：打开、创建、删除、移动、查看"
        }


# 测试
if __name__ == "__main__":
    parser = LLMCommandParser()
    
    test_commands = [
        "打开记事本",
        "创建 test.txt",
        "删除 file.txt",
        "移动 a.txt 到 D:/backup",
        "查看图片.png"
    ]
    
    print("\n测试命令解析：\n")
    for cmd in test_commands:
        print(f"输入：{cmd}")
        result = parser.parse_command(cmd)
        print(f"结果：{result}\n")
