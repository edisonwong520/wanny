# Wanny Backend Rules

本文件只记录后端开发规则。处理后端任务时，除根目录 `README.md` 与根目录 `GEMINI.md` 外，还必须阅读本文件。

## 1. 技术栈与基础约束

- 核心框架：Python + Django
- 包管理工具：必须优先使用 `uv`，例如 `uv add`、`uv run`
- 配置与鉴权：禁止硬编码 API Key、数据库密码等敏感信息；必须通过 `.env` 配置并用 `os.getenv` 读取
- 时区与时间：数据库、后台逻辑和业务代码统一使用北京时间 `Asia/Shanghai`

## 2. 后端开发规范

- Mac 环境下若 `uv sync` 遇到 `mysqlclient` 编译错误，可安装 `brew install mysql-client pkg-config`
- 之后设置环境变量：`export PKG_CONFIG_PATH="/opt/homebrew/opt/mysql-client/lib/pkgconfig"`
- 严禁使用 `print()` 输出运行日志，必须统一使用项目 `logger`
- 日志必须能定位到具体文件名和代码行号，并同时支持控制台与文件输出

## 3. 智能体与编排

- 关注 AI 分析、多 Agent 协同和后台异步任务的完整性，避免数据丢失
- 所有直接调用或实例化 AI 模型的代码，必须抽象为统一类，例如 `AIClient` 或 `AIAgent`
- 统一 AI 客户端至少要兼容两种模式：
  - 通过 `GEMINI_API_KEY` 连接官方 Gemini
  - 通过 `AI_BASE_URL`、`AI_API_KEY`、`AI_MODEL` 走 OpenAI 兼容协议
- 调用方不应直接感知底层 SDK，切换模型来源时应尽量无感

## 4. 第三方平台接入

### 4.1 微信 iLink 协议

- 参考文档：https://www.wechatbot.dev/zh/python
- 主要包名：`wechatbot-sdk`
- 监听回调必须基于 Async/Await，消息入口使用 `@bot.on_message`
- 回复消息使用 `bot.reply()`
- 运行时由 bot 接管底层 WebSocket 事件循环

### 4.2 小米 / 米家 API

- 参考文档：https://github.com/Do1e/mijia-api
- 主要包名：`mijiaAPI`
- 任何设备交互前必须先完成 `api.login()`，并复用/缓存认证数据
- 严禁自行构造底层协议请求，优先通过 `mijiaDevice(api, dev_name="特定名称")` 进行设备抽象操作
- 读写属性使用 `get()` / `set()`，动作调用使用 `run_action()`
