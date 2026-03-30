# Wanny Project Rules (GEMINI.md)

作为 AI 助手，在协助开发 Wanny 项目时，每次交互都**必须**严格阅读并遵守以下规则。如果你感受到有新的开发模式、最佳实践或新的要求，请主动提示我，或者请求直接将相关规则更新到此文件 (`GEMINI.md`) 中。

## 1. 文档定位 (Document Purpose)

- **唯一准则**：`GEMINI.md` 仅用于记录 **规则约束、开发规范与 AI 行为准则**。
- **严禁包含项目介绍**：禁止在本文件中记录项目背景、业务逻辑介绍、功能说明等非规范性内容。
- **项目说明归宿**：所有关于项目背景、API 文档、安装指南等内容必须记录在各自目录的 `README.md` 中。AI 在需要了解项目背景时应优先阅读对应目录的 README。

## 2. 目录规范与测试代码要求 (Directory & Testing Standards)

- **测试用例管理（强制要求）**：**所有**生成的测试用例、测试脚本、验证连接用的小脚本（如 API 测试、集成验证），**绝对不允许**随意放置在根目录或业务逻辑代码旁。它们必须被放入模块专属的 `tests/` 目录下（例如 `backend/tests/`），以免污染主代码库。
- **文件命名风格**：测试文件必须以 `test_*.py` 命名，以便测试框架能够自动识别和执行。
- **前端工作区约束**：所有前端页面、组件、样式和构建配置必须统一放置在根目录的 `frontend/` 工作区；前端的运行与安装说明应记录在 `frontend/README.md` 中。

## 3. 技术栈与开发规范 (Tech Stack & Guidelines)

在生成代码或方案时，请严格遵守以下技术栈，避免随意引入未经确认的其他依赖：

### 3.1 后端 (Backend)
- **核心框架**：Python + Django
- **包管理工具**：必须优先使用 `uv`（例如：使用 `uv add xx` / `uv run xx`），避免使用纯粹的 pip 从而保持项目依赖锁定和一致。
- **Mac 环境下的 mysqlclient 安装**：如果在 Mac 上执行 `uv sync` 时遇到 `mysqlclient` 编译错误（`pkg-config` 无法找到 `mysqlclient`），请确保已安装 `brew install mysql-client pkg-config`，并在执行前设置环境变量：`export PKG_CONFIG_PATH="/opt/homebrew/opt/mysql-client/lib/pkgconfig"`。建议将其加入 `~/.bash_profile` 或 `~/.zshrc` 中。
- **配置与鉴权**：禁止硬编码（Hardcoding）API Keys、数据库密码等敏感信息或特定环境相关配置。必须统一通过 `.env` 获取并通过 `os.getenv` 读取。
- **时区与时间**：数据库、后台逻辑和所有的业务代码必须统一且严格地使用 **北京时间 (UTC+8, Asia/Shanghai)**，**严禁混用或使用 UTC 进行任何处理**。在 Django 配置中，`TIME_ZONE` 必须设定为 `'Asia/Shanghai'` 并且统一使用此本地时间进行储存与计算。
- **统一日志与精准排错 (Logging & Debugging)**：
  - **严禁使用 `print()`** 打印任何控制台日志内容。必须统一引入并调用本项目的封装 `logger`（参考：`from utils import logger` / `from utils.logger import logger`）。
  - **必备精准格式**：所有的调试以及运行日志在输出时，必须明确带上所被触发的**具体文件名（所在哪个文件）和代码行号（排查用报错所在的第几行）**。其本质原因是为了在后续极高频迭代修改和定位异常问题时可以一秒追溯，缩短一切除虫成本与沟通精力。日志需要实现控制台与文件（如 `logs/wanny.log`）的双端同步写入。

### 3.2 智能体与编排 (Agents & Orchestration)
- **设计模式**：关注 AI 分析、多 Agent 之间的协同流转（如 Mem0 集成、Gemini 分析等），需确保数据的完整性与防丢（结合 Celery 或其他异步队列完成后台高耗时任务）。
- **AI 客户端抽象规范**：由于大模型服务多变，所有**直接调用**或**实例化** AI 模型的代码必须抽象为**统一的类 (如 `AIClient` 或 `AIAgent`)**。该类至少要兼顾支持两种连接方式：
  1. 通过原生的 `GEMINI_API_KEY` (结合 `google-generativeai` 包) 连接官方 Gemini。
  2. 通过 OpenAI 兼容协议 (结合 `AI_BASE_URL`, `AI_API_KEY`, `AI_MODEL` 和 `openai` 包) 连接第三方模型代理或本地大模型。
  调用方不应感知底层 SDK，且能根据环境变量平滑切换。

