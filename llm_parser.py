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
    "target_type": "file|folder|program|unknown",
    "destination": "目标路径（仅 move 操作需要）",
    "directory": "操作所在目录（如"这个文件夹"指最近打开的文件夹）",
    "message": "返回给用户的友好提示"
}

类型说明：
- file: 文件（如 test.txt, 图片.png）
- folder: 文件夹/目录（如 丑橘, 文档）
- program: 应用程序（如 记事本, 计算器）
- unknown: 无法确定类型

示例：
用户说"打开记事本" → {"action": "open", "target": "记事本", "target_type": "program", "destination": null, "directory": null, "message": "正在打开记事本..."}
用户说"打开丑橘文件夹" → {"action": "open", "target": "丑橘", "target_type": "folder", "destination": null, "directory": null, "message": "正在打开丑橘文件夹..."}
用户说"打开丑橘" → {"action": "open", "target": "丑橘", "target_type": "folder", "destination": null, "directory": null, "message": "正在打开丑橘文件夹..."}
用户说"创建 test.txt" → {"action": "create", "target": "test.txt", "target_type": "file", "destination": null, "directory": null, "message": "已创建 test.txt"}
用户说"删除 file.txt" → {"action": "delete", "target": "file.txt", "target_type": "file", "destination": null, "directory": null, "message": "已删除 file.txt"}
用户说"删除这个文件夹里面的大愁居文件" → {"action": "delete", "target": "大愁居", "target_type": "file", "destination": null, "directory": "这个文件夹", "message": "已删除大愁居文件"}
用户说"删除这个文件夹里面的大愁居" → {"action": "delete", "target": "大愁居", "target_type": "file", "destination": null, "directory": "这个文件夹", "message": "已删除大愁居"}
用户说"移动 a.txt 到 D:/backup" → {"action": "move", "target": "a.txt", "target_type": "file", "destination": "D:/backup", "directory": null, "message": "已移动文件"}
用户说"查看图片.png" → {"action": "view", "target": "图片.png", "target_type": "file", "destination": null, "directory": null, "message": "正在查看..."}

支持的程序名：记事本、计算器、Chrome、Edge、微信、QQ、游戏等
支持的文件操作：.txt, .doc, .docx, .pdf, .jpg, .png, .mp4, .mp3 等

注意：
1. 如果用户说"这个文件夹"、"当前文件夹"、"刚才打开的文件夹"，请在 directory 字段中保留原文
2. 如果目标名称包含"文件夹"、"目录"字样，target_type 应为 folder
3. 如果目标名称包含文件扩展名（如 .txt, .png），target_type 应为 file
4. 如果目标是常见程序名，target_type 应为 program

