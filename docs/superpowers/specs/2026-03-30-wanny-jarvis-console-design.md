# Wanny Jarvis Console 设计规范 v1.0

## 1. 目标 (Objectives)

Jarvis Console 是 Wanny 的运营中枢，不是单纯的展示型仪表盘。它的目标是把微信交互、设备调度、长期记忆、Shell 执行与安全门禁统一到一个可观察、可控制、可追溯的管理界面中。

Console 主要解决 4 个问题：

1. 让操作者快速知道 Jarvis 当前在忙什么、卡在什么地方、是否安全。
2. 让设备控制、审批流和主动关怀不再分散在微信聊天记录里。
3. 让记忆与画像成为可浏览、可确认、可修正的系统资产。
4. 让后续前端逐步承接更多“管理台”能力，并支持用户未来本地自部署、自管理。

## 2. 产品定位 (Product Positioning)

Jarvis Console 的定位是“Operator Cockpit”，服务的是 Jarvis 的主人，也就是系统的实际部署者、维护者和操作者，而不是普通访客。

它有两个核心特征：

- **运营台**：强调状态、队列、风险、执行结果与回放能力。
- **控制面**：强调批准、拒绝、重试、切换模式、更新策略等操作能力。

因此，Console 的设计原则应优先保证：

- 高信噪比
- 快速定位问题
- 重要操作有上下文和审计线索
- 所有自动化都能被看见、理解和必要时打断

## 3. 核心用户与场景 (Users & Scenarios)

### 3.1 核心用户

- **主人 / Operator**：日常使用 Console 管理 Jarvis，批准高风险任务，查看设备与建议，并在本地部署环境中自行维护系统状态。

### 3.2 典型场景

1. 用户通过微信下达复杂任务，Jarvis 需要人工批准再执行。
2. 设备状态异常，Jarvis 已发现但尚未采取动作，需要人工确认或调整策略。
3. 每日复盘生成了新的用户画像或主动建议，需要查看和校正。
4. Jarvis 最近行为异常，需要追查是 AI 决策、设备状态、权限矩阵还是外部接入出了问题。

## 4. 信息架构 (Information Architecture)

首版 Console 建议分为 5 个一级模块：

1. **Overview**
2. **Mission Desk**
3. **Device Fabric**
4. **Memory Atlas**
5. **Guard Rails**

后续可补第 6 个模块：

6. **Settings & Integrations**

---

## 5. 模块功能设计 (Module Design)

### 5.1 Overview

Overview 是首页，目标是在 10 秒内回答“现在系统情况如何”。

#### 5.1.1 必备功能

- **系统健康状态**
  - 微信 Bot 在线状态
  - 设备轮询服务状态
  - Daily Review 状态
  - 向量记忆引擎状态
  - AI Provider 状态
- **关键数字摘要**
  - 待审批任务数
  - 今日执行成功数 / 失败数
  - 今日主动建议数
  - 最近异常事件数
- **最近事件流**
  - 最近 10 条系统级事件
  - 包括设备异常、审批触发、Shell 执行完成、记忆复盘完成
- **当前模式**
  - 当前激活的 `HomeMode`
  - 当前总控策略（例如：Manual Gate / Semi Auto）

#### 5.1.2 设计重点

- 首页不承载复杂编辑能力，重点是“总览 + 跳转”。
- 每张摘要卡片都应能跳到对应模块的深层页面。

---

### 5.2 Mission Desk

Mission Desk 是 Jarvis 的任务控制台，负责管理来自微信与 AI 决策层的执行流。

#### 5.2.1 必备功能

- **待审批任务队列**
  - 来自微信的高风险任务
  - 显示原始消息、拟执行意图、风险等级、创建时间
  - 支持批准 / 拒绝 / 延后
- **任务详情抽屉**
  - 用户原始消息
  - AI 意图分类结果
  - 待执行命令或执行 Prompt
  - 风险说明
  - 相关历史上下文
- **执行历史**
  - 已批准任务
  - 已拒绝任务
  - 运行成功 / 失败记录
- **运行输出回放**
  - stdout / stderr
  - 执行耗时
  - 最终回复给用户的内容

#### 5.2.2 对应后端能力

- `comms` app 的微信消息接收与待执行指令缓存
- `ShellExecutor`
- `GeminiAgent / AIClient`

#### 5.2.3 首期交互动作

- Approve
- Reject
- Retry
- Copy command / prompt
- 跳转到相关记忆或相关设备上下文

---

### 5.3 Device Fabric

Device Fabric 是设备与场景控制的总览层，负责让 Jarvis 的“感知-决策-执行”闭环可视化。

#### 5.3.1 必备功能

- **设备总览**
  - 设备列表 / 卡片视图
  - 在线状态
  - 所属房间
  - 关键属性（如 power、温度、湿度、空气质量）
- **房间视图**
  - 按空间组织设备
  - 快速判断每个房间当前环境
- **场景模式面板**
  - 当前 `HomeMode`
  - 支持切换模式
  - 显示模式变更时间
- **策略矩阵**
  - 基于 `HabitPolicy` 显示 ASK / ALWAYS / NEVER
  - 支持按模式、设备、属性过滤
- **异常事件**
  - 例如 Away 模式下灯未关
  - 显示 Jarvis 的建议动作与当前判定依据

#### 5.3.2 二期功能

- 手动设备控制
- 自动化建议确认
- 观察计数器可视化（ObservationCounter）
- 房间级时间线