### 3.3 前端 (Frontend)
- **框架与构建**：Vue 3、Vite、TypeScript；Node 推荐使用 `24.11.1`，至少保持在兼容的现代 LTS 版本。
- **样式系统**：Tailwind CSS
- **UI 组件库**：必须使用 **shadcn-vue** 作为核心基础组件方案
- **国际化**：使用 **vue-i18n**，且默认支持中文与英文
- **响应式布局**：所有前端页面、组件必须默认采用自适应布局（Responsive Design），确保桌面与移动端均可用
- **主题方向**：默认采用浅色主题，不以深色主题作为主视觉；整体气质应融合微信的国民级易用性与 AI 管家的科技感
- **品牌主色**：`#07C160`（微信绿）作为品牌主强调色，仅用于关键按钮、状态高亮和 AI 运行标识
- **基础色板**：主背景 `#F7F7F7`、面板 `#FFFFFF`、一级文本 `#191919`、二级文本 `#999999`、AI 光晕辅助色 `#E1F8EA`
- **科技感表达**：通过局部光晕、轻毛玻璃和克制的动态背景表达 AI“生命力”，严禁使用大面积高饱和霓虹光效
- **审美底线**：必须追求极其卓越的高级视觉质感，使用现代 Web 设计最佳实践（例如采用浅色极简、通透玻璃拟态与克制的 AI 光晕效果）。不允许生成看起来像“玩具”的平庸界面。
- **交互设计**：强制要求丰富的微交互与过渡动画。组件必须提供恰当的悬停（Hover）、点击（Active）和 Focus 反馈。
- **字体排印**：必须使用主流现代西文字体（如 Inter, Roboto）与美观的中文字体配置。禁止使用纯黑色 `#000` 或纯白 `#fff`，应该倾向于使用精心配比的高级中性色阶。

## 4. Git 代码提交流程 (Commit Guidelines)

为了能够准确追踪 AI 生成与人类手动微调的改动，项目需要遵从如下管理：
- 使用结构化的 Commit Message（如 `feat:`, `fix:`, `refactor:`, `test:` 等前缀）。
- 涉及到 AI 的自主决策更新代码时，推荐在日志中带上 AI 的标记，以便未来追溯。
- 添加依赖后（`uv add`），务必提交锁文件更新（`uv.lock` 和 `pyproject.toml`）。

## 5. 项目持续迭代与扩充 (Self-Improvement)

- 这并不是一份一次性文件。如果在后续开发中，存在新的重要架构决策（如新引入了一套智能家居 API 规则、消息队列改换等），AI **必须主动**将新规范更新至 `GEMINI.md` 的内容，保证其始终作为该项目的“单一真理来源 (Single Source of Truth)”。

## 6. 第三方 API 与生态对接参考 (Third-party Integrations)

当需要编写或修改外部物联网设备、社交平台代理相关的代码时，AI 在生成代码前必须优先参考以下官方约定及已验证的封装机制：

- **社交代理与系统自动回复 (微信 iLink 协议)**：
  - **参考文档**: [https://www.wechatbot.dev/zh/python](https://www.wechatbot.dev/zh/python)
  - **主要包名**: `wechatbot-sdk`
  - **开发规范**: 基于 Async/Await 机制。监听回调必须使用 `@bot.on_message` 装饰器；发送回复使用 `bot.reply()` 方法；需使用 `bot.run()` 接管底层 WebSocket 事件循环及提供扫码登录。

- **智能家居物联网层控 (米家 Mijia API)**：
  - **参考文档**: [https://github.com/Do1e/mijia-api](https://github.com/Do1e/mijia-api)
  - **主要包名**: `mijiaAPI`
  - **开发规范**: 任何设备交互前必须进行 `api.login()` 获取/缓存 Token；严禁自行构造底层协议请求，统一使用 `mijiaDevice(api, dev_name="特定名称")` 类抽象来对接（读写属性用 `get()/set()`，动作操作用 `run_action()`）。