如果无法理解，返回：{"action": "unknown", "target": null, "target_type": "unknown", "destination": null, "directory": null, "message": "我不太明白，请试试：打开、创建、删除、移动、查看"}"""
    
    def _init_ollama(self):
        """初始化 Ollama"""
        try:
            import ollama
            self.ollama = ollama
            print("[INFO] Ollama 连接成功")
        except ImportError:
            print("[ERROR] ollama 库未安装，请运行：pip install ollama")
            self.ollama = None
        except Exception as e:
            print(f"[ERROR] Ollama 初始化失败：{e}")
            self.ollama = None
    
    def _resolve_drive_path(self, dest):
        """将中文驱动器名称和常见位置转换为实际路径"""
        import os
        
        # 驱动器映射
        drive_map = {
            'c盘': 'C:\\', 'c': 'C:\\', 'c:': 'C:\\',
            'd盘': 'D:\\', 'd': 'D:\\', 'd:': 'D:\\',
            'e盘': 'E:\\', 'e': 'E:\\', 'e:': 'E:\\',
            'f盘': 'F:\\', 'f': 'F:\\', 'f:': 'F:\\',
            'g盘': 'G:\\', 'g': 'G:\\', 'g:': 'G:\\',
            'h盘': 'H:\\', 'h': 'H:\\', 'h:': 'H:\\',
        }
        
        # 常见位置映射
        common_locations = {
            '桌面': os.path.join(os.path.expanduser('~'), 'Desktop'),
            '文档': os.path.join(os.path.expanduser('~'), 'Documents'),
            '下载': os.path.join(os.path.expanduser('~'), 'Downloads'),
            '桌宠': os.path.dirname(os.path.abspath(__file__)),
            '桌宠文件夹': os.path.dirname(os.path.abspath(__file__)),
            '程序目录': os.path.dirname(os.path.abspath(__file__)),
            '当前目录': os.getcwd(),
        }
        
        # 先检查驱动器映射
        if dest.lower() in drive_map:
            return drive_map[dest.lower()]
        
        # 检查常见位置
        if dest in common_locations:
            return common_locations[dest]
        
        return dest
    
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
                # 解析驱动器路径
                dest = parsed.get('destination')
                if dest:
                    dest = self._resolve_drive_path(dest)
                
                # 特殊修正：LLM可能把"桌宠"误识别为"桌面"
                if dest and "Desktop" in dest and "桌宠" in text:
                    dest = self._resolve_drive_path("桌宠")
                
                result = {
                    "success": parsed['action'] != 'unknown',
                    "action": parsed['action'],
                    "target": parsed.get('target'),
                    "target_type": parsed.get('target_type'),
                    "destination": dest,
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

        # 常见程序列表
        common_programs = {'记事本', '计算器', '画图', 'cmd', '命令提示符', 'powershell',
                          '控制面板', '任务管理器', '资源管理器', '注册表', '截图',
                          '截图工具', '写字板', '放大镜', '屏幕键盘', '语音输入',
                          '便签', '录音机', '微信', 'qq', 'chrome', 'edge', 'steam',
                          'code', 'vscode', 'vs code', 'visual studio code', 'word',
                          'excel', 'ppt', 'powerpoint', 'outlook', 'onenote', 'python'}

        def _detect_target_type(target):
            """根据目标名称判断类型"""
            target_lower = target.lower()
            
            # 检查是否为程序
            for prog in common_programs:
                if prog in target_lower or target_lower in prog:
                    return 'program'
            
            # 检查是否为文件夹（包含文件夹/目录字样）
            if any(word in target for word in ['文件夹', '目录', '文件夹里', '目录里']):
                return 'folder'
            
            # 检查是否为文件（包含扩展名）
            if '.' in target and len(target.split('.')[-1]) <= 4:
                return 'file'
            
            # 默认返回unknown
            return 'unknown'

        def _extract_context_dir(text):
            """提取上下文目录引用（如"这个文件夹"）"""
            context_phrases = ['这个文件夹', '当前文件夹', '刚才打开的文件夹', '刚才的文件夹']
            for phrase in context_phrases:
                if phrase in text:
                    return phrase
            return None

        # ---- 模式1：在「目录」里面「动作」「目标」----
        m = re.search(r'在\s*([\u4e00-\u9fa5\w\\/]+?)\s*(?:里|里面|目录|文件夹)?\s*'
                      r'(打开|创建|新建|删除|删掉|查看|看看|移动)\s*'
                      r'(?:命名为?|一个)?\s*[：:]?\s*([\u4e00-\u9fa5\w.\\/：:（）()，,]+?)?(?:的)?'
                      r'(?:文件|文件夹)?\s*$', text)
        if m:
            directory = m.group(1).strip()
            action_cn = m.group(2)
            target = m.group(3).strip() if m.group(3) else ''
            action_map = {'打开': 'open', '创建': 'create', '新建': 'create',
                         '删除': 'delete', '删掉': 'delete',
                         '查看': 'view', '看看': 'view', '移动': 'move'}
            action_en = action_map.get(action_cn, 'open')
            
            # 检查上下文引用
            context_dir = _extract_context_dir(text)
            
            if action_en == 'open':
                target_type = _detect_target_type(directory)
                return {"success": True, "action": "open", "target": directory,
                        "target_type": target_type, "directory": None, 
                        "destination": None, "content": None,
                        "message": f"正在打开{directory}..."}
            if action_en == 'create' and target:
                target_type = _detect_target_type(target)
                return {"success": True, "action": "create", "target": target,
                        "target_type": target_type, "directory": directory, 
                        "destination": None, "content": None,
                        "message": f"在{directory}中创建{target}"}
            if action_en == 'create' and not target:
                target_type = _detect_target_type(directory)
                return {"success": True, "action": "create", "target": directory,
                        "target_type": target_type, "directory": None, 
                        "destination": None, "content": None,
                        "message": f"正在创建{directory}..."}

        # ---- 模式2：删除/移动 + 上下文引用（如"删除这个文件夹里面的大愁居文件"）----
        m = re.search(r'(删除|删掉|移动)\s*(这个文件夹|当前文件夹|刚才打开的文件夹|刚才的文件夹)\s*(?:里面|里)?\s*(?:的)?\s*([\u4e00-\u9fa5\w.]+?)\s*(文件|文件夹)?\s*$', text)
        if m:
            action_cn = m.group(1)
            context_dir = m.group(2)
            target = m.group(3).strip()
            type_hint = m.group(4) if m.group(4) else ''
            
            action_map = {'删除': 'delete', '删掉': 'delete', '移动': 'move'}
            action_en = action_map.get(action_cn, 'delete')
            
            # 根据type_hint和文件名判断类型
            if type_hint == '文件' or '.' in target:
                target_type = 'file'
            elif type_hint == '文件夹':
                target_type = 'folder'
            else:
                target_type = 'file'  # 默认按文件处理
            
            if action_en == 'delete':
                return {"success": True, "action": "delete", "target": target,
                        "target_type": target_type, "directory": context_dir,
                        "destination": None, "content": None,
                        "message": f"已删除{target}"}
            elif action_en == 'move':
                return {"success": True, "action": "move", "target": target,
                        "target_type": target_type, "directory": context_dir,
                        "destination": None, "content": None,
                        "message": f"准备移动{target}"}
        
        # ---- 模式2b：删除/移动 + 简单"里面的"引用（如"删除里面的大愁居文件"）----
        m = re.search(r'(删除|删掉|移动)\s*(?:里面|里)?\s*(?:的)?\s*([\u4e00-\u9fa5\w.]+?)\s*(文件|文件夹)?\s*$', text)
        if m:
            action_cn = m.group(1)
            target = m.group(2).strip()
            type_hint = m.group(3) if m.group(3) else ''
            
            action_map = {'删除': 'delete', '删掉': 'delete', '移动': 'move'}
            action_en = action_map.get(action_cn, 'delete')
            
            # 判断类型
            if type_hint == '文件' or '.' in target:
                target_type = 'file'
            elif type_hint == '文件夹':
                target_type = 'folder'
            else:
                target_type = 'file'
            
            # 使用上下文（最近打开的文件夹）
            return {"success": True, "action": action_en, "target": target,
                    "target_type": target_type, "directory": "这个文件夹",
                    "destination": None, "content": None,
                    "message": f"已{action_cn}{target}"}

        # ---- 模式 3：打开 ----
        for kw in ["打开", "进入", "启动", "运行"]:
            if kw in text:
                target = text.replace(kw, "").strip()
                # 去掉"这个"等修饰词
                target = re.sub(r'^(?:这个 | 那个 | 那个)', '', target).strip()
                
                # 重要：先判断类型，再去掉后缀
                target_type = None
                if target.endswith('文件夹'):
                    target = target[:-3]
                    target_type = 'folder'
                elif target.endswith('目录'):
                    target = target[:-2]
                    target_type = 'folder'
                elif target.endswith('文件'):
                    target = target[:-2]
                    target_type = 'file'
                elif '.' in target and len(target.split('.')[-1]) <= 4:
                    # 有扩展名，肯定是文件
                    target_type = 'file'
                else:
                    # 无后缀，根据上下文推断
                    if '文件夹' in text:
                        target_type = 'folder'
                    elif '文件' in text:
                        target_type = 'file'
                    else:
                        # 默认调用检测函数（会检查是否为程序）
                        target_type = _detect_target_type(target)
                
                if target and target_type:
                    return {"success": True, "action": "open", "target": target,
                            "target_type": target_type, "directory": None, 
                            "destination": None, "content": None,
                            "message": f"正在打开{target}..."}

        # ---- 模式 4：创建/新建 ----
        for kw in ["创建", "新建"]:
            if kw in text:
                target = text.replace(kw, "").strip()
                target = re.sub(r'^(?:命名为？|一个)\s*', '', target)
                
                # 重要：先判断类型，再去掉后缀
                target_type = None
                if target.endswith('文件夹'):
                    target = target[:-3]
                    target_type = 'folder'
                elif target.endswith('目录'):
                    target = target[:-2]
                    target_type = 'folder'
                elif target.endswith('文件'):
                    target = target[:-2]
                    target_type = 'file'
                elif '.' in target and len(target.split('.')[-1]) <= 4:
                    # 有扩展名，肯定是文件
                    target_type = 'file'
                else:
                    # 无后缀，根据上下文推断
                    if '文件夹' in text:
                        target_type = 'folder'
                    elif '文件' in text:
                        target_type = 'file'
                    else:
                        # 默认调用检测函数
                        target_type = _detect_target_type(target)
                
                if target and target_type:
                    return {"success": True, "action": "create", "target": target,
                            "target_type": target_type, "directory": None, 
                            "destination": None, "content": None,
                            "message": f"已创建{target}"}

        # ---- 模式 5：删除 ----
        for kw in ["删除", "删掉"]:
            if kw in text:
                target = text.replace(kw, "").strip()
                # 检查是否有上下文引用
                context_dir = _extract_context_dir(text)
                
                # 重要：先判断类型，再去掉后缀
                # 这样能正确区分"丑橘文件"（文件名为"丑橘"）和"丑橘"（文件名就是"丑橘"）
                if target.endswith('文件夹'):
                    target = target[:-3]
                    target_type = 'folder'
                elif target.endswith('目录'):
                    target = target[:-2]
                    target_type = 'folder'
                elif target.endswith('文件'):
                    target = target[:-2]
                    target_type = 'file'
                elif '.' in target and len(target.split('.')[-1]) <= 4:
                    # 有扩展名，肯定是文件
                    target_type = 'file'
                else:
                    # 无后缀、无扩展名，根据上下文推断
                    # 如果原文中有"文件"字样（如"删除丑橘文件"），说明 target 已经是去掉后缀后的
                    # 如果原文中没有"文件"字样，默认按文件处理
                    if '文件' in text and '文件夹' not in text:
                        target_type = 'file'
                    elif '文件夹' in text:
                        target_type = 'folder'
                    else:
                        target_type = 'file'  # 默认按文件处理
                
                if target:
                    return {"success": True, "action": "delete", "target": target,
                            "target_type": target_type, "directory": context_dir,
                            "destination": None, "content": None,
                            "message": f"已删除{target}"}

        # ---- 模式 6：移动 ----
        if "移动" in text and "到" in text:
            parts = text.split("移动", 1)[1].split("到", 1)
            if len(parts) == 2:
                target = parts[0].strip()
                dest = parts[1].strip()
                
                # 重要：先判断类型，再去掉后缀
                target_type = None
                if target.endswith('文件夹'):
                    target = target[:-3]
                    target_type = 'folder'
                elif target.endswith('目录'):
                    target = target[:-2]
                    target_type = 'folder'
                elif target.endswith('文件'):
                    target = target[:-2]
                    target_type = 'file'
                elif '.' in target and len(target.split('.')[-1]) <= 4:
                    # 有扩展名，肯定是文件
                    target_type = 'file'
                else:
                    # 无后缀，根据上下文推断
                    if '文件夹' in text:
                        target_type = 'folder'
                    elif '文件' in text:
                        target_type = 'file'
                    else:
                        target_type = self._detect_target_type(target)
                
                # 解析驱动器路径（使用类方法）
                dest = self._resolve_drive_path(dest)
                # 特殊处理：LLM 可能把"桌宠"识别为"桌面"
                if "桌面" in parts[1] and "桌宠" in text:
                    dest = self._resolve_drive_path("桌宠")
                
                if target_type:
                    return {"success": True, "action": "move",
                            "target": target, "target_type": target_type,
                            "destination": dest, "directory": None, "content": None,
                            "message": "已移动文件"}

        # ---- 模式7：查看 ----
        for kw in ["查看", "看看"]:
            if kw in text:
                target = text.replace(kw, "").strip()
                target_type = _detect_target_type(target)
                if target:
                    return {"success": True, "action": "view", "target": target,
                            "target_type": target_type, "directory": None, 
                            "destination": None, "content": None,
                            "message": f"正在查看{target}..."}

        return {"success": False, "action": "unknown",
                "target": None, "target_type": "unknown", "directory": None,
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
