# Wanny AI Agent (Jarvis Shell) 设计规范 v1.0

## 1. 目标 (Objectives)
在 Wanny 现有的米家控制能力基础上，集成 Gemini CLI，使其成为具备执行 Shell 指令能力的智能管家。用户可以通过微信与 Jarvis 聊天，要求其查询天气、下载电影、管理文件等，所有涉及系统操作的指令均需经过用户手动确认（Manual-Gate）。

## 2. 核心逻辑 (Core Logic)

### 2.1 任务处理分类 (Task Classification)
- **简单询问 (Simple Queries)**: 
    - 对于天气查询、闲聊或简单的知识问答，Wanny 直接在后端构造 Prompt 并调用 AI 模型获取文本回复，无需经过 Shell 执行层。
- **复杂任务 (Complex Tasks)**: 
    - 涉及联网搜索、文件处理、电影下载等复杂操作时，Wanny 首先调用 AI 模型判断是否需要执行外部指令。
    - 若确定需要，则由 AI 生成具体的执行 Prompt，Wanny 通过命令行执行：`gemini -p 'Prompt' --yolo`。
    - **--yolo 模式**: 允许 Gemini 自动决定并执行多步 Shell 指令，赋予 Jarvis 极高的行动效率。

### 2.2 确认机制 (Manual-Gate)
- **内存存储**: 使用 Python 字典（Memory Cache）存储每个用户待确认的指令：
  `{ "user_id": { "cmd": "...", "timestamp": "..." } }`
- **确认触发**: 
    - 涉及 `--yolo` 或敏感 Shell 指令的操作，Wanny 会先通过微信向用户发送 `chat` 内容，并请求“批准”执行。
- **指令激活**: 用户回复“批准/Yes/OK/执行”等关键词时，触发指令运行。

## 3. 技术实现 (Technical Implementation)

### 3.1 环境配置 (.env)
- `GEMINI_API_KEY`: 用于调用 Gemini CLI。
- `AGENT_SYSTEM_PROMPT`: 预设的 Jarvis 人格和格式约束。

### 3.2 关键组件
- **`GeminiAgent`**: 封装 `subprocess` 调用，处理简单对话逻辑及复杂任务的意图识别。
- **`ShellExecutor`**: 负责执行 `--yolo` 命令或被批准的 Shell 指令，捕获 stdout/stderr。
- **`WeChatLogic`**: 在 `comms` app 中增加逻辑，区分普通对话和指令确认。

## 4. 安全防护与路线图 (Security & Roadmap)
- **关键词过滤**: 在执行前检查 `cmd`，禁止包含 `sudo` 等高危前缀。
- **--yolo 风险控制**: 由于 `--yolo` 权限极大，系统目前强制开启“用户确认门禁”。
- **未来演进**: 
    - **沙箱模式 (Sandbox)**: 计划引入 Restricted Shell 或独立用户空间执行。
    - **容器化执行 (Docker)**: 最终方案将所有 AI 生成的复杂指令放入独立的 Docker 容器中执行，实现物理级隔离，确保宿主机系统绝对安全。

## 5. 交互示例 (Example)
- **User**: "Sir, 帮我查下上海明天的天气。"
- **Jarvis**: "好的 Sir，我需要运行 `curl wttr.in/Shanghai` 来为您查询，请问是否批准？"
- **User**: "批准"
- **Jarvis**: (运行指令并回传天气预报文本) "Sir, 这是上海明天的天气预报：..."
