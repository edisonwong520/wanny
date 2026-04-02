# 微信语音指令设备控制方案设计

## 概述

实现通过微信发送自然语言指令（包括语音消息）控制智能家居设备的能力。用户可以用口语化表达如"把客厅灯关了"、"空调开到26度"来操作米家、美的、Home Assistant 等平台的设备。

## 当前进度（2026-04-02）

### 总体状态

- `1. 意图分类体系`：已完成并落地
- `2. 设备指令解析流程`：已完成并落地
- `3. DeviceCommandService 服务`：已完成并落地
- `4. DeviceContextManager 上下文管理`：已完成并落地
- `5. DeviceExecutor 设备执行器`：核心已完成并落地
- `6. WeChatService 改造`：已完成并落地
- `7. 测试策略`：已基本落地，正在继续把老测试迁到新目录

### 已落地能力

- 微信文本 / 语音消息已支持设备控制、设备查询、澄清、确认、拒绝、Shell 分流
- `jarvis, xxx` / `贾维斯，xxx` 已作为硬性命令模式落地，不再回退为普通聊天
- 设备控制 Mission 已支持冻结执行计划，确认阶段不再重新猜设备
- 设备歧义澄清已支持 pending mission、取消、过期、幂等保护
- `DeviceContextManager` 已支持最近操作记录、人类可读时间、连续调节型上下文继承
- `DeviceExecutor` 已支持统一执行入口、显式平台分发、错误归一化、离线替代建议、单设备刷新
- Web 控制台已支持展示 `device_control` / `device_clarification` 任务，并能审批设备控制任务

### 主要代码位置

- `backend/apps/comms/device_intent.py`
- `backend/apps/comms/device_command_service.py`
- `backend/apps/comms/device_context_manager.py`
- `backend/apps/comms/services.py`
- `backend/apps/devices/executor.py`
- `backend/apps/comms/serializers.py`
- `backend/apps/comms/views.py`

### 已补齐的测试与脚本

- Unit:
  - `backend/tests/unit/test_device_intent_parser.py`
  - `backend/tests/unit/test_device_command_resolver.py`
  - `backend/tests/unit/test_device_executor.py`
  - `backend/tests/unit/test_device_context_manager.py`
- Integration:
  - `backend/tests/integration/test_device_control_flow.py`
  - `backend/tests/integration/test_wechat_device_command.py`
- Scripts:
  - `backend/tests/scripts/test_wechat_device_command.py`
  - `backend/tests/scripts/test_mijia_voice_command.py`
  - `backend/tests/scripts/test_midea_voice_command.py`

### 回家后适合继续推进的收尾项

- 继续把 `backend/apps/comms/tests.py` 里稳定的设备链路用例迁移到 `backend/tests/unit` / `backend/tests/integration`
- 继续细化 `DeviceExecutor` 的平台级错误映射测试，分别补厚米家 / 美的 / HA 的异常边界
- 本地执行 smoke script 前先跑一次 `./.venv/bin/python manage.py migrate`

## 核心特性

- 支持语音消息自动转文字（微信 iLink 协议自带）
- 混合模式：默认全量意图识别，支持关键词强制切换模式
- `jarvis, xxx` / `贾维斯，xxx` 一律进入命令模式，绝不按普通闲聊处理
- 模糊指令交互确认 + 上下文继承
- 继承现有 HabitPolicy 策略矩阵
- 操作失败直接报错 + 替代方案推荐

---

## 1. 意图分类体系

### 1.1 意图类型定义

| 类型 | 说明 | 输出字段 |
|------|------|----------|
| `CHAT` | 普通闲聊/查询 | `response` |
| `DEVICE_CONTROL` | 设备操作指令 | 见 1.2 |
| `DEVICE_QUERY` | 设备状态查询 | 见 1.3 |
| `COMPLEX_SHELL` | Shell 系统指令 | `shell_prompt`, `confirm_text`, `metadata` |
| `CONFIRM` | 确认上一次待审批任务 | - |
| `PERMANENT_ALLOW` | 永久授权 | - |
| `DENY` | 拒绝执行 | `response` |
| `UNSUPPORTED_COMMAND` | 已识别为命令模式，但无法映射到设备 / Shell / 确认语义 | `response`, `reason` |

### 1.2 DEVICE_CONTROL 输出结构

