# 仙狐桌宠 🦊

一个基于 Live2D + AI 的桌面宠物，会说话、会卖萌、能帮你管理文件。

![version](https://img.shields.io/badge/version-9.0-orange)
![python](https://img.shields.io/badge/python-3.8+-blue)
![license](https://img.shields.io/badge/license-MIT-green)

---

## 功能概览

**🐾 桌面交互**
- Live2D 仙狐形象（Senko 模型，CDN 加载）
- 左键拖动移动、右键菜单快捷操作
- 双击打开聊天对话框
- 半透明玻璃底座 + 在线状态指示

**💬 AI 对话**
- 接入本地 Ollama（qwen2.5:7b），完全离线
- 角色扮演：温柔元气的仙狐，会关心人也会撒娇
- 打字指示器动画 + 渐入气泡消息
- 对话历史管理（自动截断，不超过 20 轮）

**🔧 工具系统**
- 天气查询（wttr.in，支持任何城市）
- 系统状态（CPU / 内存 / 系统信息）
- 外网 IP 查询 + 归属地
- 每日一言 / 今日运势
- 随机密码生成
- 定时提醒

**📁 文件管理**
- 打开文件 / 文件夹 / 应用程序
- 创建文件或文件夹
- 删除到回收站（带二次确认）
- 移动、重命名、查看文件信息
- 桌面快捷方式自动解析
- 支持模糊搜索（2 层目录深度）

**🎤 语音交互**
- T 键按住说话，松开识别
- 语音转文字输入（Google Speech API）
- 系统 TTS 朗读回复

---

## 快速开始

### 前置条件

1. 安装并运行 [Ollama](https://ollama.com/)
2. 拉取模型：
```bash
ollama pull qwen2.5:7b
```

### Windows 一键安装

双击 `install.bat`，或手动执行：

```bash
cd D:\桌宠
pip install -r requirements.txt
python pet.py
```

### 依赖说明

| 依赖 | 说明 | 可选 |
|------|------|------|
| PyQt5 | GUI 框架 | 必选 |
| PyQtWebEngine | Live2D WebView 渲染 | 必选 |
| ollama | LLM 本地推理 | 必选 |
| SpeechRecognition | 语音识别 | 可选 |
| pyaudio | 麦克风输入 | 可选（语音需装） |
| pywin32 | Windows 快捷方式解析 | 可选 |
| psutil | 系统状态监控 | 可选 |
| keyboard | 全局按键监听 | 可选（语音需装） |

---

## 使用说明

### 鼠标操作

| 操作 | 效果 |
|------|------|
| 左键拖动 | 移动桌宠位置 |
| 左键双击 | 打开聊天对话框 |
| 右键点击 | 快捷菜单（夸夸 / 笑话 / 运势 / 关闭） |

### 命令示例

直接打字或用语音说：

```
"今天天气怎么样"
"帮我打开记事本"
"打开丑橘文件夹"
"删除大愁居.txt"
"查看我的IP"
"生成一个16位密码"
"5分钟后提醒我喝水"
"给我讲个笑话"
"查一下系统状态"
```

支持口语化表达，系统会自动清洗后交给 AI 解析。

### 语音模式

按下 **T 键** 开始录音，松开识别。需要安装 `pyaudio` 和 `keyboard`。

---

## 项目结构

```
桌宠/
├── pet.py                 # 主程序入口（~1700行）
│   ├── FoxPet             # 桌宠主窗口（Live2D + 交互）
│   └── FoxChatDialog      # 聊天对话框（AI 对话 + 命令执行）
│
├── llm_parser.py          # 命令解析器
│   ├── LLMCommandParser   # Ollama 解析 + 正则回退
│   └── preprocess_input   # 输入清洗（去除废话、转换句式）
│
├── tools.py               # 工具注册系统
│   ├── register_tool      # 工具注册装饰器
│   ├── get_ollama_tools   # 导出 Ollama tools 格式
│   └── execute_tool_call  # 工具执行器
│
├── file_manager.py        # 文件管理器
│   ├── 文件/文件夹增删改查
│   ├── 应用程序查找与启动
│   ├── 桌面快捷方式解析
│   └── 回收站安全删除
│
├── voice.py               # 语音处理（STT + TTS）
│
├── character.json         # 角色设定（性格、语气、行为规则）
├── config.json            # 用户偏好配置
│
├── assets/                # 图标资源
└── live2d-viewer/         # Live2D 模型文件（CDN 为主）
```

## 技术栈

| 技术 | 用途 |
|------|------|
| Python 3.8+ | 主语言 |
| PyQt5 | GUI + 事件循环 |
| PyQtWebEngine | Live2D WebView 渲染 |
| Ollama (qwen2.5:7b) | 本地 LLM 推理 |
| JSON-RPC tool calling | 结构化工具调用 |
| 双通道解析 (LLM + 正则) | 命令理解 + 降级兜底 |
| SHFileOperationW API | 回收站安全删除 |
| ChromaDB (可选) | 知识库 / RAG 支持 |

---

## 设计特点

**命令解析流水线**：
```
用户输入 → 预处理清洗 → LLM 解析 → JSON 提取 → 文件系统校验 → 执行
                                         ↓ 失败
                                    正则回退 → 执行
```

**安全措施**：
- 删除操作必须二次确认
- 删除走系统回收站（可恢复）
- 路径遍历攻击防护（sanitize_target）
- 文件搜索超时保护（5 秒自动放弃）

---

## 许可证

MIT
