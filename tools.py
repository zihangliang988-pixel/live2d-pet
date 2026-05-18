#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
桌宠工具层 - 统一管理所有技能
"""

import json
import os
import re
import urllib.request
import urllib.parse
import subprocess
import platform
import random
import datetime

# ======================================================================
# 工具注册表
# ======================================================================
_tool_registry = {}

def register_tool(name, description, parameters, fn):
    """注册一个工具"""
    _tool_registry[name] = {
        "name": name,
        "description": description,
        "parameters": parameters,
        "fn": fn,
    }

def get_ollama_tools():
    """返回 Ollama tools 格式的列表"""
    tools = []
    for name, t in _tool_registry.items():
        tools.append({
            'type': 'function',
            'function': {
                'name': t['name'],
                'description': t['description'],
                'parameters': t['parameters'],
            }
        })
    return tools

def execute_tool_call(tool_call):
    """执行单个 Ollama tool_call，返回结果字符串"""
    name = tool_call['function']['name']
    args = json.loads(tool_call['function']['arguments'])
    
    if name in _tool_registry:
        try:
            result = _tool_registry[name]['fn'](**args)
            # 直接返回结果，不要嵌套在 {"result": ...} 中
            if isinstance(result, dict):
                return json.dumps(result, ensure_ascii=False)
            return str(result)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)
    return json.dumps({"error": f"未知工具：{name}"})


# ======================================================================
# 工具实现
# ======================================================================

# ---- 1. 天气查询 ----
def _weather(city: str = "北京"):
    """获取城市天气"""
    try:
        encoded = urllib.parse.quote(city)
        url = f"https://wttr.in/{encoded}?format=%C|%t|%w|%h|%p"
        req = urllib.request.Request(url, headers={'User-Agent': 'curl/8.0'})
        with urllib.request.urlopen(req, timeout=8) as resp:
            raw = resp.read().decode('utf-8').strip()
        parts = raw.split('|')
        return {
            "city": city,
            "weather": parts[0] if len(parts) > 0 else "未知",
            "temp": parts[1] if len(parts) > 1 else "未知",
            "wind": parts[2] if len(parts) > 2 else "未知",
            "humidity": parts[3] if len(parts) > 3 else "未知",
        }
    except Exception as e:
        return {"city": city, "error": str(e)}

register_tool(
    "get_weather",
    "查询指定城市的实时天气",
    {
        "type": "object",
        "properties": {
            "city": {"type": "string", "description": "城市名，如 北京、上海、东京"}
        },
        "required": ["city"]
    },
    _weather
)


# ---- 2. 系统状态 ----
def _sysinfo():
    """获取系统状态"""
    try:
        # CPU
        cpu_pct = "未知"
        try:
            import psutil
            cpu_pct = f"{psutil.cpu_percent(interval=0.1)}%"
        except ImportError:
            cpu_pct = "需安装 psutil"
        
        # 内存
        mem_info = "未知"
        try:
            import psutil
            mem = psutil.virtual_memory()
            total_gb = mem.total / (1024**3)
            used_gb = mem.used / (1024**3)
            mem_info = f"{used_gb:.0f}GB/{total_gb:.0f}GB ({mem.percent}%)"
        except ImportError:
            mem_info = "需安装 psutil"
        
        # 系统
        sys_name = platform.system()
        sys_ver = platform.release()
        
        return {
            "system": f"{sys_name} {sys_ver}",
            "cpu": cpu_pct,
            "memory": mem_info,
        }
    except Exception as e:
        return {"error": str(e)}

register_tool(
    "get_system_info",
    "获取电脑系统状态（操作系统、CPU使用率、内存占用）",
    {
        "type": "object",
        "properties": {}
    },
    _sysinfo
)


# ---- 3. IP / 归属地 ----
def _myip():
    """获取本机外网 IP"""
    try:
        req = urllib.request.Request(
            'https://httpbin.org/ip',
            headers={'User-Agent': 'curl/8.0'}
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())
        ip = data.get('origin', '未知')
        
        # 反向查归属地
        try:
            req2 = urllib.request.Request(
                f'https://ipapi.co/{ip}/json/',
                headers={'User-Agent': 'curl/8.0'}
            )
            with urllib.request.urlopen(req2, timeout=5) as resp2:
                loc = json.loads(resp2.read())
            return {
                "ip": ip,
                "city": loc.get('city', ''),
                "region": loc.get('region', ''),
                "country": loc.get('country_name', ''),
                "isp": loc.get('org', ''),
            }
        except Exception:
            return {"ip": ip}
    except Exception as e:
        return {"error": str(e)}

register_tool(
    "get_my_ip",
    "查询本机的外网 IP 地址和归属地信息",
    {
        "type": "object",
        "properties": {}
    },
    _myip
)


# ---- 4. 每日一言 ----
_quotes = [
    "今天也要元气满满哦！🦊✨",
    "每一个不曾起舞的日子，都是对生命的辜负。",
    "世界那么大，你值得去看看。",
    "累了就休息一下，仙狐会陪着你的。",
    "不要着急，最好的总在不经意间出现。",
    "生活就像一杯茶，不会苦一辈子。",
    "你已经很棒了，比昨天的自己更好。",
    "微笑是最美的语言，今天也要多笑笑哦~",
    "人生没有白走的路，每一步都算数。",
    "去做你想做的事，成为你想成为的人。",
    "温柔的人，运气都不会太差。",
    "今天是全新的一天，一切都会好起来的！",
]

def _quote():
    """随机一句励志语录"""
    return random.choice(_quotes)

register_tool(
    "get_daily_quote",
    "获取一句随机的励志语录或心灵鸡汤",
    {
        "type": "object",
        "properties": {}
    },
    _quote
)


# ---- 5. 今日运势 ----
def _fortune():
    """赛博占卜"""
    luck = random.randint(1, 100)
    if luck >= 90:
        level = "大吉 🎉"
        advice = "今天运气爆棚，放手去做吧！"
    elif luck >= 70:
        level = "吉 🌟"
        advice = "适合尝试新事物，会有不错的收获~"
    elif luck >= 40:
        level = "中吉 👍"
        advice = "平平淡淡才是真，稳中求进。"
    elif luck >= 20:
        level = "小凶 🌧"
        advice = "今天宜低调，注意保管好随身物品。"
    else:
        level = "大凶 ⚠️"
        advice = "不宜做重大决定，喝杯热水缓缓。"
    
    colors = ["红色", "橙色", "蓝色", "绿色", "紫色", "白色"]
    numbers = [str(random.randint(1, 50)) for _ in range(3)]
    
    return {
        "luck_score": luck,
        "level": level,
        "advice": advice,
        "lucky_color": random.choice(colors),
        "lucky_numbers": numbers,
    }

register_tool(
    "get_daily_fortune",
    "获取今日运势占卜（运气评分、建议、幸运色、幸运数字）",
    {
        "type": "object",
        "properties": {}
    },
    _fortune
)


# ---- 6. 定时提醒（简化：返回提醒文案，由前端弹窗） ----
# 注意：实际定时器需要 Qt 主线程处理，这里只做解析
def _remind(text: str, minutes: int = 5):
    """设置定时提醒"""
    return {
        "text": text,
        "minutes": minutes,
        "message": f"好的，{minutes}分钟后提醒你：{text}"
    }

register_tool(
    "set_reminder",
    "设置一个定时提醒，指定提醒内容",
    {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "提醒内容"},
            "minutes": {"type": "integer", "description": "多少分钟后提醒（默认5分钟）"}
        },
        "required": ["text"]
    },
    _remind
)


# ---- 7. 随机密码生成 ----
def _password(length: int = 16):
    """生成随机密码"""
    import secrets
    import string
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    pwd = ''.join(secrets.choice(chars) for _ in range(length))
    return {"password": pwd, "length": length}

register_tool(
    "generate_password",
    "生成一个随机强密码",
    {
        "type": "object",
        "properties": {
            "length": {"type": "integer", "description": "密码长度（默认16位）"}
        },
        "required": []
    },
    _password
)


# ======================================================================
# 工具列表
# ======================================================================
def list_tools():
    """列出所有已注册的工具"""
    result = []
    for name, t in _tool_registry.items():
        result.append({
            "name": t["name"],
            "description": t["description"],
        })
    return result


if __name__ == "__main__":
    print("已注册工具:")
    for t in list_tools():
        print(f"  - {t['name']}: {t['description']}")
