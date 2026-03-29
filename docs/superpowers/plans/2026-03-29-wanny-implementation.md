# Wanny (Wechat+Nanny) 实施计划 v2.1

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个后端先行的智能管家，先跑通微信控制与硬件监控，最后补齐 Vue 3 前端。

**Architecture:** 后端采用 FastAPI + MySQL 8.0，AI 逻辑使用 LLM Agent 架构，前端采用 Vue 3 + Vite。

**Tech Stack:** Python, FastAPI, MySQL, MiCloud API, OpenAI/DeepSeek API, weclaw, Vue 3.

---

### Phase 1: 后端核心与硬件连接 (Backend Foundation)

#### Task 1: FastAPI 与 MySQL 基础环境
- **Files:**
    - Create: `backend/config.py`
    - Create: `backend/db/mysql_client.py`
    - Create: `backend/db/schema.sql`
- [ ] **Step 1**: 配置 `config.py` 读取环境变量（MySQL, API Keys）。
- [ ] **Step 2**: 编写 `schema.sql` 定义设备状态、习惯、聊天表。
- [ ] **Step 3**: 实现 `mysql_client.py` 处理基础 CRUD。
- [ ] **Step 4**: **验证**: 运行测试脚本，确保能连接 MySQL 并插入一条模拟设备记录。

#### Task 2: 小米云端 (MiCloud) 接入
- **Files:**
    - Create: `backend/providers/mi_cloud.py`
- [ ] **Step 1**: 使用 `micloud` 库实现登录逻辑。
- [ ] **Step 2**: 实现 `get_devices()` 获取全量设备列表。
- [ ] **Step 3**: 实现 `control_device()` 执行开关等操作。
- [ ] **Step 4**: **验证**: 编写 `test_micloud.py` 打印出家里的所有小米设备名称。

#### Task 3: 设备状态轮询 (Monitor Engine)
- **Files:**
    - Create: `backend/services/monitor.py`
- [ ] **Step 1**: 实现异步轮询任务，每 60 秒获取一次 MiCloud 设备状态。
- [ ] **Step 2**: 发现状态变化时，自动写入 `device_states` 表。
- [ ] **Step 3**: **验证**: 启动服务，手动开关物理设备，观察数据库中是否产生新记录。

---

### Phase 2: AI 大脑与微信收发 (AI & Wechat Loop)

#### Task 4: LLM Agent 集成
- **Files:**
    - Create: `backend/brain/agent.py`
- [ ] **Step 1**: 封装 OpenAI/DeepSeek SDK。
- [ ] **Step 2**: 编写 System Prompt，训练模型将自然语言转为设备控制 JSON（如 `{"action": "turn_on", "target": "light"}`）。
- [ ] **Step 3**: **验证**: 在终端输入“帮我关灯”，打印出对应的 JSON 指令。

#### Task 5: Weclaw 微信网关对接
- **Files:**
    - Create: `backend/api/wechat.py`
- [ ] **Step 1**: 编写 Webhook 接口接收 `weclaw` 的消息推送。
- [ ] **Step 2**: 串联 `LLM Agent` -> `MiCloud Provider`。
- [ ] **Step 3**: **验证**: 在手机微信发送“家里现在温度多少”，收到 Wanny 的回复。

---

### Phase 3: 记忆与主动逻辑 (Memory & Proactive)

#### Task 6: 记忆系统 (Context & Habits)
- **Files:**
    - Create: `backend/services/memory.py`
- [ ] **Step 1**: 实现基于 MySQL 的短期对话上下文管理。
- [ ] **Step 2**: 编写简单的 SQL 聚合逻辑，分析用户过去 7 天的开关灯时间。
- [ ] **Step 3**: **验证**: 连续询问两次，确保 Wanny 记得上一个问题的上下文。

#### Task 4: 主动提醒引擎 (Proactive Logic)
- **Files:**
    - Create: `backend/services/proactive_engine.py`
- [ ] **Step 1**: 在轮询过程中增加“规则匹配”。
- [ ] **Step 2**: 如果匹配到异常（如：空调开着且人离开 1 小时），调用 LLM 生成关怀文案并推送微信。
- [ ] **Step 3**: **验证**: 手动修改数据库模拟异常，观察微信是否收到主动推送。

---

### Phase 4: 前端展示 (Frontend - Final)

#### Task 8: Vue 3 初始化与 Landing Page
- [ ] **Step 1**: `npm create vite@latest frontend -- --template vue-ts`。
- [ ] **Step 2**: 设计 Landing Page，展示 Wanny 的全能管家特性。

#### Task 9: 管理后台与 WebSocket 实时监控
- [ ] **Step 1**: 实现 Dashboard 页面。
- [ ] **Step 2**: 后端 `main.py` 开启 WebSocket 服务。
- [ ] **Step 3**: 前端连接 WS，当 `MonitorEngine` 发现状态变化时，前端图标实时跳动。