```json
{
  "type": "DEVICE_CONTROL",
  "action": "set_property",
  "room": "客厅",
  "device": "主灯",
  "control_key": "power",
  "value": false,
  "unit": null,
  "confidence": 0.85,
  "ambiguous": false,
  "alternatives": [],
  "suggested_reply": "好的，正在关闭客厅主灯",
  "error_hint": null
}
```

字段说明：

- `action`: 操作类型
  - `set_property`: 设置属性值（开关、亮度、温度等）
  - `run_action`: 执行动作（如"清扫"、"制冷模式")

- `room`: 房间名称（模糊匹配，可为空）
- `device`: 设备名称（模糊匹配，可为空）
- `control_key`: 控制标识（如 `power`, `brightness`, `temperature`)
- `value`: 目标值（布尔、数值、字符串）
- `confidence`: 匹配置信度（0-1）
- `ambiguous`: 是否需要用户确认（置信度低或多个候选时为 true）
- `alternatives`: 模糊匹配时的候选列表
- `suggested_reply`: AI 建议的回复文案
- `error_hint`: 预判的错误提示（如设备不存在）

### 1.3 DEVICE_QUERY 输出结构

```json
{
  "type": "DEVICE_QUERY",
  "room": "客厅",
  "device": "空调",
  "control_key": "temperature",
  "suggested_reply": "客厅空调当前温度为 26°C"
}
```

### 1.4 命令模式约束

当消息命中 Jarvis 唤醒词时，系统进入 `COMMAND_MODE`。

**命中规则**:

- 文本或语音转写以 `"jarvis "`、`"jarvis,"`、`"jarvis，"`、`"jarvis:"`、`"jarvis："` 开头
- 文本或语音转写以 `"贾维斯 "`、`"贾维斯，"`、`"贾维斯："` 开头
- 命中后先剥离唤醒词，再做后续意图解析

**硬约束**:

- `COMMAND_MODE` 下绝不能返回 `CHAT`
- `COMMAND_MODE` 下只能返回：
  - `DEVICE_CONTROL`
  - `DEVICE_QUERY`
  - `COMPLEX_SHELL`
  - `CONFIRM`
  - `PERMANENT_ALLOW`
  - `DENY`
  - `UNSUPPORTED_COMMAND`
- 如果系统无法判断具体要执行什么，必须返回 `UNSUPPORTED_COMMAND`，而不是回退到普通闲聊

**UNSUPPORTED_COMMAND 输出结构**:

```json
{
  "type": "UNSUPPORTED_COMMAND",
  "response": "这是命令模式，但我还没理解您希望我执行什么操作。",
  "reason": "not_device_not_shell"
}
```

---

## 2. 设备指令解析流程

### 2.1 analyze_device_intent 函数

**位置**: `backend/apps/comms/device_intent.py`

**职责**: 接收用户消息文本 + 设备上下文，调用 AI 返回结构化的设备操作指令

**输入参数**:

- `user_msg`: 用户原始消息文本
- `account`: 用户账户对象
- `memory_context`: 历史对话上下文（可选）
- `command_mode`: 是否已命中 Jarvis 唤醒词

**Prompt 注入内容**:

1. **设备清单**: 从 `DeviceSnapshot` 获取用户所有设备，格式化为：
   ```
   设备列表：
   - 客厅: 主灯(在线), 空调(在线), 电视(离线)
   - 卧室: 床头灯(在线), 空调(在线)
   - 厨房: 油烟机(在线)
   ```

2. **控制能力**: 从 `DeviceControl` 获取每个设备的可操作项：
   ```
   客厅主灯 可操作: power(开关), brightness(亮度 0-100), color_temp(色温)
   客厅空调 可操作: power(开关), temperature(温度 16-30), mode(模式: 制冷/制热/除湿)
   ```

3. **最近操作上下文**: 从 `DeviceContextManager` 获取：
   ```
   最近操作: 客厅主灯(2分钟前关闭)
   ```

4. **当前模式**: 从 `HomeMode` 获取（如有）：
   ```
   当前模式: 在家
   ```

**Prompt 模板**:

