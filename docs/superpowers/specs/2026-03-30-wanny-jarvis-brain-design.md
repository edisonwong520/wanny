# Wanny Jarvis Brain 设计规范 v1.0

## 1. 目标 (Objectives)
构建一个具备“感知-决策-执行”闭环能力的智能管家（Jarvis）。系统通过米家 API 监控设备状态，结合预设场景模式（HomeMode）进行主动关怀，并通过微信与用户进行“确认制”交互，最终通过观察学习进化为全自动助手。

## 2. 核心架构 (Core Architecture)

### 2.1 状态感知层 (Perception)
- **定时轮询 (Polling)**: 后端 `MonitorService` 每隔 2-5 分钟调用 `mijiaAPI` 获取全量设备状态。
- **场景模式 (HomeMode)**: 定义系统当前所处的状态（如：Home, Away, Sleep, Vacation）。

### 2.2 决策大脑 (Brain Logic)
- **权限矩阵 (HabitPolicy)**: 记录每个场景下动作的授权状态（ASK, ALWAYS, NEVER）。
- **观察者 (ObservationCounter)**: 记录用户在特定场景下对动作的反馈历史。
- **决策流**: 
    1. 发现异常状态（如 Away 模式灯亮）。
    2. 检查 `HabitPolicy`。
    3. 如果为 ASK，则根据 `ObservationCounter` 决定询问话术（普通询问 vs. 转正提议）。

### 2.3 交互执行层 (Interaction)
- **微信网关**: 通过微信发送带操作按钮或自然语言引导的消息。
- **LLM Agent**: 解析用户的自然语言回复（如 "Allow always"），并执行相应的米家控制指令或更新权限表。

## 3. 数据库模型 (Data Models)

### 3.1 `HomeMode` (场景模式)
- `id`: PK
- `name`: 模式名称 (Home, Away, Sleep, etc.)
- `is_active`: 是否为当前激活模式

### 3.2 `HabitPolicy` (策略矩阵)
- `id`: PK
- `mode`: FK(HomeMode)
- `device_did`: 米家设备 ID
- `property`: 设备属性 (e.g., "power")
- `value`: 目标值 (e.g., "off")
- `policy`: [ASK, ALWAYS, NEVER] (默认 ASK)

### 3.3 `ObservationCounter` (观察计数器)
- `id`: PK
- `mode`: FK(HomeMode)
- `device_did`: 米家设备 ID
- `property`: 设备属性
- `target_value`: 目标值
- `success_count`: 连续同意次数 (当达到 3 时触发转正提议)
- `last_updated`: 最后一次成功时间

## 4. 关键流程 (Key Workflows)

### 4.1 观察学习与转正 (Learning & Pitching)
1. **触发**: 场景匹配且 Policy 为 ASK。
2. **计数检查**: 
    - 如果 `success_count < 3`: 发送普通询问。
    - 如果 `success_count >= 3`: 发送包含“以后都直接做吗？”的提议。
3. **反馈处理**:
    - 用户回复“同意/Yes”: `success_count` +1。
    - 用户回复“以后都直接做/Allow Always”: 修改 `HabitPolicy` 为 ALWAYS，重置计数器。
    - 用户回复“拒绝/No”: 重置 `success_count` 为 0。

### 4.2 自然语言解析 (NLU)
- 使用 LLM 对微信回复进行分类：`CONFIRM` (单次确认), `DENY` (拒绝), `PERMANENT_ALLOW` (永久授权), `CHAT` (普通闲聊)。

## 5. 交互设计 (Interaction)
- **角色定位**: Classic Jarvis (专业、礼貌、称呼 Sir/主人)。
- **反馈闭环**: 每一条执行指令都必须有反馈（微信回复或静默日志）。
