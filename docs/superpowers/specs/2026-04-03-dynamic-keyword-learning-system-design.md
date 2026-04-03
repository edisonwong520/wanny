# 动态关键词学习与智能指令路由系统设计

**状态**: Draft
**日期**: 2026-04-03
**作者**: Claude

---

## 1. 问题背景

### 1.1 现状分析

当前设备意图识别系统存在以下问题：

| 问题类别 | 描述 | 影响 |
|----------|------|------|
| 中文覆盖不全 | 房间/设备/控制关键词硬编码，仅覆盖少量常见词 | 口语化表达无法识别 |
| 英文完全不支持 | 关键词列表全是中文，英文指令直接跳过设备意图解析 | 英文用户无法使用 |
| 硬编码不可扩展 | 关键词写死在代码中，无法根据用户设备动态调整 | 新设备需要改代码 |
| 无学习能力 | 系统无法从用户历史对话中学习习惯表达 | 重复匹配失败 |

### 1.2 当前代码结构

| 文件 | 关键词列表 | 作用 |
|------|-----------|------|
| `device_intent.py` | `DEVICE_HINT_PATTERNS` | 快速判断是否涉及设备 |
| `device_intent.py` | `ROOM_HINTS` (9个中文) | 房间名称匹配 |
| `device_intent.py` | `DEVICE_HINTS` (16个中文) | 设备名称匹配 |
| `device_intent.py` | `CONTROL_HINT_ALIASES` (11个) | 控制属性中文别名 |
| `device_command_service.py` | `control_aliases` | 控制属性别名（含部分英文） |

---

## 2. 设计目标

1. **双语支持**: 中文和英文指令同等处理能力
2. **动态学习**: 从用户历史对话和设备数据库自动学习关键词
3. **用户个性化**: 支持按用户存储个性化别名和表达习惯
4. **最少模型调用**: 40-50% 场景零模型调用，大部分场景 1 次小模型
5. **可扩展**: 新设备/新表达无需修改代码

---

## 3. 系统架构

### 3.1 四层处理流程

```
用户消息
    │
    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Layer 0: 小模型标准化层 (Normalizer)                                │
│  ─────────────────────────────────────────────────────────────────  │
│  触发条件: 检测到需要标准化（英文/口语化/语法混乱）                    │
│  模型: Ollama (qwen2.5:3b) 或 Gemini Flash Lite                     │
│  输入: 用户原始消息                                                  │
│  输出: 标准化中文指令                                                │
│  延迟目标: < 500ms                                                   │
└─────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Layer 1: 智能路由分类 (CommandRouter)                               │
│  ─────────────────────────────────────────────────────────────────  │
│  功能: 根据输入特征决定处理路径                                      │
│  分类结果:                                                           │
│  - "standard": 标准格式，跳过所有模型                                │
│  - "try_heuristic": 尝试启发式匹配                                   │
│  - "try_heuristic_then_normalize": 启发式优先，失败再标准化          │
│  - "needs_normalize": 需要标准化                                     │
│  - "needs_full_ai": 直接走大模型                                     │
│  - "skip_device": 非设备话题，跳过                                   │
│  数据来源: 动态加载的关键词（LearnedKeyword 表）                      │
└─────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Layer 2: 启发式解析 (HeuristicParser)                               │
│  ─────────────────────────────────────────────────────────────────  │
│  功能: 规则匹配，无模型调用                                          │
│  匹配维度:                                                           │
│  - 房间关键词（动态加载）                                            │
│  - 设备关键词（动态加载 + 设备数据库）                               │
│  - 控制属性关键词（动态加载）                                        │
│  - 动作关键词（动态加载）                                            │
│  输出: 结构化意图或 None                                             │
│  延迟: < 50ms                                                        │
└─────────────────────────────────────────────────────────────────────┘
    │ 匹配成功 → 返回意图
    │ 匹配失败 →
    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Layer 3: 大模型语义解析 (AI Parser)                                 │
│  ─────────────────────────────────────────────────────────────────  │
│  模型: Gemini Pro 或 Claude                                          │
│  功能: 处理复杂/多意图/歧义指令                                      │
│  输入: 标准化后的消息 + 设备列表 + 控制能力列表                       │
│  输出: 结构化意图 JSON                                               │
│  延迟: 1-3s                                                          │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 智能跳过逻辑

为减少模型调用次数，设计了智能跳过机制：

```
┌─────────────────────────────────────────────────────────────────────┐
│                    处理流程（最优路径选择）                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Step 1: 启发式优先尝试                                              │
│  ─────────────────────                                              │
│  输入 → 直接启发式匹配                                               │
│  成功 → 返回结果，结束 (0次调用)                                     │
│  失败 → 进入 Step 2                                                 │
│                                                                     │
│  Step 2: 判断是否需要标准化                                          │
│  ─────────────────────────                                          │
│  检测信号:                                                          │
│  - 英文关键词 ≥ 2个 → 需要                                           │
│  - 口语化特征 ≥ 1个 → 需要                                           │
│  - 语法混乱/过长 → 需要                                              │
│  - 标准格式 → 跳过                                                   │
│                                                                     │
│  Step 3: 小模型标准化 (按需触发)                                     │
│  ─────────────────────────────                                      │
│  需要 → 调用小模型标准化                                             │
│  标准化后 → 再次启发式匹配                                           │
│  成功 → 返回结果 (1次小调用)                                         │
│  失败 → 进入 Step 4                                                 │
│                                                                     │
│  Step 4: 大模型语义解析                                              │
│  ─────────────────────                                              │
│  处理复杂指令、多意图                                                │
│  返回结果 (1次大调用 或 2次调用)                                     │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 4. 模型调用次数预估