```
你是 Wanny 的设备控制解析引擎。用户发送了一条消息，请判断是否为设备控制指令，并输出结构化 JSON。

用户设备清单：
{device_list}

各设备可操作项：
{control_capabilities}

最近操作上下文：
{recent_context}

当前模式：{current_mode}

用户消息：{user_msg}
是否命令模式：{command_mode}

请严格返回 JSON（不要使用 markdown 代码块），格式如下：
{
  "type": "DEVICE_CONTROL" | "DEVICE_QUERY" | "CHAT" | "UNSUPPORTED_COMMAND",
  ...
}

判断规则：
1. 如果消息涉及设备操作（开关、调节、查询状态），输出 DEVICE_CONTROL 或 DEVICE_QUERY
2. 仅在非命令模式下，普通对话才允许输出 CHAT
3. 如果是命令模式但无法映射为设备意图，输出 UNSUPPORTED_COMMAND
4. 房间和设备名称允许模糊匹配，系统会自动处理
5. 如果无法确定具体设备，设置 ambiguous=true 并提供 alternatives
6. 如果用户说"调暗一点"、"稍微开大点"，请推断合理的数值变化（如亮度降低 20%）
7. 命令模式下不要输出闲聊式安慰或扩展回答，只输出结构化命令结果
```

**补充约束**:

- Prompt 中注入的设备能力尽量使用半结构化格式，而不是纯自然语言描述，至少包含：
  - `device_external_id`
  - `room`
  - `device_name`
  - `control_external_id`
  - `key`
  - `label`
  - `kind`
  - `writable`
  - `unit`
  - `options`
  - `range_spec`
- AI 返回结果只负责语义归一化，最终设备选择和能力校验必须由服务端二次校验

---

## 3. DeviceCommandService 服务

**位置**: `backend/apps/comms/device_command_service.py`

**职责**:

- 接收 AI 解析的结构化指令
- 匹配具体设备实例
- 处理模糊匹配和用户确认
- 查询授权策略
- 执行设备操作
- 返回结果反馈

### 3.1 resolve_device_target 方法

**输入**: AI 解析的 JSON（room, device, control_key）

**处理逻辑**:

1. 根据 `room` 查询 `DeviceRoom`，模糊匹配房间名称
2. 根据 `device` 在该房间内查询 `DeviceSnapshot`，模糊匹配设备名称
3. 根据 `control_key` 查询 `DeviceControl`，确认设备具备该操作能力
4. 计算匹配置信度：
   - 房间+设备+控制项完全匹配 → confidence=1.0
   - 部分模糊匹配 → confidence=0.5-0.9
   - 无法匹配 → 返回候选列表

**输出**:

```python
{
    "matched_device": DeviceSnapshot,
    "matched_control": DeviceControl,
    "confidence": float,
    "ambiguous": bool,
    "alternatives": [
        {"room": "客厅", "device": "主灯", "control": "power"},
        {"room": "卧室", "device": "床头灯", "control": "power"}
    ]
}
```

**补充要求**:

- 最终执行应尽量落到具体的 `DeviceControl.external_id`
- 若一个 `control_key` 在同一设备上存在多个候选 control，不得直接执行，必须进入确认
- resolver 应输出是否来自上下文继承，例如：

```python
{
    "matched_device": DeviceSnapshot,
    "matched_control": DeviceControl,
    "confidence": float,
    "ambiguous": bool,
    "resolved_from_context": bool,
    "alternatives": [...]
}
```

### 3.2 check_authorization 方法

**输入**: 设备对象 + 用户账户 + 操作类型

**处理逻辑**:

1. 区分“用户主动命令”和“系统主动建议”两类场景
2. 对于用户主动命令：
   - 默认优先执行
   - 仅在高风险设备、高风险动作、低置信度匹配或上下文继承不充分时要求确认
3. 对于系统主动建议 / 自动化链路：
   - 查询 `HabitPolicy`，获取该设备的策略（ASK/ALWAYS/NEVER）
4. 如果策略为 ALWAYS → 直接执行
5. 如果策略为 NEVER → 拒绝并返回原因
6. 如果策略为 ASK 或无策略 → 需用户确认

**设计说明**:

- `HabitPolicy` 主要服务于主动决策与自动化，不应机械地覆盖用户明确下达的设备命令
- 否则会出现“用户亲自发出命令却因 NEVER 被拒绝”的体验冲突

**输出**:

```python
{
    "allowed": bool,
    "need_confirm": bool,
    "policy": "ASK" | "ALWAYS" | "NEVER",
    "reason": str
}
```

### 3.3 execute_device_operation 方法

**输入**: 设备对象 + 控制项 + 目标值

**处理逻辑**:

