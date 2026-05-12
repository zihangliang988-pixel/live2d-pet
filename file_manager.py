#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文件管理器 - 处理所有文件操作 + 应用程序启动
"""

import os
import sys
import shutil
import json
import time as time_module
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
    "terminal": ["WindowsTerminal.exe", "cmd.exe", "powershell.exe"],
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
        """查找系统应用程序
        
        优先级：
        1. 桌面快捷方式（.lnk 文件）
        2. 内置映射表
        3. PATH 环境变量
        4. 常见安装目录
        """
        name_lower = name.lower().strip()
        
        # 1. 优先搜索桌面快捷方式
        desktop_shortcut = self._find_desktop_shortcut(name)
        if desktop_shortcut:
            print(f"[INFO] 找到桌面快捷方式：{desktop_shortcut}")
            return desktop_shortcut
        
        # 2. 直接匹配映射表
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
        
        # 3. 智能匹配（避免短词误匹配长名）
        for app_name, candidates in self.window_apps.items():
            a = app_name.lower()
            ok = (name_lower == a
                  or (len(name_lower) >= 4 and len(a) >= 3 and name_lower.endswith(a))
                  or (len(a) >= 4 and len(name_lower) >= 3 and a.endswith(name_lower))
                  or (len(a) >= 4 and len(name_lower) >= 4 and a in name_lower))
            if not ok:
                continue
            if isinstance(candidates, str):
                candidates = [candidates]
            for candidate in candidates:
                if candidate.startswith("ms-"):
                    return candidate
                found = self._which(candidate)
                if found:
                    return found
        
        # 4. 最后尝试在 PATH 中查找
        return self._which(name)
    
    def _find_desktop_shortcut(self, name: str) -> Optional[str]:
        """在桌面搜索快捷方式并解析目标路径"""
        import os
        
        # 获取桌面路径（多个可能位置）
        desktop_paths = [
            os.path.join(os.path.expanduser('~'), 'Desktop'),
            os.path.join(os.environ.get('USERPROFILE', ''), 'Desktop'),
            os.path.join(os.environ.get('PUBLIC', ''), 'Desktop'),
        ]
        
        search_name = name.lower()
        # 去掉常见后缀
        for suffix in ['快捷方式', 'launcher', '启动器', '启动']:
            if search_name.endswith(suffix):
                search_name = search_name[:-len(suffix)]
                break
        
        for desktop_path in desktop_paths:
            if not os.path.exists(desktop_path):
                continue
            
            try:
                # 只搜索桌面第一层，不递归
                for item in os.listdir(desktop_path):
                    item_lower = item.lower()
                    
                    # 匹配快捷方式文件
                    if item_lower.endswith('.lnk'):
                        lnk_name = os.path.splitext(item)[0].lower()
                        
                        # 精确匹配或包含匹配
                        if lnk_name == search_name or (len(search_name) >= 2 and search_name in lnk_name):
                            lnk_path = os.path.join(desktop_path, item)
                            # 解析快捷方式目标
                            target = self._resolve_shortcut(lnk_path)
                            if target and os.path.exists(target):
                                return target
                                
            except Exception as e:
                print(f"[WARN] 搜索桌面快捷方式失败：{e}")
                continue
        
        return None
    
    def _resolve_shortcut(self, lnk_path: str) -> Optional[str]:
        """解析 Windows 快捷方式 (.lnk) 文件，返回目标路径"""
        # 方案 1: 使用 pywin32（Windows 原生）
        try:
            import win32com.client
            shell = win32com.client.Dispatch("WScript.Shell")
            shortcut = shell.CreateShortcut(lnk_path)
            target = shortcut.TargetPath
            if target and os.path.exists(target):
                return target
        except ImportError:
            pass  # 尝试方案 2
        except Exception as e:
            print(f"[DEBUG] pywin32 解析失败：{e}")
        
        # 方案 2: 使用 PowerShell（跨平台）
        try:
            import subprocess
            # 在 Windows 上执行 PowerShell 命令
            ps_cmd = f'$WshShell = New-Object -ComObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut("{lnk_path}"); $Shortcut.TargetPath'
            
            # 如果在 WSL，通过 Windows 的 PowerShell 执行
            result = subprocess.run(
                ['wslvar', 'USERPROFILE'] if False else ['powershell', '-Command', ps_cmd],
                capture_output=True, text=True, timeout=5,
                shell=True if os.name == 'nt' else False
            )
            
            if result.returncode == 0:
                target = result.stdout.strip()
                if target and os.path.exists(target):
                    return target
        except Exception as e:
            print(f"[DEBUG] PowerShell 解析失败：{e}")
        
        # 方案 3: 直接返回.lnk 路径（让 Windows 自己处理）
        # Windows 可以自动识别并打开.lnk 文件
        if os.path.exists(lnk_path):
            return lnk_path
        
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
            if not os.path.exists(base):
                continue
            _walk_start = time_module.time()
            try:
                for root, dirs, files in os.walk(base):
                    # 单目录搜索超时 1 秒
                    if time_module.time() - _walk_start > 1.0:
                        del dirs[:]
                        break

                    for f in files:
                        if f.lower() == exe_name.lower():
                            return os.path.join(root, f)

                    # 限制搜索深度
                    if root.count(os.sep) > base.count(os.sep) + 3:
                        del dirs[:]
                        continue
            except PermissionError:
                continue
            except Exception:
                continue
        return None

    def _find_file_in_dir(self, name: str, directory: str) -> Optional[str]:
        """在指定目录中搜索文件（深度 2 层）"""
        if not os.path.isdir(directory):
            return None
        search_name = name.lower()
        try:
            for root, dirs, files in os.walk(directory):
                depth = root.replace(directory, '').count(os.sep)
                if depth > 2:
                    del dirs[:]
                    continue
                # 精确匹配 + 前缀匹配（如 "大愁居" 匹配 "大愁居.txt"）
                for f in files:
                    f_lower = f.lower()
                    f_noext = os.path.splitext(f_lower)[0]
                    if f_lower == search_name or f_noext == search_name:
                        return os.path.join(root, f)
                    # 部分匹配（搜索词在文件名中）
                    if len(search_name) >= 3 and search_name in f_lower:
                        return os.path.join(root, f)
                for d in dirs:
                    if d.lower() == search_name:
                        return os.path.join(root, d)
                    if len(search_name) >= 3 and search_name in d.lower():
                        return os.path.join(root, d)
        except Exception:
            pass
        return None

    def _get_drive_letters(self):
        """获取系统中可用的驱动器列表（不包括网络驱动器）"""
        if sys.platform == 'win32':
            try:
                # 方法1：使用 ctypes（更可靠）
                import ctypes
                kernel32 = ctypes.windll.kernel32
                
                drives = []
                # 遍历所有可能的驱动器字母 (A-Z)
                for i in range(ord('A'), ord('Z') + 1):
                    drive = chr(i) + ':\\'
                    # GetDriveTypeW 返回驱动器类型
                    drive_type = kernel32.GetDriveTypeW(drive)
                    # DRIVE_FIXED = 3, DRIVE_REMOVABLE = 2, DRIVE_CDROM = 5
                    if drive_type in [2, 3, 5]:
                        # 验证驱动器是否存在
                        if os.path.exists(drive):
                            drives.append(drive)
                return drives
            except Exception:
                # 回退方案：手动列出常见驱动器
                common_drives = ['C:\\', 'D:\\', 'E:\\', 'F:\\', 'G:\\', 'H:\\']
                return [d for d in common_drives if os.path.exists(d)]
        else:
            return []

    def _find_file(self, name: str, search_depth: int = 2, prefer_folder: bool = True) -> Optional[str]:
        """在系统中查找文件或文件夹（支持模糊匹配，带深度限制）
        
        Args:
            name: 要搜索的名称
            search_depth: 搜索深度限制
            prefer_folder: 是否优先返回文件夹（默认 True）
        """
        # 优先搜索常用位置（桌面、文档等）
        common_paths = [
            self.desktop_path,
            self.default_folder,
            os.path.join(os.path.expanduser('~'), 'Documents'),
            os.path.join(os.path.expanduser('~'), 'Downloads'),
            os.path.join(os.path.expanduser('~'), 'Desktop'),
            os.path.expanduser('~'),  # C:\Users\用户名
        ]
        
        # 获取桌宠程序所在目录及其父目录（确保能搜索到 D:\桌宠\D 盘\丑橘）
        app_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(app_dir)
        if parent_dir not in common_paths:
            common_paths.insert(0, app_dir)  # 桌宠目录优先
            common_paths.insert(1, parent_dir)  # 父目录其次
        
        # 获取所有本地驱动器
        all_drives = self._get_drive_letters()
        
        # 去掉 文件夹/目录 后缀，便于模糊匹配
        search_name = name
        for suffix in ['文件夹', '目录', '文件']:
            if search_name.endswith(suffix) and len(search_name) > len(suffix):
                search_name = search_name[:-len(suffix)]
                break

        # 先收集所有匹配项，然后按优先级排序
        matches = []
        folder_matches = []  # 文件夹匹配
        file_matches = []     # 文件匹配

        # 搜索超时保护（避免卡住主线程）
        _search_aborted = [False]
        _search_start = [time_module.time()]
        _max_search_time = 5.0  # 最大搜索时间 5 秒

        def _abort_check():
            if time_module.time() - _search_start[0] > _max_search_time:
                _search_aborted[0] = True

        # 跳过的系统目录和常见排除列表
        skip_dirs = {
            'windows', 'winnt', 'program files', 'program files (x86)',
            'system32', 'syswow64', '$recycle.bin', 'system volume information',
            'appdata', 'localappdata', 'roaming', 'python', 'node_modules', 
            '.git', '__pycache__', 'temp', 'tmp', 'cache', 'logs',
            'microsoft', 'intel', 'amd', 'nvidia', 'programdata',
        }

        def _search_in_path(search_path, priority_offset=0, max_depth=None):
            """在指定路径中搜索，priority_offset 用于区分搜索优先级"""
            if not os.path.exists(search_path):
                return
            if _search_aborted[0]:
                return
            try:
                for root, dirs, files in os.walk(search_path):
                    if _search_aborted[0]:
                        break
                    _abort_check()

                    # 限制搜索深度
                    depth = root.replace(search_path, '').count(os.sep)
                    current_max_depth = max_depth if max_depth is not None else search_depth
                    if depth > current_max_depth:
                        del dirs[:]
                        continue

                    # 跳过不需要深入搜索的目录
                    dir_name_lower = os.path.basename(root).lower()
                    if dir_name_lower in skip_dirs:
                        del dirs[:]
                        continue

                    # 搜索文件夹（拉大优先级间隔，精确匹配绝对优先）
                    for item_name in dirs:
                        item_lower = item_name.lower()
                        search_lower = search_name.lower()
                        name_lower = name.lower()
                        
                        if item_lower == search_lower:
                            folder_matches.append((1 + priority_offset, os.path.join(root, item_name)))
                        elif item_lower == name_lower:
                            folder_matches.append((2 + priority_offset, os.path.join(root, item_name)))
                        elif len(search_name) >= 3 and search_lower in item_lower:  # 至少 3 字才模糊匹配
                            folder_matches.append((20 + priority_offset, os.path.join(root, item_name)))

                    # 搜索文件（同样拉大优先级间隔）
                    for item_name in files:
                        item_lower = item_name.lower()
                        search_lower = search_name.lower()
                        name_lower = name.lower()
                        
                        if item_lower == search_lower:
                            file_matches.append((1 + priority_offset, os.path.join(root, item_name)))
                        elif item_lower == name_lower:
                            file_matches.append((2 + priority_offset, os.path.join(root, item_name)))
                        elif len(search_name) >= 3 and search_lower in item_lower:  # 至少 3 字才模糊匹配
                            file_matches.append((20 + priority_offset, os.path.join(root, item_name)))
            except PermissionError:
                return
            except Exception:
                return

        # 第一阶段：搜索常用位置（高优先级）
        for path in common_paths:
            _search_in_path(path, priority_offset=0)

        # 第二阶段：搜索所有驱动器（低优先级，深度限制为 1）
        if not folder_matches and not file_matches and all_drives:
            for drive in all_drives:
                # 系统盘根目录限制深度为 1，其他盘深度为 2
                if drive.lower() == 'c:\\':
                    _search_in_path(drive, priority_offset=10, max_depth=1)
                else:
                    _search_in_path(drive, priority_offset=10, max_depth=2)

        # 合并匹配结果：优先返回文件夹
        if prefer_folder:
            if folder_matches:
                folder_matches.sort(key=lambda x: x[0])
                return folder_matches[0][1]
            if file_matches:
                file_matches.sort(key=lambda x: x[0])
                return file_matches[0][1]
        else:
            # 不优先文件夹时，合并并排序
            all_matches = folder_matches + file_matches
            if all_matches:
                all_matches.sort(key=lambda x: x[0])
                return all_matches[0][1]

        # 直接作为路径尝试
        if os.path.exists(name):
            return name

        return None

    def _find_all_matches(self, name: str, max_count: int = 5, prefer_folder: bool = True) -> List[Dict]:
        """查找所有匹配项，用于多候选提示"""
        # 复用 _find_file 的搜索逻辑，但返回所有匹配
        common_paths = [
            self.desktop_path,
            self.default_folder,
            os.path.join(os.path.expanduser('~'), 'Documents'),
            os.path.join(os.path.expanduser('~'), 'Downloads'),
            os.path.join(os.path.expanduser('~'), 'Desktop'),
            os.path.expanduser('~'),
        ]
        
        app_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(app_dir)
        if parent_dir not in common_paths:
            common_paths.insert(0, app_dir)
            common_paths.insert(1, parent_dir)
        
        # 去掉后缀
        search_name = name
        for suffix in ['文件夹', '目录', '文件']:
            if search_name.endswith(suffix) and len(search_name) > len(suffix):
                search_name = search_name[:-len(suffix)]
                break
        
        all_matches = []
        
        def _collect_in_path(search_path, priority_offset=0):
            if not os.path.exists(search_path):
                return
            try:
                for root, dirs, files in os.walk(search_path):
                    depth = root.replace(search_path, '').count(os.sep)
                    if depth > 2:
                        del dirs[:]
                        continue
                    
                    search_lower = search_name.lower()
                    
                    for item_name in dirs:
                        item_lower = item_name.lower()
                        item_path = os.path.join(root, item_name)
                        if item_lower == search_lower:
                            all_matches.append((1 + priority_offset, item_path, True))
                        elif len(search_name) >= 3 and search_lower in item_lower:
                            all_matches.append((20 + priority_offset, item_path, True))
                    
                    for item_name in files:
                        item_lower = item_name.lower()
                        item_path = os.path.join(root, item_name)
                        if item_lower == search_lower:
                            all_matches.append((1 + priority_offset, item_path, False))
                        elif len(search_name) >= 3 and search_lower in item_lower:
                            all_matches.append((20 + priority_offset, item_path, False))
            except Exception:
                return
        
        for path in common_paths:
            _collect_in_path(path, priority_offset=0)
        
        # 排序并返回
        all_matches.sort(key=lambda x: x[0])
        result = []
        for priority, path, is_dir in all_matches[:max_count]:
            result.append({
                'path': path,
                'is_dir': is_dir,
                'is_file': not is_dir
            })
        return result

    def open_file(self, name: str, target_type: str = None) -> Dict:
        """打开文件、文件夹或应用程序"""
        # 根据 target_type 决定是否优先搜索文件夹
        if target_type == 'folder':
            prefer_folder = True
        elif target_type == 'file':
            prefer_folder = False
        else:
            prefer_folder = True  # 默认优先文件夹（更符合直觉）
        
        # 先尝试作为文件/文件夹打开（优先）
        file_path = self._find_file(name, prefer_folder=prefer_folder)
        
        # 如果找到多个候选，返回提示让用户选择
        if not file_path:
            matches = self._find_all_matches(name, max_count=5, prefer_folder=prefer_folder)
            if len(matches) > 1:
                options = "\n".join([f"{i+1}. {m['path']} ({'📁 文件夹' if m['is_dir'] else '📄 文件'})" 
                                    for i, m in enumerate(matches[:5])])
                return {
                    "success": False, 
                    "message": f"找到多个匹配项，请指定：\n{options}\n\n或者说「打开{name}文件夹」/「打开{name}文件」~"
                }
        
        if file_path:
            try:
                if sys.platform == 'win32':
                    os.startfile(file_path)
                else:
                    os.system(f'open "{file_path}"')
                action = "文件夹" if os.path.isdir(file_path) else "文件"
                return {"success": True, "message": f"正在打开{action} {name}...", "path": file_path, "is_dir": os.path.isdir(file_path)}
            except Exception as e:
                return {"success": False, "message": f"打开失败：{str(e)}"}

        # 再尝试作为应用程序打开（先去掉文件/文件夹后缀，避免误匹配）
        app_name = name
        for suffix in ['文件夹', '目录', '文件']:
            if app_name.endswith(suffix) and len(app_name) > len(suffix):
                app_name = app_name[:-len(suffix)]
                break
        app_path = self._find_app(app_name)
        if app_path:
            try:
                if app_path.startswith("ms-"):
                    subprocess.run(["start", app_path], shell=True, timeout=5)
                else:
                    subprocess.Popen([app_path])
                return {"success": True, "message": f"正在打开 {name}..."}
            except Exception as e:
                return {"success": False, "message": f"打开 {name} 失败：{str(e)}"}
        
        # 都没找到
        return {"success": False, "message": f"没找到 '{name}' 哦"}



    def create_file(self, name: str, content: str = "", directory: str = None) -> Dict:
        """创建文件"""
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
            return {"success": True, "message": f"已创建文件 {name}", "path": file_path}
        except Exception as e:
            return {"success": False, "message": f"创建文件失败：{str(e)}"}

    def create_folder(self, name: str, directory: str = None) -> Dict:
        """创建文件夹"""
        try:
            target_dir = directory or self.default_folder
            # 支持嵌套路径，如 "文档/项目/2024"
            if '/' in name or '\\' in name:
                folder_path = os.path.join(target_dir, name.replace('\\', '/'))
            else:
                folder_path = os.path.join(target_dir, name)
            
            if os.path.exists(folder_path):
                return {"success": False, "message": f"文件夹 '{name}' 已经存在了"}
            
            Path(folder_path).mkdir(parents=True, exist_ok=True)
            return {"success": True, "message": f"已创建文件夹 {name}", "path": folder_path}
        except Exception as e:
            return {"success": False, "message": f"创建文件夹失败：{str(e)}"}

    def delete_file(self, name: str, directory: str = None) -> Dict:
        """删除文件。如果指定 directory，优先在该目录下搜索。"""
        if directory:
            # 优先在指定目录下找
            dir_path = directory.rstrip('\\/')
            candidate = os.path.join(dir_path, name)
            if os.path.exists(candidate):
                file_path = candidate
            else:
                # 在指定目录内搜索
                file_path = self._find_file_in_dir(name, dir_path)
        else:
            file_path = self._find_file(name)

        if not file_path:
            msg = f"没找到 '{name}'"
            if directory:
                msg += f" 在目录 '{directory}' 中"
            msg += " 哦"
            return {"success": False, "message": msg}
        
        # 验证文件确实存在
        if not os.path.exists(file_path):
            return {"success": False, "message": f"文件 '{name}' 不存在或已被删除"}
        
        try:
            import ctypes
            from ctypes import wintypes
            
            # 使用 SHFileOperationW 将文件移到回收站
            class SHFILEOPSTRUCTW(ctypes.Structure):
                _fields_ = [
                    ("hwnd", wintypes.HWND),
                    ("wFunc", wintypes.UINT),
                    ("pFrom", wintypes.LPCWSTR),
                    ("pTo", wintypes.LPCWSTR),
                    ("fFlags", wintypes.FILEOP_FLAGS),
                    ("fAnyOperationsAborted", wintypes.BOOL),
                    ("hNameMappings", wintypes.LPVOID),
                    ("lpszProgressTitle", wintypes.LPCWSTR)
                ]
            
            # FO_DELETE = 3
            # FOF_ALLOWUNDO = 0x40
            # FOF_NOCONFIRMATION = 0x10
            # FOF_SILENT = 0x4
            
            fileop = SHFILEOPSTRUCTW()
            fileop.hwnd = None
            fileop.wFunc = 3  # FO_DELETE
            fileop.pFrom = ctypes.c_wchar_p(file_path + '\0')  # 必须以双null结尾
            fileop.pTo = None
            fileop.fFlags = 0x40 | 0x10 | 0x4  # FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT
            fileop.fAnyOperationsAborted = False
            fileop.hNameMappings = None
            fileop.lpszProgressTitle = None
            
            result = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(fileop))
            
            if result != 0:
                return {"success": False, "message": f"删除失败，错误码：{result}"}
            
            # 验证文件是否真的被删除了（移到回收站）
            if os.path.exists(file_path):
                # 尝试直接删除（绕过回收站）
                try:
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                    else:
                        import shutil
                        shutil.rmtree(file_path)
                except Exception as e2:
                    return {"success": False, "message": f"文件 '{name}' 删除失败，请检查权限或手动删除"}
            
            return {"success": True, "message": f"已将 {name} 移到回收站"}
        except Exception as e:
            # 作为最后的备用方案，直接删除
            try:
                if os.path.isfile(file_path):
                    os.remove(file_path)
                else:
                    import shutil
                    shutil.rmtree(file_path)
                return {"success": True, "message": f"已删除 {name}"}
            except Exception as e2:
                return {"success": False, "message": f"删除失败：{str(e2)}"}

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