### 4.1 场景覆盖分析

| 输入类型 | 示例 | 处理路径 | 调用次数 |
|----------|------|----------|----------|
| 标准中文 | "打开客厅灯" | 启发式成功 | **0次** |
| 标准中文+设备 | "卧室空调调到24度" | 启发式成功 | **0次** |
| 口语化+设备关键词 | "把那个灯弄亮" | 启发式优先→成功 | **0次** |
| 口语化+模糊 | "有点热" | 启发式失败→标准化→启发式成功 | **1次(小)** |
| 纯英文 | "turn on the light" | 标准化→启发式成功 | **1次(小)** |
| 英文复杂 | "can you check the fuel in my car" | 标准化→启发式失败→大模型 | **2次(小+大)** |
| 多意图 | "开灯然后开空调" | 直接大模型 | **1次(大)** |
| 非设备 | "今天天气怎么样" | 跳过设备 | **0次(设备)** |

### 4.2 覆盖率目标

| 调用次数 | 目标占比 |
|----------|----------|
| 0次 | 40-50% |
| 1次(小模型) | 30-40% |
| 1次(大模型) | 10-15% |
| 2次 | 5-10% |

### 4.3 成本对比

| 指标 | 当前方案 | 新方案 |
|------|----------|--------|
| 标准指令调用 | 0次 | 0次 |
| 口语化/英文调用 | 1次(大) | 0-1次(小) |
| 复杂指令调用 | 1次(大) | 1-2次 |
| 平均延迟 | 1-3s | 0.3-1s |
| 成本节省 | - | **30-50%** |

---

## 5. 数据模型设计

### 5.1 LearnedKeyword 表

