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
            
            import re
            import json as json_mod
            
            # 尝试多种解析方式
            parsed = None
            
            # 方式1：直接从 markdown 代码块提取
            block = re.search(r'```(?:json)?\s*\n?([\s\S]*?)```', content)
            if block:
                try:
                    parsed = json_mod.loads(block.group(1).strip())
                except Exception:
                    pass
            
            # 方式2：提取第一个 {…} 对象
            if not parsed:
                brace = re.search(r'\{[^{}]*"action"[^{}]*\}', content)
                if brace:
                    try:
                        parsed = json_mod.loads(brace.group())
                    except Exception:
                        pass
            
            if parsed and 'action' in parsed:
                result = {
                    "success": parsed['action'] != 'unknown',
                    "action": parsed['action'],
                    "target": parsed.get('target'),
                    "destination": parsed.get('destination'),
                    "directory": parsed.get('directory'),
                    "content": parsed.get('content'),
                    "message": parsed.get('message', '')
                }
                print(f"[LLM解析] {result}")
                return result

            # LLM没返回JSON → 回退规则匹配
            return self._fallback_parse(text)

        except Exception as e:
            print(f"❌ 大模型解析失败：{e}")
            return self._fallback_parse(text)
    
    def _fallback_parse(self, text: str) -> dict:
        """回退到规则匹配（支持复杂中文指令）"""
        import re

        # ---- 模式1：在「目录」里面「动作」「目标」 ----
        m = re.search(r'在\s*([\u4e00-\u9fa5\w\\/]+?)\s*(?:里|里面|目录|文件夹)?\s*'
                      r'(打开|创建|新建|删除|删掉|查看|看看|移动)\s*'
                      r'(?:命名为?|一个)?\s*([\u4e00-\u9fa5\w.\\/]+?)?(?:的)?'
                      r'(?:文件|文件夹)?\s*$', text)
        if m:
            directory = m.group(1).strip()
            action_cn = m.group(2)
            target = m.group(3).strip() if m.group(3) else ''
            action_map = {'打开': 'open', '创建': 'create', '新建': 'create',
                         '删除': 'delete', '删掉': 'delete',
                         '查看': 'view', '看看': 'view', '移动': 'move'}
            action_en = action_map.get(action_cn, 'open')
            if action_en == 'open':
                return {"success": True, "action": "open", "target": directory,
                        "directory": None, "destination": None, "content": None,
                        "message": f"正在打开{directory}..."}
            if action_en == 'create' and target:
                return {"success": True, "action": "create", "target": target,
                        "directory": directory, "destination": None, "content": None,
                        "message": f"在{directory}中创建{target}"}
            if action_en == 'create' and not target:
                return {"success": True, "action": "create", "target": directory,
                        "directory": None, "destination": None, "content": None,
                        "message": f"正在创建{directory}..."}

        # ---- 模式2：打开 ----
        for kw in ["打开", "进入", "启动", "运行"]:
            if kw in text:
                target = text.replace(kw, "").strip()
                if target:
                    return {"success": True, "action": "open", "target": target,
                            "directory": None, "destination": None, "content": None,
                            "message": f"正在打开{target}..."}

        # ---- 模式3：创建/新建 ----
        for kw in ["创建", "新建"]:
            if kw in text:
                target = text.replace(kw, "").strip()
                target = re.sub(r'^(?:命名为?|一个)\s*', '', target)
                if target:
                    return {"success": True, "action": "create", "target": target,
                            "directory": None, "destination": None, "content": None,
                            "message": f"已创建{target}"}

        # ---- 模式4：删除 ----
        for kw in ["删除", "删掉"]:
            if kw in text:
                target = text.replace(kw, "").strip()
                if target:
                    return {"success": True, "action": "delete", "target": target,
                            "directory": None, "destination": None, "content": None,
                            "message": f"已删除{target}"}

        # ---- 模式5：移动 ----
        if "移动" in text and "到" in text:
            parts = text.split("移动", 1)[1].split("到", 1)
            if len(parts) == 2:
                return {"success": True, "action": "move",
                        "target": parts[0].strip(), "destination": parts[1].strip(),
                        "directory": None, "content": None,
                        "message": "已移动文件"}

        # ---- 模式6：查看 ----
        for kw in ["查看", "看看"]:
            if kw in text:
                target = text.replace(kw, "").strip()
                if target:
                    return {"success": True, "action": "view", "target": target,
                            "directory": None, "destination": None, "content": None,
                            "message": f"正在查看{target}..."}

        return {"success": False, "action": "unknown",
                "target": None, "directory": None,
                "destination": None, "content": None,
                "message": "我不太明白，请试试：打开、创建、删除、移动、查看"}


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
