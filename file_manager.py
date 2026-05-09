#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文件管理器 - 处理所有文件操作 + 应用程序启动
"""

import os
import sys
import shutil
import json
import subprocess
from pathlib import Path
from typing import Optional, List, Dict


# Windows 应用程序名称映射表
WINDOWS_APPS = {
    # 中文名 -> 可执行文件名
    "记事本": "notepad.exe",
    "计算器": "calc.exe",
    "画图": "mspaint.exe",
    "cmd": "cmd.exe",
    "命令提示符": "cmd.exe",
    "powershell": "powershell.exe",
    "控制面板": "control.exe",
    "任务管理器": "taskmgr.exe",
    "资源管理器": "explorer.exe",
    "注册表": "regedit.exe",
    "截图": "snippingtool.exe",
    "截图工具": "SnippingTool.exe",
    "写字板": "write.exe",
    "放大镜": "magnify.exe",
    "屏幕键盘": "osk.exe",
    "语音输入": "SpeechUX.exe",
    "便签": "StikyNot.exe",
    "录音机": "SoundRecorder.exe",
    # 中文名 -> 完整路径
    "微信": "C:/Program Files/Tencent/WeChat/WeChat.exe",
    "qq": "C:/Program Files (x86)/Tencent/QQ/Bin/QQ.exe",
}

# 通用软件名 -> 可能路径
COMMON_APPS = {
    "chrome": ["chrome.exe", "google chrome"],
    "edge": ["msedge.exe", "microsoft edge"],
    "steam": ["steam.exe"],
    "code": ["code.exe"],
    "vscode": ["code.exe"],
    "vs code": ["code.exe"],
    "visual studio code": ["code.exe"],
    "notepad": ["notepad.exe"],
    "notepad++": ["notepad++.exe"],
    "sublime": ["sublime_text.exe"],
    "word": ["WINWORD.EXE"],
    "excel": ["EXCEL.EXE"],
    "ppt": ["POWERPNT.EXE"],
    "powerpoint": ["POWERPNT.EXE"],
    "outlook": ["OUTLOOK.EXE"],
    "onenote": ["ONENOTE.EXE"],
    "python": ["python.exe"],
    "terminal": ["cmd.exe", "powershell.exe", "WindowsTerminal.exe"],
    "terminal": ["WindowsTerminal.exe"],
    "settings": ["SystemSettings.exe", "ms-settings:"],
    "设置": ["SystemSettings.exe", "ms-settings:"],
    "文件夹": ["explorer.exe"],
    "文件管理器": ["explorer.exe"],
    "浏览器": ["msedge.exe", "chrome.exe", "firefox.exe"],
}


class FileManager:
    def __init__(self, config_path: str = "config.json"):
        self.config = self._load_config(config_path)
        self.desktop_path = self.config["user_preferences"]["desktop_path"]
        self.default_folder = self.config["user_preferences"]["default_folder"]
        self.window_apps = {**WINDOWS_APPS, **COMMON_APPS}

    def _load_config(self, config_path: str) -> Dict:
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return {
                "user_preferences": {
                    "desktop_path": str(Path.home() / "Desktop"),
                    "default_folder": "D:/桌宠/文件",
                    "confirmation_required": ["delete", "move", "rename"]
                }
            }

    def _find_app(self, name: str) -> Optional[str]:
        """查找系统应用程序"""
        name_lower = name.lower().strip()

        # 1. 直接匹配映射表
        if name in self.window_apps:
            candidates = self.window_apps[name]
            if isinstance(candidates, str):
                candidates = [candidates]
            for candidate in candidates:
                if candidate.startswith("ms-"):
                    return candidate  # ms-settings: 这种 URI 协议
                found = self._which(candidate)
                if found:
                    return found

        # 2. 模糊匹配映射表的 key
        for app_name, candidates in self.window_apps.items():
            if name_lower in app_name.lower() or app_name.lower() in name_lower:
                if isinstance(candidates, str):
                    candidates = [candidates]
                for candidate in candidates:
                    if candidate.startswith("ms-"):
                        return candidate
                    found = self._which(candidate)
                    if found:
                        return found

        # 3. 尝试直接作为可执行文件名
        exe_name = name if name.endswith('.exe') else f"{name}.exe"
        found = self._which(exe_name)
        if found:
            return found

        # 4. 检查是否包含 .exe
        if not name.endswith('.exe'):
            for ext in ['', '.exe', '.lnk']:
                found = self._which(f"{name}{ext}")
                if found:
                    return found

        return None

    def _which(self, exe_name: str) -> Optional[str]:
        """在 PATH 中查找可执行文件"""
        try:
            result = subprocess.run(
                ["where", exe_name],
                capture_output=True, text=True, timeout=3
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip().split('\n')[0]
        except:
            pass

        # 也搜索常见安装目录
        common_dirs = [
            os.environ.get('ProgramFiles', 'C:/Program Files'),
            os.environ.get('ProgramFiles(x86)', 'C:/Program Files (x86)'),
            os.environ.get('SystemRoot', 'C:/Windows'),
            os.environ.get('SystemRoot', 'C:/Windows') + '/System32',
            os.path.expanduser('~/AppData/Local'),
            os.path.expanduser('~/AppData/Roaming/Microsoft/Windows/Start Menu/Programs'),
        ]
        for base in common_dirs:
            for root, dirs, files in os.walk(base):
                for f in files:
                    if f.lower() == exe_name.lower():
                        return os.path.join(root, f)
                # 限制搜索深度
                if root.count(os.sep) > base.count(os.sep) + 4:
                    break
        return None

    def _find_file(self, name: str) -> Optional[str]:
        """在桌面、默认文件夹和常见位置查找文件或文件夹（支持模糊匹配）"""
        search_paths = [
            self.desktop_path,
            self.default_folder,
            os.path.expanduser('~'),  # C:\Users\用户名
            "D:/",
            "C:/",
        ]

        # 去掉 文件夹/目录 后缀，便于模糊匹配
        search_name = name
        for suffix in ['文件夹', '目录', '文件']:
            if search_name.endswith(suffix) and len(search_name) > len(suffix):
                search_name = search_name[:-len(suffix)]
                break

        for search_path in search_paths:
            if not os.path.exists(search_path):
                continue
            try:
                for root, dirs, files in os.walk(search_path):
                    # 限制搜索深度，避免遍历整个 C 盘
                    depth = root.replace(search_path, '').count(os.sep)
                    if depth > 3:
                        del dirs[:]  # 不继续深入
                        continue

                    for item_name in dirs + files:
                        # 完全匹配
                        if item_name.lower() == search_name.lower() or item_name.lower() == name.lower():
                            return os.path.join(root, item_name)
                        # 部分匹配
                        if len(search_name) >= 2 and search_name.lower() in item_name.lower():
                            return os.path.join(root, item_name)
            except PermissionError:
                continue
            except Exception:
                continue

        # 直接作为路径尝试
        if os.path.exists(name):
            return name

        return None

    def open_file(self, name: str) -> Dict:
        """打开文件、文件夹或应用程序"""
        # 先尝试作为应用程序打开
        app_path = self._find_app(name)
        if app_path:
            try:
                if app_path.startswith("ms-"):
                    # Windows URI 协议
                    subprocess.run(["start", app_path], shell=True, timeout=5)
                else:
                    subprocess.Popen([app_path])
                return {"success": True, "message": f"正在打开 {name}..."}
            except Exception as e:
                return {"success": False, "message": f"打开 {name} 失败：{str(e)}"}

        # 尝试作为文件/文件夹打开
        file_path = self._find_file(name)
        if not file_path:
            return {"success": False, "message": f"没找到 '{name}' 哦，试试：记事本、计算器、画图、微信、QQ"}

        try:
            is_directory = os.path.isdir(file_path)
            if sys.platform == 'win32':
                os.startfile(file_path)
            elif sys.platform == 'darwin':
                os.system(f'open {file_path}')
            else:
                os.system(f'xdg-open {file_path}')

            action = "文件夹" if is_directory else "文件"
            return {"success": True, "message": f"正在打开{action} {name}..."}
        except Exception as e:
            return {"success": False, "message": f"打开失败：{str(e)}"}

    def create_file(self, name: str, content: str = "", directory: str = None) -> Dict:
        try:
            target_dir = directory or self.default_folder
            Path(target_dir).mkdir(parents=True, exist_ok=True)
            if '/' in name or '\\' in name:
                parts = name.replace('\\', '/').split('/')
                if len(parts) > 1:
                    target_dir = os.path.join(target_dir, '/'.join(parts[:-1]))
                    Path(target_dir).mkdir(parents=True, exist_ok=True)
                    name = parts[-1]
            file_path = os.path.join(target_dir, name)
            if os.path.exists(file_path):
                return {"success": False, "message": f"'{name}' 已经存在了"}
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return {"success": True, "message": f"已创建 {name}", "path": file_path}
        except Exception as e:
            return {"success": False, "message": f"创建失败：{str(e)}"}

    def delete_file(self, name: str) -> Dict:
        file_path = self._find_file(name)
        if not file_path:
            return {"success": False, "message": f"没找到 '{name}' 哦"}
        try:
            import ctypes
            ctypes.windll.shell32.ShellExecuteW(None, "delete", file_path, None, None, 0)
            return {"success": True, "message": f"已将 {name} 移到回收站"}
        except Exception as e:
            return {"success": False, "message": f"删除失败：{str(e)}"}

    def move_file(self, name: str, target_dir: str) -> Dict:
        file_path = self._find_file(name)
        if not file_path:
            return {"success": False, "message": f"没找到 '{name}' 哦"}
        try:
            Path(target_dir).mkdir(parents=True, exist_ok=True)
            file_name = Path(file_path).name
            new_path = os.path.join(target_dir, file_name)
            shutil.move(file_path, new_path)
            return {"success": True, "message": f"已将 {name} 移动到 {target_dir}"}
        except Exception as e:
            return {"success": False, "message": f"移动失败：{str(e)}"}

    def rename_file(self, old_name: str, new_name: str) -> Dict:
        file_path = self._find_file(old_name)
        if not file_path:
            return {"success": False, "message": f"没找到 '{old_name}' 哦"}
        try:
            dir_path = os.path.dirname(file_path)
            new_path = os.path.join(dir_path, new_name)
            os.rename(file_path, new_path)
            return {"success": True, "message": f"已将 {old_name} 重命名为 {new_name}"}
        except Exception as e:
            return {"success": False, "message": f"重命名失败：{str(e)}"}

    def view_file(self, name: str) -> Dict:
        file_path = self._find_file(name)
        if not file_path:
            return {"success": False, "message": f"没找到 '{name}' 哦"}
        try:
            stat = os.stat(file_path)
            info = {
                "name": Path(file_path).name,
                "path": file_path,
                "size": self._format_size(stat.st_size),
                "modified": self._format_time(stat.st_mtime),
                "is_file": os.path.isfile(file_path),
                "is_dir": os.path.isdir(file_path)
            }
            return {"success": True, "message": f"📄 {info['name']} ({info['size']})"}
        except Exception as e:
            return {"success": False, "message": f"查看失败：{str(e)}"}

    def list_files(self, directory: str = None) -> Dict:
        target_dir = directory or self.desktop_path
        if not os.path.exists(target_dir):
            return {"success": False, "message": f"目录 '{target_dir}' 不存在"}
        try:
            items = []
            for item in Path(target_dir).iterdir():
                items.append({
                    "name": item.name,
                    "is_file": item.is_file(),
                    "is_dir": item.is_dir(),
                    "size": self._format_size(item.stat().st_size) if item.is_file() else "-"
                })
            return {"success": True, "items": items, "count": len(items)}
        except Exception as e:
            return {"success": False, "message": f"列出失败：{str(e)}"}

    @staticmethod
    def _format_size(size: int) -> str:
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"

    @staticmethod
    def _format_time(timestamp: float) -> str:
        from datetime import datetime
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
