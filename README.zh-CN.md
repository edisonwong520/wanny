# Wanny - 你的 AI 超级管家

[English README](./README.md) | 中文说明

Wanny 是一个连接微信与智能家居的“全能管家”系统。它不仅能通过微信控制米家设备，还集成 Gemini CLI 成为具备 Shell 操作能力的 AI Agent，并拥有长期记忆与主动关怀能力。

项目整体介绍、系统组成与架构总览可优先阅读 [2026-03-29-wanny-design.md](./docs/superpowers/specs/2026-03-29-wanny-design.md)。

本仓库主项目采用 [Apache License 2.0](./LICENSE)。`third_party/` 下的子仓库继续保留各自上游协议。

> 重要声明
>
> - 本项目仅供个人学习、研究、实验与非商业用途使用。
> - 本项目暂不提供 SaaS 托管服务，如需使用请自行部署。
> - 当前仍处于快速迭代阶段，目标是探索 AI 在设备控制、自动化、长期记忆与 Agent 执行上的更多可能性。
> - 由于项目迭代速度较快，当前阶段可能仍会存在不少 bug 和不完善之处，敬请理解。
> - 欢迎 Star、提 Issue，也欢迎直接贡献代码，一起接入更多物理设备与真实世界能力。
> - 请务必谨慎使用：AI 驱动的执行链路可能触发真实命令、影响真实设备或外部服务，并带来实际安全风险。
> - 你需要自行判断每一项接入、授权、自动化和执行动作是否适合当前环境。
> - 使用本项目即代表你理解并接受相关风险；对于因使用、误配置、自动化副作用、第三方平台变化或其他相关原因导致的损失、故障、异常或安全问题，仓库维护者不承担责任。

## 🌐 支持的平台

- **消息入口**: 微信
- **智能家居平台**: 米家、美的
- **出行平台**: 奔驰
- **自动化中枢**: Home Assistant

## 🖼️ 产品预览

### 微信交互示例

![WeChat Demo](./assets/readme/wechat-demo.jpg)

### 控制台面板

![Console Panel](./assets/readme/console-panel.jpg)

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
  /third_party       # 第三方源码参考区（仅用于对照、移植与致谢）
```

## 📖 项目文档

- 项目介绍与系统设计总览见 [2026-03-29-wanny-design.md](./docs/superpowers/specs/2026-03-29-wanny-design.md)。
- roadmap 见 [docs/ROADMAP.zh-CN.md](./docs/ROADMAP.zh-CN.md)。
- 详细专项设计、实施记录与规格说明位于 [`docs/superpowers/specs`](./docs/superpowers/specs)。

## ⚠️ 免责声明

- 本项目可能包含第三方依赖、第三方参考实现，或基于公开资料与社区项目整理出的协议兼容代码；相关知识产权、许可证与合规边界仍以各上游项目和服务提供方的条款为准。
- 某些平台接入能力可能依赖非官方接口、未公开 API、抓包分析、协议逆向或兼容性适配实现，例如智能家居平台云端接口对接。这类能力不代表得到相关平台官方认可，也不保证长期稳定可用。
- 若你使用与第三方平台账号、设备、App 或云服务相关的接入能力，请自行评估潜在风险，包括但不限于接口变更、账号风控、功能失效、服务条款限制或地区差异。
- 本项目默认将这些能力视为研究、学习、个人集成与兼容性探索用途；如需在生产环境、商业环境或面向终端用户的大规模场景中使用，请先完成必要的法律、合规、安全与许可证审查。
- 本项目属于试验性项目，且包含 AI 参与控制智能家电、自动化执行和外部平台联动等能力；请你在实际使用时保持谨慎，尤其留意通电设备、加热设备、门锁、传感器联动和无人值守场景中的潜在风险。
- 使用者应自行判断每一次接入、授权、自动化规则和控制指令是否安全、是否适合当前环境，并自行承担因误操作、配置不当、接口异常、设备异常或第三方服务变化带来的后果；与此相关的现实设备损失、人身风险、财产风险或平台问题，不应归责于本项目本身。

## 🖥️ 前端工作区

- `frontend/` 将承载官网 Landing Page 与后续的 Jarvis Console
- 当前前端技术路线为 Vue 3 + Vite + TypeScript + Tailwind CSS + shadcn-vue + vue-i18n
- 详细运行方式与目录说明请查看 `frontend/README.md`

## 🔐 安全与准则

- **隐私第一**: 核心逻辑本地化运行，敏感操作强制二次确认。
- **安全过滤**: 禁止执行 `sudo` 或危险的文件删除指令。
- **AI 规则链路**: 根目录 `README.md` 与 `README.zh-CN.md` 提供项目入口，根目录 `GEMINI.md` 管理通用规则，`backend/GEMINI.md` 与 `frontend/GEMINI.md` 分别管理领域规则。

## 🙏 第三方参考与致谢

- `third_party/midea_auto_cloud` 以 Git submodule 形式引入，作为美的接入的参考实现源码。上游协议为 Apache License 2.0。
- `third_party/mbapi2020` 以 Git submodule 形式引入，作为奔驰接入的参考实现源码。上游协议为 MIT License。
- 该仓库当前主要用于协议分析、字段映射与移植对照，不作为 Wanny 的运行时依赖。
- 致谢上游项目 [`sususweet/midea_auto_cloud`](https://github.com/sususweet/midea_auto_cloud) 提供的 Home Assistant 集成与相关实现思路。
- 致谢上游项目 [`ReneNulschDE/mbapi2020`](https://github.com/ReneNulschDE/mbapi2020) 提供的 Home Assistant 集成与相关实现思路。

## 🤖 AI 阅读入口

- AI 可优先阅读根目录 `README.md`（英文）或 `README.zh-CN.md`（中文），理解项目背景、目录结构与工作区边界。
- 通用 AI 规则位于根目录 `GEMINI.md`，这里定义跨前后端都适用的开发约束与行为规则。
- 后端专属规则位于 `backend/GEMINI.md`。
- 前端专属规则位于 `frontend/GEMINI.md`。
- 推荐阅读顺序：
  1. `README.md`
  2. `README.zh-CN.md`
  3. `GEMINI.md`
  4. `backend/GEMINI.md` 或 `frontend/GEMINI.md`

`GEMINI.md` 的作用是承载 AI rule，而不是项目介绍。项目说明、运行方式、背景信息和目录说明应继续保留在各自的 `README.md` 中。

### 美的映射巡检

- 后端提供 `uv run python manage.py audit_midea_mapping --limit 80`，用于扫描美的映射翻译后的高风险项。
- 这个巡检主要帮助发现“标签仍然过于原始”“选项文案未语义化”“底层状态字段泄漏到主界面”等问题，避免只能靠手动点设备页发现回归。