存储学习到的关键词和别名映射。

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | PK | 主键 |
| `account_id` | FK (nullable) | 用户ID，null 表示全局关键词 |
| `keyword` | VARCHAR(64) | 用户实际使用的表达，如 "那个大灯" |
| `normalized_keyword` | VARCHAR(64) | 归一化后的关键词，用于查重和检索 |
| `canonical` | VARCHAR(64) | 简单映射目标，仅用于纯别名场景，如 "主灯" |
| `canonical_payload` | JSON | 结构化映射结果，承载 room/device/control_key/action/value/unit 等 |
| `category` | ENUM | device/room/control/action/colloquial |
| `source` | ENUM | history/device/user/system |
| `confidence` | FLOAT | 置信度 0-1，越高越可靠 |
| `usage_count` | INT | 使用次数，用于权重计算 |
| `last_used_at` | DATETIME | 最后使用时间 |
| `learned_at` | DATETIME | 学习时间 |
| `is_active` | BOOLEAN | 是否启用 |

### 5.2 分类枚举

**Category Choices:**

| 值 | 说明 | 示例 |
|----|------|------|
| `device` | 设备别名 | "大灯" → "主灯" |
| `room` | 房间别名 | "主卧" → "卧室" |
| `control` | 控制属性别名 | "温度" → `temperature` |
| `action` | 动作别名 | "turn on" → "打开" |
| `colloquial` | 口语化表达 | "那个"、"弄"、"有点" |

**Source Choices:**

| 值 | 说明 |
|----|------|
| `history` | 从历史对话学习 |
| `device` | 从设备数据库提取 |
| `user` | 用户自定义 |
| `system` | 系统预设 |

### 5.3 索引设计

| 索引 | 字段 | 用途 |
|------|------|------|
| `idx_account_category` | account_id, category | 按用户分类查询 |
| `idx_account_normalized_keyword` | account_id, normalized_keyword | 用户维度关键词快速查找 |
| `idx_global_normalized_keyword` | normalized_keyword | 全局关键词快速查找 |
| `idx_active_confidence` | is_active, confidence | 筛选有效关键词 |
| `unique_account_keyword_category` | account_id, normalized_keyword, category | 防止用户级重复 |
| `unique_global_keyword_category` | normalized_keyword, category（仅 account_id is null） | 防止全局重复 |

### 5.4 canonical_payload 结构

为了适配当前 `device_intent.py` 与 `device_command_service.py` 的执行链，学习结果不能只存字符串映射，必须支持结构化语义：

```json
{
  "room": "客厅",
  "device": "主灯",
  "control_key": "brightness",
  "action": "set_property",
  "value": "+10%",
  "unit": null
}
```

使用原则：

1. `device` / `room` 类关键词：优先填充 `device` 或 `room`
2. `control` 类关键词：优先填充 `control_key`
3. `action` 类关键词：优先填充 `action`
4. 包含增量或数值语义的表达（如“热一点”“亮一点”）：必须写入 `canonical_payload.value`
5. `canonical` 仅作为人类可读展示和简单替换辅助字段，不作为唯一语义来源

---

## 6. 关键词学习系统

### 6.1 学习引擎 (KeywordLearner)

**触发方式:**
- 定时任务：全局学习每24小时，用户学习每6小时
- 手动触发：用户添加新设备时
- 事件触发：用户修正识别错误时

**学习来源:**

| 来源 | 方法 | 输出 |
|------|------|------|
| 历史对话 | AI 分析用户消息习惯 | 口语化关键词、用户习惯表达 |
| 设备数据库 | 提取设备名/房间名/控制名 | 设备关键词、房间关键词、控制关键词 |
| 用户反馈 | 用户显式添加别名 | 用户自定义别名 |
| 设备名变体生成 | 规则生成口语化变体 | "主灯" → "那个大灯"、"大灯" |

**学习边界约束:**

历史对话学习只允许使用“已成功落库并已执行/已确认”的设备交互样本，避免把闲聊、失败解析和误判学习成关键词。

建议仅从以下数据源抽样：

1. `Mission.source_type = DEVICE_CONTROL` 且状态为 `APPROVED` / 已成功执行
2. `DeviceOperationContext.intent_json.type in {"DEVICE_CONTROL", "DEVICE_QUERY"}`
3. 用户消息 `ChatMessage.role = USER`，且能关联到上述已确认设备意图

以下样本应显式排除：

