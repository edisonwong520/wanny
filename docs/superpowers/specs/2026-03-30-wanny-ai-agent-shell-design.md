# Wanny AI Agent (Jarvis Shell) 设计规范 v1.0

## 1. 目标 (Objectives)
在 Wanny 现有的米家控制能力基础上，集成 Gemini CLI，使其成为具备执行 Shell 指令能力的智能管家。用户可以通过微信与 Jarvis 聊天，要求其查询天气、下载电影、管理文件等，所有涉及系统操作的指令均需经过用户手动确认（Manual-Gate）。

## 2. 核心逻辑 (Core Logic)

### 2.1 交互架构 (Interaction Architecture)
- **AI 引擎**: 通过命令行调用 `gemini -p '...'` 获取响应。
- **输出格式**: 强制要求 Gemini 输出纯 JSON 格式：
  ```json
  {
    "chat": "给用户的微信回复文案",
    "cmd": "待执行的 Bash 指令 (若无则为 null)"
  }
  ```
- **执行环境**: 运行在 macOS/Linux 服务器上，拥有常用 CLI 工具（brew, curl, ffmpeg 等）权限。

### 2.2 确认机制 (Manual-Gate)
- **内存存储**: 使用 Python 字典（Memory Cache）存储每个用户待确认的指令：
  `{ "user_id": { "cmd": "...", "timestamp": "..." } }`
- **确认触发**: 当 Gemini 返回 `cmd` 不为 null 时，Wanny 发送 `chat` 内容，并将 `cmd` 存入内存。
- **指令激活**: 用户回复“批准/Yes/OK/执行”等关键词时，触发指令运行。

## 3. 技术实现 (Technical Implementation)

### 3.1 环境配置 (.env)
- `GEMINI_API_KEY`: 用于调用 Gemini CLI。
- `AGENT_SYSTEM_PROMPT`: 预设的 Jarvis 人格和格式约束。

### 3.2 关键组件
- **`GeminiAgent`**: 封装 `subprocess` 调用，处理 JSON 解析与容错。
- **`CommandHandler`**: 负责执行被批准的 Shell 指令，捕获 stdout/stderr。
- **`WeChatLogic`**: 在 `comms` app 中增加逻辑，区分普通对话和指令确认。

## 4. 安全防护 (Security)
- **关键词过滤**: 在执行前检查 `cmd`，禁止包含 `sudo`, `rm -rf /` 等高危指令。
- **超时失效**: 内存中的指令默认 10 分钟后失效，防止误操作。
- **只读预览**: 指令执行前会完整通过微信展示给用户看。

## 5. 交互示例 (Example)
- **User**: "Sir, 帮我查下上海明天的天气。"
- **Jarvis**: "好的 Sir，我需要运行 `curl wttr.in/Shanghai` 来为您查询，请问是否批准？"
- **User**: "批准"
- **Jarvis**: (运行指令并回传天气预报文本) "Sir, 这是上海明天的天气预报：..."
