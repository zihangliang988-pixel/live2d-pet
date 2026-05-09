#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
桌宠主程序入口 - Senko Live2D 桌宠 v9.1
"""
import sys, os, traceback

# 先写错误日志
log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'error.log')
sys.stderr = open(log_file, 'w', encoding='utf-8')

os.chdir(os.path.dirname(os.path.abspath(__file__)))

# 设置 QtWebEngine 缓存到纯 ASCII 路径
cache_dir = os.path.join(os.environ.get('TEMP', 'C:\\temp'), 'SenkoPet_Cache')
os.makedirs(cache_dir, exist_ok=True)

os.environ['QTWEBENGINE_DISABLE_SANDBOX'] = '1'
os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = '--no-sandbox'

try:
    from desktop_pet import DesktopPet
except Exception as e:
    with open(log_file, 'a') as f:
        f.write(f'Import error: {e}\n{traceback.format_exc()}\n')
    sys.exit(1)


def main():
    try:
        sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)
    except Exception:
        pass

    print("=" * 50)
    print("[Senko] 桌宠助手 v9.1")
    print("=" * 50)
    print()
    print("正在启动...")

    try:
        pet = DesktopPet()
        sys.exit(pet.run())
    except KeyboardInterrupt:
        print("\n桌宠已退出")
    except Exception as e:
        with open(log_file, 'a') as f:
            f.write(f'Runtime error: {e}\n{traceback.format_exc()}\n')
        print(f"\n错误：{e}")
        traceback.print_exc()
        input("\n按回车键退出...")


if __name__ == "__main__":
    main()