1. 检查设备在线状态（`DeviceSnapshot.status`）
2. 根据设备来源类型（mijia/midea_cloud/ha_entity）调用对应客户端
3. 执行操作并等待响应
4. 执行单设备回读，更新 `DeviceControl.value` 和 `DeviceSnapshot.telemetry`
5. 处理异常：离线、超时、操作失败

**输出**:

```python
{
    "success": bool,
    "message": str,
    "new_value": dict,
    "error": str | None,
    "suggestion": str | None
}
```

---

## 4. DeviceContextManager 上下文管理

**位置**: `backend/apps/comms/device_context_manager.py`

**职责**:

- 记录用户最近操作的设备
- 提供上下文继承能力（模糊指令时继承上次操作的设备）
- 支持跨会话的上下文持久化

### 4.1 数据模型

新建 `DeviceOperationContext` 模型：

```python
class DeviceOperationContext(models.Model):
    """用户设备操作上下文记录"""
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    device = models.ForeignKey(DeviceSnapshot, on_delete=models.CASCADE)
    control_key = models.CharField(max_length=64)
    operation_type = models.CharField(max_length=32)   # set_property / run_action
    value = models.JSONField()
    operated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "comms_device_context"
        ordering = ['-operated_at']
```

选择独立模型而非复用 `DeviceControl` 的原因：

- 独立存储操作历史，不影响设备模型职责
- 可记录多次操作历史，支持更丰富的上下文继承逻辑
- 便于未来扩展（如统计分析用户操作习惯）

### 4.2 核心方法

#### record_operation

记录用户的一次设备操作。

**输入**: account, device, control_key, operation_type, value

**处理**:

- 创建 `DeviceOperationContext` 记录
- 可选：限制每个账户只保留最近 N 条记录（如 20 条），避免数据膨胀

#### get_recent_context

获取用户最近操作的设备上下文。

**输入**: account, limit=5

**输出**:

```python
[
    {"room": "客厅", "device": "主灯", "control": "power", "value": False, "operated_at": "2分钟前"},
    {"room": "卧室", "device": "空调", "control": "temperature", "value": 26, "operated_at": "10分钟前"},
]
```

#### get_last_operated_device

获取用户最近操作的设备（用于模糊指令继承）。

**输入**: account

**输出**: DeviceSnapshot 对象或 None

### 4.3 上下文继承规则

当 AI 解析的指令中 `device` 为空或 `ambiguous=true` 时：

1. 检查是否有最近操作的设备（`get_last_operated_device`）
2. 仅当满足以下全部条件时，才允许自动继承：
   - 最近操作时间在短窗口内（建议 3-5 分钟）
   - 当前指令属于连续调节型控制，如亮度、温度、音量、风速
   - 当前 control 与最近 control 同类，或可明确推导为同类
3. 对以下类型不得直接自动继承，必须确认：
   - 电源开关类（如开灯、关灯、开空调）
   - 动作触发类（如清扫、开锁、开门）
   - 涉及多个候选设备的场景
4. 如果继承成功，resolver 需标记 `resolved_from_context=true`
5. 例如：用户刚操作了"客厅主灯"，后续说"调暗一点" → 可继承到客厅主灯亮度控制
6. 例如：用户刚操作了"卧室空调"，后续只说"关掉" → 不得自动继承执行，必须先确认

### 4.4 审计与排障信息

为方便排查误触发、误识别、误执行，建议记录以下字段：

- `raw_user_msg`: 用户原始文本
- `normalized_msg`: 剥离唤醒词并清洗后的文本
- `voice_transcript`: 语音转写文本（若有）
- `intent_json`: AI 结构化输出
- `resolver_result`: 目标解析结果
- `execution_result`: 最终执行结果

---

## 5. DeviceExecutor 设备执行器

**位置**: `backend/apps/devices/executor.py`

**职责**:

- 统一封装各平台的设备操作调用
- 处理操作结果和异常
- 触发设备状态回读更新

### 5.1 平台适配器

根据 `DeviceControl.source_type` 调用对应客户端：

| source_type | 客户端 | 操作方式 |
|-------------|--------|----------|
| `mijia_property` | `mijiaAPI` | `device.get()` / `device.set()` |
| `mijia_action` | `mijiaAPI` | `device.run_action()` |
| `midea_cloud_property` | `MideaCloudClient` | 自定义 API 调用 |
| `midea_cloud_action` | `MideaCloudClient` | 自定义 API 调用 |
| `ha_entity` | Home Assistant API | REST 调用 |

### 5.2 核心方法

#### execute

执行设备操作。