1. `CHAT` / `UNSUPPORTED_COMMAND`
2. 澄清中间态消息
3. 未执行成功的设备控制
4. 纯环境描述但未触发设备行为的句子，如“今天太热了”

### 6.2 设备名变体生成规则

| 原始名称 | 生成的变体 |
|----------|------------|
| "主灯" | "那个主灯"、"这个主灯"、"大灯"、"主灯的那个" |
| "空调" | "那个空调"、"这台空调"、"大空调" |
| "扫地机" | "那个扫地机"、"扫地机器人"、"小扫地" |

### 6.3 历史对话学习 Prompt 设计

```
分析以下用户对话记录，提取用户习惯使用的设备控制表达方式。

要求：
1. 提取用户口语化表达（如 "那个大灯"、"弄亮一点"）
2. 映射到标准设备名/控制名
3. 区分：设备别名、房间别名、动作表达、口语化表达
4. 只提取出现 2 次以上的表达

输出 JSON 数组格式：
[
  {
    "keyword": "用户实际表达",
    "normalized_keyword": "归一化表达",
    "canonical": "标准映射",
    "category": "device|room|control|action|colloquial",
    "canonical_payload": {
      "room": "",
      "device": "",
      "control_key": "",
      "action": "",
      "value": null,
      "unit": null
    },
    "confidence": 0.0-1.0,
    "examples": ["原文例句1", "原文例句2"]
  }
]

对话记录：
{conversation_history}

设备列表（供参考映射）：
{device_list}
```

---

## 7. 关键词加载系统

### 7.1 KeywordLoader 设计

**加载策略:**

| 层级 | 说明 | 刷新频率 |
|------|------|----------|
| 全局缓存 | account_id=null 的关键词 | 启动时加载 + 每小时刷新 |
| 用户缓存 | 特定用户的关键词 | 按需加载 + 用户学习后刷新 |

**缓存结构:**

```
{
  "devices": Set[str],      // 所有设备关键词
  "rooms": Set[str],        // 所有房间关键词
  "controls": Set[str],     // 所有控制属性关键词
  "actions": Set[str],      // 所有动作关键词
  "colloquial": Set[str],   // 口语化表达信号
  "mapping": Dict[str, str], // keyword → canonical 映射（展示/简单替换）
  "payloads": Dict[str, dict] // keyword → canonical_payload（结构化语义）
}
```

### 7.2 合并策略

用户关键词与全局关键词合并时：
1. 用户关键词优先（覆盖全局同名关键词）
2. 映射关系合并，用户映射覆盖全局映射
3. 集合类型取并集
4. `payloads` 合并时同样以用户级为准，避免全局词覆盖用户私有习惯

---

## 8. 小模型标准化层

### 8.1 模型选择

| 优先级 | 模型 | 延迟 | 成本 | 适用场景 |
|--------|------|------|------|----------|
| 1 | Ollama (qwen2.5:3b) | 0.2-0.5s | 0 | 有本地算力 |
| 2 | Gemini Flash Lite | 0.3-0.6s | ~$0.0001/次 | 无本地算力 |
| 3 | Claude Haiku | 0.5-1s | ~$0.00025/次 | 备选 |

### 8.2 标准化 Prompt

```
你是智能家居指令标准化器。把用户口语化/英文/混合表达转为简洁的标准中文指令。

规则：
1. 输出必须是简洁中文，不超过20字
2. 只保留核心意图：动作 + 设备/房间 + 属性（如有）
3. 无法识别为设备指令时，输出原文不变

转换示例：
- "turn on the living room light" → "打开客厅灯"
- "make the bedroom warmer" → "调高卧室温度"
- "把客厅那个大灯弄得亮一点" → "调亮客厅主灯"
- "check the car fuel level" → "查询油量"
- "空调几度啊" → "查询空调温度"
- "卧室太热了" → "降低卧室温度"
- "今天天气怎么样" → "今天天气怎么样" (非设备指令)

用户消息:
{user_msg}

标准化输出（只输出结果，不要解释）:
```