#### 5.3.3 对应后端能力

- `brain` app 中的 `HomeMode` / `HabitPolicy`
- 设备轮询与监控服务
- `devices` app 的状态读取与控制能力

---

### 5.4 Memory Atlas

Memory Atlas 是记忆与画像管理中心，目标是让“Jarvis 记得什么、为什么会这么判断”变得可见。

#### 5.4.1 必备功能

- **语义记忆浏览器**
  - 展示向量记忆命中结果
  - 支持按用户、时间、来源过滤
  - 支持搜索关键词
- **画像面板**
  - 展示 `UserProfile`
  - 按类别显示偏好（Environment / Habit / Device / Entertainment）
  - 显示置信度与最后确认时间
- **主动关怀记录**
  - 展示 `ProactiveLog`
  - 查看建议内容、评分、用户反馈
- **每日复盘概览**
  - 展示最近一次 Review 是否成功
  - 展示本次新增 / 修改的画像建议数量

#### 5.4.2 二期功能

- 人工确认或驳回画像更新
- 手动固定某条画像为“核心规则”
- 记忆召回对话可视化

#### 5.4.3 对应后端能力

- `memory.vector_store`
- `memory.services`
- `UserProfile`
- `ProactiveLog`
- `review.py`

---

### 5.5 Guard Rails

Guard Rails 是 Console 的安全中心，负责管理系统边界和自动化权限。

#### 5.5.1 必备功能

- **审批策略面板**
  - 当前系统是 Manual Gate 还是更自动化模式
  - 高风险任务是否强制审批
- **命令安全概览**
  - 最近被阻止的命令
  - 风险关键词命中统计
- **策略审计**
  - 谁批准了什么
  - 何时执行了什么
  - 是否产生异常
- **异常回退入口**
  - 对最近错误任务进行重试或转人工处理

#### 5.5.2 二期功能

- Allowlist / Denylist 可视化
- 更细粒度的 Shell 权限矩阵
- 不同任务类型的门禁策略模板

#### 5.5.3 对应后端能力

- `ShellExecutor` 的安全检查
- 审批缓存 / 执行日志
- `HabitPolicy` 与未来的自动化策略配置

---

### 5.6 Settings & Integrations（后续模块）

这个模块不建议在首期抢做，但应在架构上为本地部署用户预留。

#### 功能范围

- WeChat 接入状态
- Mijia 接入状态
- AI Provider 配置状态
- Review 调度配置
- 前后端版本与运行环境信息

这个模块应该偏“配置与健康检查”，不要和 Overview 混在一起。

## 6. MVP 范围建议 (What To Build First)

为了尽快把 Console 从“好看”推进到“可用”，建议按下面顺序落地：

### P0：必须先做

1. **Overview**
   - 系统状态卡片
   - 待审批数量
   - 最近事件流
2. **Mission Desk**
   - 待审批列表
   - 任务详情
   - 批准 / 拒绝动作
3. **Device Fabric**
   - 设备列表
   - 当前模式
   - 基础策略矩阵

### P1：第二阶段

1. **Memory Atlas**
   - 向量记忆浏览
   - 用户画像浏览
   - 主动建议日志
2. **Guard Rails**
   - 审批策略概览
   - 安全审计列表

### P2：第三阶段

1. Console 中的高级筛选与搜索
2. 更细的设备拓扑与房间维度视图
3. 画像确认与修正流
4. Settings & Integrations

## 7. 首版前端路由建议 (Frontend Routing)

建议首版前端路由如下：

- `/console`
  - Overview 首页
- `/console/missions`
  - Mission Desk
- `/console/devices`
  - Device Fabric
- `/console/memory`
  - Memory Atlas
- `/console/guard`
  - Guard Rails

Landing Page 保持在 `/`。

## 8. 首版页面结构建议 (UI Layout)

首版 Console 建议采用：

- **左侧固定导航**
  - 模块切换
  - 系统总状态
- **顶部全局栏**
  - 当前模式
  - 搜索
  - 快捷入口
- **主内容区**
  - 每个模块自己的卡片布局与明细表格
- **右侧上下文栏（可选）**
  - 近期事件
  - 当前审批
  - 快捷操作

这样做的好处是后续扩展不会推翻整体结构。

## 9. 与现有后端的映射 (Backend Mapping)

| Console 模块 | 对应后端 |
| --- | --- |
| Overview | `brain`, `comms`, `memory`, `devices` 的聚合状态 |
| Mission Desk | `comms`, `executor.py`, `ai.py` |
| Device Fabric | `brain.models`, `devices`, `monitor.py` |
| Memory Atlas | `memory.vector_store`, `memory.models`, `review.py` |
| Guard Rails | `comms` 待审批流、Shell 安全策略、策略矩阵 |

这意味着 Console 不应等待“一个全新的后端模块”才能开始写，而是可以从现有 app 上逐步拼装。

## 10. 下一步建议 (Next Step)

下一步建议不是继续扩写文案，而是直接进入 Console 的第一屏实现。

推荐实现顺序：

1. 先把 `/console` 做成真正的 **Overview**
2. 再拆出 `/console/missions` 和 `/console/devices`
3. 最后接入 `/console/memory` 与 `/console/guard`

这样做的原因是：

- Overview 最容易快速形成“可用感”
- Mission Desk 和 Device Fabric 最贴近当前后端已有能力
- Memory Atlas 与 Guard Rails 更适合作为第二批功能扩展
