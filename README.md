# Wanny (Wechat + Nanny) - 你的 AI 超级管家

Wanny 是一个连接微信与智能家居的“全能管家”系统。它不仅能通过微信控制米家设备，还集成 Gemini CLI 成为具备 Shell 操作能力的 AI Agent，并拥有长期记忆与主动关怀能力。

## 🚀 核心能力

### 1. 智能家居控制 (Jarvis Brain)
- **感知-决策-执行**: 通过米家 API 实时监控设备状态，结合场景模式（HomeMode）自动优化家居环境。
- **观察学习**: 自动识别你的生活规律（如：离开家忘记关灯），并通过“确认制”交互进化为全自动助手。
- **权限矩阵**: 灵活配置每个场景下动作的授权状态（询问、总是、从不）。

### 2. AI 命令行代理 (Jarvis Shell)
- **自然语言交互**: 通过微信直接命令 Jarvis 执行任务（如：“查下明天上海天气”、“帮我下部科幻片”）。
- **简单/复杂任务分类**: 
  - 简单询问由后端直接构造 Prompt 获取回复。
  - 复杂任务通过 AI 生成 Prompt 并调用 `gemini --yolo` 模式执行多步 Shell 指令。
- **手动门禁 (Manual-Gate)**: 所有涉及系统操作的指令均需经过用户微信回复“批准”后方可执行。
- **安全路线图**: 规划引入 Sandbox 和 Docker 容器化执行，实现物理级安全隔离。

### 3. 长期记忆与主动关怀 (Memory & Proactive Care)
- **双轨制记忆**: 
  - **Memory A (语义向量)**: 记录所有对话片段，提供基于语义相似度的实时回想。
  - **Memory B (结构化画像)**: 自动提取并持久化你的核心偏好（如：习惯室温、观影习惯）。
- **每日复盘**: Jarvis 每天凌晨会自动复盘当天的交互，更新用户画像并进化建议算法。
- **主动建议**: 监测环境变化（如：降雨、PM2.5 超标）或基于习惯主动推送温馨提醒，避免过度打扰。

## 🛠️ 技术栈

- **后端**: Django 6.0 + Django Channels (WebSocket)
- **数据库**: MySQL + 向量数据库 (ChromaDB/FAISS)
- **AI 引擎**: Gemini CLI (`gemini`)
- **通讯**: WeChat iLink 协议 (`wechatbot-sdk`)
- **硬件对接**: Mijia API (`mijiaAPI`)
- **前端**: Vue 3 + Vite + TypeScript + Tailwind CSS + shadcn-vue + vue-i18n

## 📁 目录结构

```text
/wanny
  /backend           # Django 项目根目录
    /apps
      /brain         # LLM Agent 逻辑、决策中枢
      /comms         # 微信网关、消息路由
      /database      # 核心 ORM 模型与存储
      /memory        # 长期记忆、画像提取逻辑
      /devices       # 设备管理驱动
      /providers     # 第三方 API 接入
  /frontend          # Vue 3 前端工作区（Landing Page + Jarvis Console）
  /docs              # 详细设计规范与实施计划
```

## 🖥️ 前端工作区

- `frontend/` 将承载官网 Landing Page 与后续的 Jarvis Console
- 当前前端技术路线为 Vue 3 + Vite + TypeScript + Tailwind CSS + shadcn-vue + vue-i18n
- 详细运行方式与目录说明请查看 `frontend/README.md`

## 🔐 安全与准则

- **隐私第一**: 核心逻辑本地化运行，敏感操作强制二次确认。
- **安全过滤**: 禁止执行 `sudo` 或危险的文件删除指令。
- **单一真理来源**: 项目规范遵循 `GEMINI.md` 定义的架构原则。