### 8.3 输出约束

| 参数 | 值 | 说明 |
|------|-----|------|
| `max_tokens` | 32 | 限制输出长度 |
| `temperature` | 0.1 | 低温度保证稳定输出 |
| `timeout` | 3s | 超时返回原消息 |

---

## 9. 系统预设关键词

初始化时加载的基础双语关键词，确保系统启动即可用。

### 9.1 口语化信号

| 中文 | 英文 |
|------|------|
| "那个"、"这个"、"弄"、"搞"、"有点"、"帮我"、"太热"、"太冷"、"太亮"、"太暗" | "can you"、"please"、"a bit"、"kind of" |

### 9.2 动作关键词

| 中文 → 标准 | 英文 → 标准 |
|-------------|-------------|
| "打开" → "打开" | "turn on" → "打开" |
| "关闭" → "关闭" | "turn off" → "关闭" |
| "调高" → "调高" | "make it warmer" → "调高温度" |
| "调低" → "调低" | "make it cooler" → "调低温度" |
| "调亮" → "调亮" | "brighter" → "调亮" |
| "调暗" → "调暗" | "dimmer" → "调暗" |

### 9.3 设备关键词

| 中文 | 英文 → 中文 |
|------|-------------|
| "灯"、"空调"、"风扇"、"窗帘"、"扫地机"、"电视"、"车" | "light" → "灯"、"ac" → "空调"、"fan" → "风扇"、"curtain" → "窗帘"、"vacuum" → "扫地机"、"tv" → "电视"、"car" → "车" |

### 9.4 房间关键词

| 中文 | 英文 → 中文 |
|------|-------------|
| "客厅"、"卧室"、"主卧"、"厨房"、"卫生间"、"书房" | "living room" → "客厅"、"bedroom" → "卧室"、"master bedroom" → "主卧"、"kitchen" → "厨房"、"bathroom" → "卫生间"、"study" → "书房" |

---

## 10. 文件结构

### 10.1 新增文件

| 文件路径 | 说明 |
|----------|------|
| `backend/apps/comms/models.py` (扩展) | LearnedKeyword 数据模型 |
| `backend/apps/comms/keyword_learner.py` | 关键词学习引擎 |
| `backend/apps/comms/keyword_loader.py` | 动态关键词加载器 |
| `backend/apps/comms/initial_keywords.py` | 系统预设关键词初始化 |
| `backend/apps/comms/tasks.py` | 定时学习任务 |
| `backend/apps/comms/command_router.py` | 输入分类路由（使用动态关键词） |
| `backend/apps/comms/normalizer.py` | 小模型标准化层 |
| `backend/apps/comms/migrations/0008_learnedkeyword.py` | 数据库迁移（编号需承接当前仓库） |

### 10.2 修改文件

| 文件路径 | 修改内容 |
|----------|----------|
| `backend/apps/comms/device_intent.py` | 扩展启发式规则，使用动态关键词 |
| `backend/apps/comms/services.py` | 调用 command_router 处理消息 |
| `backend/apps/comms/device_command_service.py` | 消费结构化 `control_key` / `action` / `value` 映射 |
| `backend/.env.example` | 新增 NORMALIZER_PROVIDER 等配置 |

---

## 11. 环境配置

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `NORMALIZER_PROVIDER` | `ollama` | 标准化模型提供商: ollama / gemini |
| `NORMALIZER_OLLAMA_MODEL` | `qwen2.5:3b` | Ollama 模型名称 |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama 服务地址 |
| `NORMALIZER_GEMINI_MODEL` | `gemini-2.0-flash-lite` | Gemini 模型名称 |
| `KEYWORD_REFRESH_INTERVAL` | `3600` | 关键词缓存刷新间隔(秒) |
| `KEYWORD_LEARNING_INTERVAL_GLOBAL` | `86400` | 全局学习间隔(秒) |
| `KEYWORD_LEARNING_INTERVAL_USER` | `21600` | 用户学习间隔(秒) |

