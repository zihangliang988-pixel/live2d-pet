#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
桌宠快捷方式生成器
支持自定义图标位置
"""

import os
import sys
import ctypes
import win32com.client

def create_shortcut(target_path, shortcut_path, icon_path=None, description="桌宠 - 仙狐"):
    """
    创建 Windows 快捷方式
    
    参数:
        target_path: 目标程序路径 (.exe 或 .py)
        shortcut_path: 快捷方式保存路径 (.lnk)
        icon_path: 图标路径 (可选，可以是 .ico, .exe, .dll 等)
        description: 快捷方式描述
    """
    # 创建 Shell 对象
    shell = win32com.client.Dispatch("WScript.Shell")
    
    # 创建快捷方式
    shortcut = shell.CreateShortCut(shortcut_path)
    
    # 设置目标路径
    shortcut.TargetPath = target_path
    
    # 设置工作目录
    shortcut.WorkingDirectory = os.path.dirname(target_path)
    
    # 设置描述
    shortcut.Description = description
    
    # 设置图标位置
    if icon_path and os.path.exists(icon_path):
        # 如果是 .exe 或 .dll，可以指定图标索引 (如 "icon.exe,0")
        if icon_path.lower().endswith(('.exe', '.dll')):
            shortcut.IconLocation = f'{icon_path},0'
        else:
            shortcut.IconLocation = icon_path
        print(f"✅ 已设置自定义图标：{icon_path}")
    else:
        # 使用默认图标
        if target_path.lower().endswith('.py'):
            # Python 脚本使用 python.exe 的图标
            python_exe = sys.executable
            shortcut.IconLocation = f'{python_exe},0'
            print(f"ℹ️  使用 Python 默认图标：{python_exe}")
        else:
            shortcut.IconLocation = target_path
            print(f"ℹ️  使用程序默认图标")
    
    # 设置运行模式 (正常窗口)
    shortcut.WindowStyle = 1  # 1=正常窗口，3=最大化，7=最小化
    
    # 保存快捷方式
    shortcut.Save()
    print(f"✅ 快捷方式已创建：{shortcut_path}")
    
    return shortcut_path

def get_desktop_path():
    """获取桌面路径"""
    return os.path.join(os.environ['USERPROFILE'], 'Desktop')

def get_icon_candidates():
    """获取可能的图标文件"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = []
    
    # 查找常见的图标文件
    for ext in ['*.ico', '*.png', '*.jpg', '*.jpeg']:
        import glob
        for path in glob.glob(os.path.join(base_dir, ext)):
            candidates.append(path)
        for path in glob.glob(os.path.join(base_dir, 'assets', '**', ext), recursive=True):
            candidates.append(path)
    
    # 添加程序本身的图标
    candidates.append(os.path.join(base_dir, 'pet.py'))
    
    return candidates

def main():
    print("="*60)
    print("🦊 桌宠快捷方式生成器")
    print("="*60)
    
    # 获取程序路径
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 方案 1: 直接运行 Python 脚本
    python_script = os.path.join(base_dir, 'pet.py')
    python_exe = sys.executable
    target_path = f'"{python_exe}" "{python_script}"'
    
    # 方案 2: 如果有 run.bat
    batch_file = os.path.join(base_dir, 'run.bat')
    if os.path.exists(batch_file):
        print(f"\n📝 发现运行脚本：run.bat")
        use_batch = input("是否使用 run.bat 而不是直接运行 Python? (y/n): ").strip().lower()
        if use_batch == 'y':
            target_path = batch_file
    
    # 获取桌面路径
    desktop_path = get_desktop_path()
    shortcut_name = os.path.join(desktop_path, '桌宠 - 仙狐.lnk')
    
    print(f"\n📍 目标程序：{target_path}")
    print(f"📁 快捷方式位置：{shortcut_name}")
    
    # 显示可用的图标
    print("\n🎨 可用的图标:")
    icons = get_icon_candidates()
    if icons:
        for i, icon in enumerate(icons[:10], 1):  # 只显示前 10 个
            print(f"  {i}. {icon}")
        
        # 让用户选择图标
        choice = input(f"\n选择图标编号 (1-{len(icons)}), 或留空使用默认：").strip()
        if choice and choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(icons):
                icon_path = icons[idx]
            else:
                icon_path = None
                print("⚠️  无效的选择，使用默认图标")
        else:
            icon_path = None
            print("ℹ️  使用默认图标")
    else:
        icon_path = None
        print("  未找到自定义图标，将使用默认图标")
    
    # 询问是否覆盖
    if os.path.exists(shortcut_name):
        print(f"\n⚠️  快捷方式已存在：{shortcut_name}")
        overwrite = input("是否覆盖？(y/n): ").strip().lower()
        if overwrite != 'y':
            print("❌ 已取消")
            return
    
    # 创建快捷方式
    try:
        create_shortcut(
            target_path=target_path,
            shortcut_path=shortcut_name,
            icon_path=icon_path,
            description="桌宠 - 仙狐助手"
        )
        print("\n✨ 快捷方式创建成功！")
        print(f"📍 位置：{shortcut_name}")
        
        # 询问是否打开所在文件夹
        open_folder = input("\n是否打开快捷方式所在文件夹？(y/n): ").strip().lower()
        if open_folder == 'y':
            os.startfile(desktop_path)
        
    except Exception as e:
        print(f"\n❌ 创建失败：{e}")
        print("\n💡 提示:")
        print("  1. 请确保已安装 pywin32: pip install pywin32")
        print("  2. 请确保有权限在桌面创建文件")
        print("  3. 可以手动右键 pet.py → 创建快捷方式")

if __name__ == '__main__':
    main()