**输入**: DeviceControl 对象, 目标值, account

**处理逻辑**:

1. 获取设备对象和平台认证
2. 根据 `source_type` 分发到对应处理器（execute_mijia_property / execute_midea_property / execute_ha_entity）
3. 执行单设备回读更新
4. 返回统一格式结果

#### execute_mijia_property

米家属性操作。

**处理**:

- 从 `PlatformAuth` 获取米家登录凭证
- 构建 `mijiaDevice` 实例
- 调用 `device.set(control.key, value)`
- 捕获异常并转换为统一错误格式

#### execute_midea_property

美的属性操作。

**处理**:

- 从 `PlatformAuth` 获取美的云认证
- 调用 `MideaCloudClient` 的对应方法
- 使用已有的 `clients/midea_cloud/client.py`

#### execute_ha_entity

Home Assistant 实体操作。

**处理**:

- 从 `PlatformAuth` 获取 HA 的 URL 和 Token
- 调用 HA REST API (`/api/services/<domain>/<service>`)

#### refresh_single_device

单设备状态回读。

**处理**:

- 仅刷新当前操作设备的状态（而非全量同步）
- 更新 `DeviceControl.value` 和 `DeviceSnapshot.telemetry`
- 减少对平台 API 的压力

### 5.3 错误处理

统一错误类型：

| 错误类型 | 说明 | 用户反馈 |
|----------|------|----------|
| `DEVICE_OFFLINE` | 设备离线 | "设备离线，无法操作" + 替代建议 |
| `OPERATION_FAILED` | 操作执行失败 | "操作失败，请稍后重试" |
| `AUTH_EXPIRED` | 平台认证过期 | "平台授权已过期，请重新登录" |
| `UNSUPPORTED_OPERATION` | 设备不支持该操作 | "该设备不支持此操作" |
| `TIMEOUT` | 操作超时 | "操作超时，设备可能响应缓慢" |

### 5.4 替代方案推荐

当设备离线或操作失败时：

1. 查询同一房间内的同类型设备（如空调离线 → 推荐风扇）
2. 查询其他房间内的同类型设备（如客厅空调离线 → 推荐卧室空调）
3. 返回格式："客厅空调离线，是否打开卧室空调？"

---

## 6. WeChatService 改造

**位置**: `backend/apps/comms/services.py`

### 6.1 改造后的处理流程

```python
async def process_incoming_message(message, bot):
    # 1. 提取消息内容（支持语音自动转文字）
    content = message.text or ""
    voices = message.voices
    if voices and voices[0].text:
        content = voices[0].text

    # 2. 检查强制模式关键词
    mode = detect_command_mode(content)
    # "jarvis xxx" / "贾维斯 xxx" → 强制命令模式

    # 3. 意图分流判断
    if mode == "command" or should_check_device_intent(content):
        normalized_content = strip_wakeup_prefix(content)
        intent = await analyze_device_intent(
            normalized_content,
            account,
            memory_context,
            command_mode=(mode == "command"),
        )

        if intent["type"] in ["DEVICE_CONTROL", "DEVICE_QUERY"]:
            await handle_device_intent(intent, message, bot, account)
            return

        if mode == "command" and intent["type"] == "UNSUPPORTED_COMMAND":
            await bot.reply(message, intent["response"])
            return

    # 4. 转交原有 analyze_intent 处理
    intent = await analyze_intent(content, memory_context)

    # 5. 原有逻辑处理 CHAT, COMPLEX_SHELL, CONFIRM, DENY 等
```

### 6.2 新增辅助方法

#### detect_command_mode

检测强制模式关键词。

- 消息以 `"jarvis "`、`"jarvis,"`、`"jarvis，"`、`"jarvis:"`、`"jarvis："` 开头 → 强制命令模式
- 消息以 `"贾维斯 "`、`"贾维斯，"`、`"贾维斯："` 开头 → 强制命令模式
- 未来可扩展更多关键词

#### strip_wakeup_prefix

剥离唤醒词前缀。

- 输入：`"jarvis，把客厅灯关了"`
- 输出：`"把客厅灯关了"`
- 命令模式判定和实际语义解析应使用同一套前缀规则，避免判定与解析不一致

#### should_check_device_intent

判断是否可能为设备指令（快速过滤）。

- 包含设备相关关键词（开、关、调、亮、暗、热、冷、温度、亮度等）
- 用于减少不必要的 AI 调用

#### handle_device_intent