---

## 12. 性能指标

| 指标 | 目标值 |
|------|--------|
| 标准指令响应延迟 | < 100ms |
| 口语化指令响应延迟 | < 500ms |
| 英文指令响应延迟 | < 600ms |
| 复杂指令响应延迟 | < 3s |
| 关键词缓存刷新延迟 | < 1s |
| 学习任务执行时间 | < 30s |

---

## 13. 后续优化方向

1. **在线学习**: 用户每次修正识别错误时即时学习
2. **关键词推荐**: 当用户表达无法识别时，推荐可能的关键词
3. **多语言扩展**: 支持更多语言（日语、韩语等）
4. **Federated Learning**: 跨用户学习通用关键词（隐私保护）
5. **关键词热度衰减**: 长期未用的关键词自动降权

---

## 14. 风险与应对

| 风险 | 影响 | 应对措施 |
|------|------|----------|
| 学习到错误关键词 | 识别错误增加 | 置信度阈值过滤 + 用户反馈机制 |
| 小模型延迟过高 | 响应慢 | 本地模型优先 + 超时降级 |
| 关键词表过大 | 加载慢 | 置信度过滤 + 分级加载 |
| 用户隐私 | 数据泄露 | 本地学习优先 + 数据脱敏 |
| 学到错误上下文 | 连续误识别 | 仅从成功设备意图样本学习 + 保留人工停用开关 |

---

## 附录 A: 处理流程伪代码

```
async function process_device_command(user_msg, account):
    # Step 1: 启发式优先尝试
    result = heuristic_parse(user_msg)
    if result:
        return result  # 0次调用

    # Step 2: 判断是否需要标准化
    input_type = classify_input_type(user_msg, account.id)

    # Step 3: 按需标准化
    if input_type in ["needs_normalize", "try_heuristic_then_normalize"]:
        normalized_msg = await normalize(user_msg)  # 小模型

        result = heuristic_parse(normalized_msg)
        if result:
            return result  # 1次小调用

        user_msg = normalized_msg

    # Step 4: 大模型解析
    if input_type == "skip_device":
        return {"type": "CHAT"}

    return await analyze_device_intent(user_msg, account)  # 大模型
```

---

## 附录 B: 关键词学习流程伪代码

```
async function run_learning_cycle(account_id):
    # 来源1: 已确认成功的设备交互
    samples = fetch_confirmed_device_samples(account_id, days=7)
    history_keywords = await ai_analyze(samples, device_list)

    # 来源2: 设备数据库
    devices = fetch_devices(account_id)
    device_keywords = extract_keywords_from_devices(devices)

    # 来源3: 生成变体
    for device in devices:
        variants = generate_name_variants(device.name)
        device_keywords += variants

    all_keywords = merge(history_keywords, device_keywords)

    # 合并存储
    for kw in all_keywords:
        if exists(account_id, kw.normalized_keyword, kw.category):
            update_confidence_and_count()
        else:
            create_new_keyword()
```

---

## 附录 C: 落地建议（修订后）

建议按下面顺序实施，避免一次性引入过多变量：

1. Phase 1: 只做静态双语词表 + `KeywordLoader` + `device_intent.py` 接入，不开启历史学习
2. Phase 2: 引入 `LearnedKeyword` 表与用户级缓存，先接“设备数据库提取 + 用户手工别名”
3. Phase 3: 接入小模型标准化层，观测命中率、延迟和误判率
4. Phase 4: 最后再开启历史对话学习，且仅对成功设备意图样本生效

对应验收标准：

1. 英文基础设备控制可在 1 次小模型内完成
2. 中文标准指令仍保持 0 模型调用
3. 学习系统关闭时，现有设备控制回归测试全部通过
4. 学习系统开启后，不得降低现有高风险控制的确认门槛
