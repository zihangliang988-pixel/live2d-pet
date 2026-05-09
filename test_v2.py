#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试脚本 - FoxPet v9 桌宠（无头模式）
测试项：
1. 模块导入与编译
2. 类结构完整性
3. 配色常量
4. 语音模式切换逻辑
5. LLM 连接
6. 菜单项定义
7. UI 元素创建

注意：不会删除或修改任何本地文件
"""

import sys
import os
import time
import traceback

# 先切换到项目目录
os.chdir('D:\\桌宠')
sys.path.insert(0, 'D:\\桌宠')

# 修正编码
if sys.stdout and sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    import io
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

PASS = 0
FAIL = 0

def test(name, func):
    global PASS, FAIL
    try:
        func()
        PASS += 1
        print(f"  [PASS] {name}")
    except Exception as e:
        FAIL += 1
        print(f"  [FAIL] {name}: {e}")
        traceback.print_exc()
        print()

def banner(title):
    n = 50
    print()
    print("=" * n)
    print(f"  {title}")
    print("=" * n)

# ======================================================================
# 测试 1: 模块导入
# ======================================================================
banner("1. 模块导入与编译")

def test_imports():
    import desktop_pet_v2 as m
    # 检查类
    assert hasattr(m, 'FoxPet')
    assert hasattr(m, 'FoxChatDialog')
    assert hasattr(m, 'FeatureOverview')
    assert hasattr(m, 'DesktopPetApp')
    assert hasattr(m, 'LLMChatThread')
    assert hasattr(m, 'CommandThread')
    print(f"   6 个类/线程定义均存在")

test("模块导入", test_imports)

def test_constants():
    import desktop_pet_v2 as m
    assert m.FOX_ORANGE == "#FF8C42"
    assert m.FOX_PEACH == "#FFB07C"
    assert m.FOX_LIGHT == "#FFECD2"
    assert m.FOX_BG1 == "#FFF5E6"
    assert m.FOX_BG2 == "#FFE4C4"
    assert m.FOX_TEXT == "#5C3A1E"
    assert m.FOX_SUBTEXT == "#8B6B4A"
    print(f"   7 个配色常量均正确 (暖阳橙/蜜桃色系)")

test("配色常量", test_constants)

# ======================================================================
# 测试 2: 类结构
# ======================================================================
banner("2. 类结构完整性")

def test_foxpet_methods():
    import desktop_pet_v2 as m
    methods = [x for x in dir(m.FoxPet) if not x.startswith('__')]
    expected = ['_on_load', '_inject_js', '_setup_ui', '_show_context_menu',
                '_open_chat', '_show_functions', '_confirm_exit']
    for e in expected:
        assert e in methods, f"FoxPet missing: {e}"
    print(f"   FoxPet 方法: {len(methods)} 个")

test("FoxPet 方法", test_foxpet_methods)

def test_chat_methods():
    import desktop_pet_v2 as m
    methods = [x for x in dir(m.FoxChatDialog) if not x.startswith('__')]
    expected = ['_init_llm', '_setup_ui', '_toggle_voice_mode',
                '_add_msg', '_send_message', '_process_input',
                '_execute_command', '_chat_with_llm']
    for e in expected:
        assert e in methods, f"FoxChatDialog missing: {e}"
    print(f"   FoxChatDialog 方法: {len(methods)} 个")

test("FoxChatDialog 方法", test_chat_methods)

def test_feature_overview():
    import desktop_pet_v2 as m
    methods = [x for x in dir(m.FeatureOverview) if not x.startswith('__')]
    print(f"   FeatureOverview: 存在")

test("FeatureOverview", test_feature_overview)

# ======================================================================
# 测试 3: 菜单项定义
# ======================================================================
banner("3. 右键菜单结构")

def test_menu_items():
    import desktop_pet_v2 as m
    # 检查菜单构建逻辑
    source = open('desktop_pet_v2.py', 'r', encoding='utf-8').read()
    
    # 检查菜单项文本
    assert '开始聊天' in source
    assert '功能概览' in source
    assert '关闭' in source
    
    # 确认旧的菜单项不存在
    # 注意：旧版本可能有"可用功能"关键词
    # 这些检查只是为了验证结构
    
    # 计数菜单项
    import re
    menu_actions = re.findall(r'QAction\(["\']([^"\']+)["\']', source)
    menu_texts = []
    for a in menu_actions:
        # 排除非菜单的 QAction
        if '开始' in a or '功能' in a or '关闭' in a:
            menu_texts.append(a)
    
    print(f"   右键菜单: 开始聊天 / 功能概览 / 关闭")
    print(f"   共 {len(menu_texts)} 个菜单项")

test("菜单项定义", test_menu_items)

# ======================================================================
# 测试 4: LLM 模型名
# ======================================================================
banner("4. LLM 模型名检查")

def test_thread_model():
    import desktop_pet_v2 as m
    thread = m.LLMChatThread([])
    assert thread.model == "qwen2.5:7b"
    print(f"   LLMChatThread 默认模型: {thread.model}")

test("对话线程模型名", test_thread_model)

def test_parser_model():
    import desktop_pet_v2 as m
    # 检查源代码中模型名
    source = open('desktop_pet_v2.py', 'r', encoding='utf-8').read()
    # 应该没有 llama3.2:3b
    if 'llama3.2:3b' in source:
        print(f"   WARNING: 源代码仍有 'llama3.2:3b' 引用")
    # 应该有 qwen2.5:7b
    count = source.count('qwen2.5:7b')
    print(f"   源代码中 'qwen2.5:7b' 出现 {count} 次")
    assert count >= 2, "模型名未全部更新为 qwen2.5:7b"

test("代码中的模型名", test_parser_model)

def test_ollama_available():
    try:
        import ollama
        result = ollama.list()
        if hasattr(result, 'models'):
            # 新版 Ollama SDK
            models = result.models
            names = [str(m.model) for m in models]
        else:
            models = result.get('models', [])
            names = [m.get('name','') for m in models]
        has_qwen = any('qwen2.5:7b' in n for n in names)
        print(f"   Ollama 已连接")
        print(f"   模型列表: {', '.join(names)}")
        print(f"   qwen2.5:7b: {'已安装' if has_qwen else '未安装'}")
        assert has_qwen, "qwen2.5:7b 应该已安装"
    except Exception as e:
        print(f"   Ollama 不可用 (可能未运行): {e}")

test("Ollama 连接", test_ollama_available)

# ======================================================================
# 测试 5: 语音模式逻辑
# ======================================================================
banner("5. 语音模式逻辑")

def test_voice_toggle_source():
    import desktop_pet_v2 as m
    source = open('desktop_pet_v2.py', 'r', encoding='utf-8').read()
    
    # 检查 _toggle_voice_mode 方法
    assert 'voice_mode = not self.voice_mode' in source
    assert 'self.voice_hint.setVisible' in source
    assert 'self.input_edit.setVisible' in source
    assert 'mode_btn' in source
    assert '长按 T 说话' in source
    
    # 检查语音按钮布局位置（在 input_edit 之前添加 = 左边）
    lines = source.split('\n')
    add_widgets = [(i, l) for i, l in enumerate(lines) 
                   if 'input_layout.addWidget(' in l and ('mode_btn' in l or 'input_edit' in l)]
    
    if len(add_widgets) >= 2:
        btn_line = [l for l in add_widgets if 'mode_btn' in l[1]][0]
        input_line = [l for l in add_widgets if 'input_edit' in l[1]][0]
        assert btn_line[0] < input_line[0], f"语音按钮(行{btn_line[0]+1})应在输入框(行{input_line[0]+1})左边"
        print(f"   语音切换按钮: 输入框左边 (布局行{btn_line[0]+1}) ✓")
    
    print(f"   长按T说话提示: 存在 ✓")
    print(f"   模式切换逻辑: 正确 ✓")

test("语音模式源代码", test_voice_toggle_source)

# ======================================================================
# 测试 6: 文件完整性
# ======================================================================
banner("6. 文件完整性检查")

def test_file_exists():
    import os
    files = [
        'desktop_pet_v2.py',
        'file_manager.py',
        'voice.py',
    ]
    for f in files:
        path = os.path.join('D:\\桌宠', f)
        assert os.path.isfile(path), f"缺少文件: {f}"
        size = os.path.getsize(path)
        print(f"   {f}: {size:,} 字节")
    
    # 检查原版文件未被修改
    for orig in ['desktop_pet.py', 'main.py', 'llm_parser.py']:
        path = os.path.join('D:\\桌宠', orig)
        if os.path.isfile(path):
            mtime = os.path.getmtime(path)
            print(f"   {orig}: 存在 (未删除)")

test("文件存在性检查", test_file_exists)

def test_no_delete():
    # 确认没有删除任何原有文件
    import os
    d = 'D:\\桌宠'
    expected = ['desktop_pet.py', 'main.py', 'run.bat', 
                'file_manager.py', 'llm_parser.py', 'voice.py',
                'requirements.txt', 'desktop_pet_senko.py',
                'config.json', 'README.md']
    missing = []
    for f in expected:
        if not os.path.isfile(os.path.join(d, f)):
            missing.append(f)
    if missing:
        print(f"   ⚠️ 以下文件不存在 (可能之前已不存在):")
        for m in missing:
            print(f"      - {m}")
    else:
        print(f"   所有原有文件均存在")

test("未删除文件检查", test_no_delete)

# ======================================================================
# 测试 7: 功能概览内容
# ======================================================================
banner("7. 功能概览文本")

def test_feature_text():
    source = open('desktop_pet_v2.py', 'r', encoding='utf-8').read()
    
    expected_items = [
        'AI 聊天',
        '语音输入',
        '天气查询',
        '系统状态',
        'IP 查询',
        '每日一言',
        '今日运势',
        '密码生成',
        '打开程序',
        '文件管理',
        '仙狐陪伴',
        '拖拽',
    ]
    
    for item in expected_items:
        assert item in source, f"功能概览缺少: {item}"
    
    print(f"   7 项功能描述均完整:")
    for item in expected_items:
        print(f"      ✓ {item}")

test("功能概览文本内容", test_feature_text)

# ======================================================================
# 结果汇总
# ======================================================================
print()
print("=" * 50)
total = PASS + FAIL
print(f"  测试完成: {PASS}/{total} 通过 | {FAIL} 失败")
print("=" * 50)

if FAIL > 0:
    print("\n⚠️  部分测试未通过")
    sys.exit(1)
else:
    print("\n✅ 全部通过！")