处理设备控制意图。

**处理流程**:

1. 匹配设备目标（`DeviceCommandService.resolve_device_target`）
2. 模糊匹配时询问用户确认
3. 检查授权策略（`DeviceCommandService.check_authorization`）
4. 根据策略分支：ALWAYS 直接执行，NEVER 拒绝，ASK 创建 Mission
5. 执行操作，记录上下文，回复用户

**补充规则**:

- `DEVICE_QUERY` 不进入 Mission 审批流，应直接读取快照或触发单设备刷新后返回
- `DEVICE_CONTROL` 才进入授权与 Mission 逻辑
- 命令模式下如果语音转写存在明显歧义，可先回显识别文本让用户确认

#### create_device_mission

创建设备控制待审批任务。

- 创建 `Mission` 记录，`source_type="DEVICE_CONTROL"`
- 发送确认提示给用户
- 落库存储完整的“待执行计划”，确保后续 CONFIRM 阶段无需重新猜测目标设备

#### build_result_reply

构建执行结果回复文案。

- 成功：使用 AI 的 `suggested_reply` 或默认文案
- 失败：错误信息 + 替代方案建议

### 6.3 Mission 模型扩展

在现有 `Mission` 模型中新增字段：

```python
class Mission(models.Model):
    # ... 现有字段 ...

    device_id = models.CharField(max_length=128, blank=True, verbose_name="目标设备 ID")
    control_id = models.CharField(max_length=255, blank=True, verbose_name="目标控制 ID")
    control_key = models.CharField(max_length=64, blank=True, verbose_name="控制项标识")
    operation_action = models.CharField(max_length=32, blank=True, verbose_name="操作动作")
    operation_value = models.JSONField(default=dict, blank=True, verbose_name="操作目标值")
    source_type = models.CharField(
        max_length=32,
        choices=[
            ("shell", "Shell 指令"),
            ("device_control", "设备控制"),
        ],
        default="shell",
        verbose_name="任务来源类型"
    )
```

同时在 `metadata` 中建议保留以下解析快照：

```json
{
  "intent_type": "DEVICE_CONTROL",
  "provider": "mijia_property",
  "device_external_id": "mijia:123",
  "control_external_id": "mijia:123:power",
  "control_key": "power",
  "action": "set_property",
  "value": false,
  "unit": null,
  "resolved_from_context": false,
  "alternatives_snapshot": []
}
```

**设计要求**:

- CONFIRM / PERMANENT_ALLOW 阶段必须基于 Mission 中已冻结的执行计划执行
- 不应在确认时重新跑一次模糊匹配，以避免设备快照变动或上下文变化导致误控
- 同一条微信消息应具备幂等保护，避免重复创建 Mission 或重复执行

### 6.4 确认回复处理扩展

当用户回复 CONFIRM/PERMANENT_ALLOW 时：

```python
if intent_type == "CONFIRM":
    if mission.source_type == "device_control":
        result = await DeviceCommandService.execute_device_operation(...)
        await DeviceContextManager.record_operation(...)
```

**补充规则**:

- 若当前存在多个 `pending` 任务，不应仅按“最近一条”粗暴匹配，需优先匹配：
  - 同一用户
  - 同一会话 / 最近交互窗口
  - 同一 source_type
- 如果无法唯一确定要确认的任务，应先向用户澄清，而不是默认确认最近一条

---

## 7. 测试策略

### 7.1 测试目录结构

```
/tests
  /unit
    test_device_intent_parser.py      # 设备意图解析单元测试
    test_device_command_resolver.py   # 设备目标匹配单元测试
    test_device_executor.py           # 执行器单元测试
    test_device_context_manager.py    # 上下文管理单元测试
  /integration
    test_device_control_flow.py       # 设备控制全流程集成测试
    test_wechat_device_command.py     # 微信消息 → 设备执行集成测试
  /scripts
    test_mijia_voice_command.py       # 米家语音指令验证脚本
    test_midea_voice_command.py       # 美的语音指令验证脚本
```

### 7.2 单元测试重点

#### test_device_intent_parser.py

- 各种用户表达方式的意图识别
- 模糊匹配场景（ambiguous=true）
- 数值推断（"调暗一点" → 合理幅度）
- 上下文继承效果
- `jarvis` 命令模式下禁止回退为 CHAT
- `UNSUPPORTED_COMMAND` 返回场景

#### test_device_command_resolver.py

- 精确匹配
- 模糊匹配
- 设备不存在场景
- 控制项不支持场景

#### test_device_executor.py

- Mock 平台客户端，验证调用参数
- 离线设备处理
- 操作失败和错误转换
- 替代方案推荐逻辑

### 7.3 集成测试重点

#### test_device_control_flow.py

- 完整流程测试（不依赖真实微信）
- 各策略分支（ASK/ALWAYS/NEVER）
- Mission 创建和审批流程
- 多个 pending mission 并存时的确认匹配
- 命令模式下设备意图失败时不回退为普通闲聊

#### test_wechat_device_command.py

- 模拟微信消息对象（包含语音转文字）
- 消息分流逻辑
- 回复内容格式
- 语音转写为空 / 转写错误 / 唤醒词误识别场景
- `jarvis, xxx` / `贾维斯，xxx` 前缀处理

### 7.4 验证脚本

#### test_mijia_voice_command.py

- 通过微信发送语音指令
- 验证设备实际响应
- 手动检查设备状态变化

#### test_midea_voice_command.py

- 验证美的云 API 调用
- 验证状态回读更新

### 7.5 Mock 策略

- AI 调用：预设 JSON 响应，避免依赖真实 AI
- 设备平台：Mock 客户端，模拟成功/失败/离线场景
- 微信 SDK：Mock bot 对象，验证 reply 调用

### 7.6 高风险回归用例

- `jarvis，帮我关灯` 命中命令模式并进入设备控制链路
- `jarvis，今天天气怎么样` 不得回落为 CHAT，应进入 `UNSUPPORTED_COMMAND` 或 Shell 分析
- 用户刚操作空调后发送“关掉”，系统必须要求确认，不得直接继承执行
- 同时存在 shell mission 与 device mission 时，“好的” 不能确认错对象
- 同一消息重复投递时，不得重复创建设备 mission 或重复执行设备控制

---

## 8. 文件清单

### 新增文件

| 文件路径 | 说明 |
|----------|------|
| `backend/apps/comms/device_intent.py` | 设备意图解析函数 |
| `backend/apps/comms/device_command_service.py` | 设备指令处理服务 |
| `backend/apps/comms/device_context_manager.py` | 操作上下文管理 |
| `backend/tests/unit/test_device_intent_parser.py` | 意图解析单元测试 |
| `backend/tests/unit/test_device_command_resolver.py` | 目标匹配单元测试 |
| `backend/tests/unit/test_device_executor.py` | 执行器单元测试 |
| `backend/tests/unit/test_device_context_manager.py` | 上下文管理单元测试 |
| `backend/tests/integration/test_device_control_flow.py` | 全流程集成测试 |
| `backend/tests/integration/test_wechat_device_command.py` | 微信集成测试 |
| `backend/tests/scripts/test_mijia_voice_command.py` | 米家验证脚本 |
| `backend/tests/scripts/test_midea_voice_command.py` | 美的验证脚本 |

### 修改文件

| 文件路径 | 改动说明 |
|----------|----------|
| `backend/apps/comms/services.py` | 接入设备控制流程，新增辅助方法 |
| `backend/apps/comms/models.py` | Mission 模型新增字段 |
| `backend/apps/comms/migrations/XXXX_add_device_control_fields.py` | Mission 模型迁移文件 |
| `backend/apps/comms/migrations/XXXX_add_device_context_model.py` | DeviceOperationContext 模型迁移文件 |
| `backend/apps/devices/services.py` | 复用现有设备控制与单设备刷新能力，补充命令链路接入 |

**实现备注**:

- 设备执行优先复用现有 `devices/services.py` 中的控制与单设备刷新能力
- 若后续确实抽象单独执行器，也应以复用现有实现为前提，避免并行维护两套设备控制栈

---

## 9. 实施优先级

建议分阶段实施：

**Phase 1 - 基础能力**:
- analyze_device_intent 函数
- DeviceCommandService（resolve_device_target, check_authorization）
- Mission 模型扩展
- WeChatService 基础改造

**Phase 2 - 执行能力**:
- DeviceExecutor（米家支持）
- 单设备回读更新
- 错误处理和替代方案

**Phase 3 - 增强体验**:
- DeviceContextManager 上下文继承
- DeviceExecutor（美的、HA 支持）
- 语音消息完整支持

**Phase 4 - 测试与优化**:
- 单元测试覆盖
- 集成测试
- Prompt 优化迭代
