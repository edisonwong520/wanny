# 主动巡检与人文关怀功能设计

## 1. 功能概述

为 Wanny 增加"主动巡检"和"人文关怀"两类智能建议能力。

当前主干实现状态：
- `care` 独立应用、数据模型、基础 API、前端 `CareCenterPage/CareRulesPage` 已落地
- 定时巡检、天气抓取、微信主动推送均已接入 APScheduler / WeChat bot 常驻循环
- `FeedbackLearner` 已接入 `ProactiveLog + UserProfile`
- 系统规则初始化、天气源配置、HA 天气实体读取、缓存降级已可用
- 规则配置器单位感知/推荐值联动、关怀中心 push audit、`tests/scripts/care/` 脚本目录已补齐
- `CareSuggestionCard.vue`、`ConfirmActionDialog.vue` 已拆分为独立组件
- 关怀中心已提供推送策略总览卡；聚合来源已语义化到规则名 / 数据源名 / 事件说明
- 规则配置器已扩充更多字段预设，并支持建议模板快捷插入

- **主动巡检**：设备保养提醒（滤芯更换、低水位）、健康监控（离线）、用户自定义规则
- **人文关怀**：环境联动（天气变化→设备调节）、后续可继续扩展生活节奏与特殊事件

**核心特性**：
- 时间驱动 + 事件驱动混合触发
- 微信 + 控制台双通道同步推送
- 二次确认执行机制
- 智能聚合避免消息轰炸
- 用户反馈学习闭环

## 2. 核心概念模型

### 2.1 InspectionRule（巡检规则）

```python
class InspectionRule:
    rule_type: "maintenance" | "health" | "custom"     # 规则类型
    device_category: str                               # 设备类型（如 "water_purifier"）
    name: str                                          # 规则名称
    description: str                                   # 规则说明
    check_frequency: str                               # 检查频率（cron 或预设值）
    condition_spec: dict                               # 条件规格
    suggested_action: str                              # 建议操作类型
    suggestion_template: str                           # 建议文案模板
    priority: int                                      # 基础优先级（1-10）
    is_system_default: bool                            # 是否系统预置
    is_active: bool                                    # 是否启用
    account: Account | None                            # 关联账户（null=全局规则）
```

**condition_spec 结构示例**：
```json
{
  "field": "telemetry.filter_life_percent",
  "operator": "<",
  "threshold": 20,
  "unit": "%"
}
```

### 2.2 CareSuggestion（关怀建议）

```python
class CareSuggestion:
    suggestion_type: "inspection" | "care"             # 建议类型
    source_rule: InspectionRule | None                 # 关联规则（巡检类）
    source_event: dict | None                          # 关联事件（关怀类）
    device: DeviceSnapshot | None                      # 关联设备
    title: str                                         # 建议标题
    body: str                                          # 建议详情（AI 生成）
    action_spec: dict                                  # 可执行操作描述
    control_target: DeviceControl | None               # 执行目标
    priority: float                                    # 计算后优先级
    status: "pending" | "approved" | "rejected" | "ignored" | "executed"
    user_feedback: dict                                # 用户反馈记录
    feedback_collected_at: datetime                    # 反馈时间
    aggregated_from: list[int | str]                  # 合并来源标识（规则 ID / 源 ID）
    created_at: datetime
    account: Account
```

### 2.3 ExternalDataSource（外部数据源）

```python
class ExternalDataSource:
    source_type: "weather_api" | "ha_entity" | "other"
    name: str                                          # 数据源名称
    config: dict                                       # 配置详情
    fetch_frequency: str                               # 获取频率
    last_fetch_at: datetime                            # 上次获取时间
    last_data: dict                                    # 最新数据快照
    is_active: bool                                    # 是否启用
    account: Account
```

**天气 API 配置示例**：
```json
{
  "api_key": "xxx",
  "endpoint": "https://api.qweather.com",
  "location": "上海"
}
```

**HA 实体配置示例**：
```json
{
  "ha_entity_id": "weather.home"
}
```

说明：
- HA 鉴权不放在 `ExternalDataSource.config`，而是复用现有 `home_assistant` Provider 授权
- `weather_api` 既支持 Open-Meteo，也支持自定义 endpoint/params/字段路径

## 3. 触发与执行流程

### 3.1 定时巡检流程（时间驱动）

```
[定时任务触发]
    ↓
[InspectionScanner 扫描活跃规则]
    ↓
[执行规则检查]
    ├── 读取设备遥测数据
    ├── 计算 condition_spec
    └── 生成候选建议
    ↓
[SuggestionAggregator 聚合处理]
    ├── 按设备/类型分组
    ├── 合并同类建议
    └── 计算最终优先级
    ↓
[存入 CareSuggestion]
    ↓
[推送到微信 + 控制台]
    ↓
[等待用户反馈]
```

### 3.2 事件驱动流程（关怀类）

```
[外部数据更新]
    ├── 天气 API 返回新数据
    └── HA 天气实体状态变化
    ↓
[CareEventProcessor 处理]
    ├── 解析事件类型
    ├── 匹配关怀规则
    └── 生成候选建议
    ↓
[SuggestionAggregator] → [推送] → [等待反馈]
```

### 3.3 用户反馈处理流程

```
[用户点击"采纳"]
    ↓
[创建 Mission 任务]
    ├── 当前复用 source_type = "device_control"
    └── 解析 action_spec
    ↓
[展示二次确认详情]
    ├── 设备、控制项、目标值
    └── 预期效果说明
    ↓
[用户确认执行]
    ↓
[DeviceExecutor 执行控制]
    ↓
[更新状态为 "executed"]
    ↓
[FeedbackLearner 反馈学习]
    ├── 更新 ProactiveLog
    ├── 调整同类建议权重
    └── 写入 UserProfile
```

## 4. 模块划分

### 4.1 后端模块结构

```
backend/apps/
├── care/                    # 新增独立应用
│   ├── models.py           # CareSuggestion, InspectionRule, ExternalDataSource
│   ├── services/
│   │   ├── scanner.py      # InspectionScanner
│   │   ├── aggregator.py   # SuggestionAggregator
│   │   ├── processor.py    # CareEventProcessor
│   │   ├── learner.py      # FeedbackLearner
│   │   └── weather.py      # WeatherDataService
│   ├── management/commands/
│   │   └── runinspection.py
│   ├── urls.py
│   └── views.py
│   └── migrations/
│
├── devices/                 # 扩展
│   └── monitor.py          # 增加事件订阅
│
├── comms/                   # 复用
│   ├── models.py           # 当前复用既有 Mission.SourceTypeChoices.DEVICE_CONTROL
│   └── management/commands/runwechatbot.py
│
├── memory/                  # 扩展
│   ├── models.py           # ProactiveLog 增加 source: "care"
│   └── services.py         # 支持画像融合
```

### 4.2 服务职责

| 服务 | 职责 | 输入 | 输出 |
|------|------|------|------|
| InspectionScanner | 定时巡检 | InspectionRule 列表 | CareSuggestion |
| SuggestionAggregator | 聚合去重/合并更新 | 候选建议 | CareSuggestion |
| CareEventProcessor | 事件处理 | 天气/设备变化 | CareSuggestion |
| WeatherDataService | 天气获取 | 位置、配置 | 天气快照 |
| FeedbackLearner | 反馈学习 | 用户反馈 | 权重 + UserProfile |
| CarePushService | 微信分批推送 | 待处理建议 | 微信消息投递 |

### 4.3 定时任务配置

```python
register_default_schedules(...)
├── run_periodic_inspection           # 每 1 小时
├── fetch_weather_and_generate_care   # 每 30 分钟
└── deliver_care_suggestions          # 每 15 分钟
```

当前实现说明：
- 项目使用 APScheduler 4 持久化调度，不使用 Celery Beat
- WeChat bot 进程内还会额外启动 `CarePushService.loop_start(bot)`，在活跃微信上下文存在时尝试主动推送

## 5. 前端界面

### 5.1 页面结构

```
frontend/src/pages/console/
├── CareCenterPage.vue       # 关怀中心
│   ├── 建议卡片列表
│   ├── 快速操作按钮
│   ├── 二次确认弹窗
│   └── 规则配置入口
│
├── CareRulesPage.vue        # 规则配置 + 天气源配置
│   ├── 系统预置规则
│   ├── 用户自定义规则
│   ├── condition builder
│   ├── 启用/禁用开关
│   └── 天气源配置
│
frontend/src/components/console/care/
├── CareSuggestionCard.vue   # 建议卡片
└── ConfirmActionDialog.vue  # 执行确认弹窗
```

### 5.2 建议卡片组件

```
CareSuggestionCard.vue
├── 类型图标（巡检🔧/关怀💡）
├── 优先级色标
├── 标题 + 详情描述
├── 关联设备标签
├── [采纳] → 二次确认弹窗
├── [拒绝] → 原因输入
├── [忽略] → 静默处理
└── 合并提示（如"合并了 3 个同类提醒"）
```

### 5.3 二次确认弹窗

```
ConfirmActionDialog.vue
├── 操作标题
├── 目标设备、当前状态、目标状态
├── 执行说明
├── [确认执行]
├── [取消]
└── 实时执行结果反馈
```

## 6. API 设计

### 6.1 关怀建议 API

```
GET  /api/care/suggestions/
     ?status=pending|approved|rejected|ignored|executed
     &priority=high|medium|low
     &suggestion_type=inspection|care

POST /api/care/suggestions/{id}/feedback/
     { action: "approve" | "reject" | "ignore", reason?: string }

GET  /api/care/suggestions/{id}/confirm-detail/

POST /api/care/suggestions/{id}/execute/
     { confirmed: true }
```

### 6.2 规则管理 API

```
GET  /api/care/rules/

POST /api/care/rules/
     { rule_type, device_category, name, check_frequency, condition_spec, ... }

PUT  /api/care/rules/{id}/

DELETE /api/care/rules/{id}/    # 仅可删除用户自定义规则
```

### 6.3 外部数据源 API

```
GET  /api/care/data-sources/

POST /api/care/data-sources/
     { source_type, name, config, fetch_frequency }

PUT  /api/care/data-sources/{id}/

GET  /api/care/weather/current/
     返回当前天气快照
```

## 7. 智能聚合与优先级

### 7.1 聚合规则

- **按设备分组**：同一设备多条建议合并
- **按规则类型分组**：同类巡检规则合并
- **按时间窗口分组**：短时间内同类建议合并
- **aggregated_from** 记录规则 ID / 源 ID 列表

当前实现说明：
- 当前主聚合键基于 `device/control/field` 或天气事件源 `dedupe_key`
- 命中重复时不会新建，而是更新已有 `CareSuggestion` 的 `aggregated_count / aggregated_from / source_event`
- 当前 `GET /api/care/suggestions/` 会额外返回 `aggregationSources`，前端展示为规则名、数据源名或事件说明，而不是直接显示 marker

### 7.2 优先级计算公式

```
priority_score = (
    rule_base_priority ×
    urgency_factor ×
    profile_match_factor ×
    feedback_adjust_factor
)
```

**紧急度系数**：
- 滤芯寿命 < 10%：2.0
- 滤芯寿命 10-20%：1.5
- 设备离线 > 24h：1.8
- 天气骤降 > 10°C：1.5

**反馈调节系数**：
- 上次拒绝同类：0.7
- 连续 3 次拒绝：0.3
- 上次采纳同类：1.1

### 7.3 分批推送策略

- 单次推送上限：3 条
- 优先推送最高优先级
- 高优先级（>7）：立即推送
- 中优先级（4-7）：每小时最多 1 次
- 低优先级（<4）：仅控制台展示
- 同设备同类建议 24h 冷却
- 用户忽略建议 48h 冷却

当前实现状态：
- 已实现：单次最多 3 条、高优先级优先、中优先级每小时限 1 次、低优先级仅控制台、24h 重复推送间隔、忽略后 48h 冷却
- 已实现：关怀中心详情页展示 push audit，包括推送等级、最近推送时间、再次可推送时间、忽略冷却截止与抑制原因
- 已实现：关怀中心左侧提供推送策略总览卡，聚合展示高/中/低优先级、仅控制台、忽略冷却和重复推送冷却数量

## 8. 错误处理

| 场景 | 处理策略 |
|------|----------|
| 天气 API 失败 | 降级使用缓存，标记 `degraded` |
| 设备遥测缺失 | 跳过巡检，标记 `incomplete` |
| 控制执行失败 | 状态 `failed`，推送失败通知 |
| 连续拒绝同类 | 降低规则优先级，审视提醒 |
| 条件配置错误 | 创建时校验，拒绝保存 |

**数据一致性**：
- 天气缓存 30 分钟
- 设备遥测复用 DeviceSnapshot
- CareSuggestion 与 Mission 状态同步

## 9. 测试策略

### 9.1 当前测试覆盖

```
backend/tests/unit/
├── test_care_scanner.py
├── test_care_weather.py
├── test_care_push.py
└── test_scheduler_registration.py
```

### 9.2 当前集成测试覆盖

```
backend/tests/integration/
├── test_care_api.py
├── test_care_weather_api.py
└── test_care_push_flow.py
```

### 9.3 验证脚本

```
tests/scripts/care/
├── simulate_weather_change.py
├── simulate_device_telemetry.py
├── test_push_notification.py
└── benchmark_aggregator.py
```

补充说明：
- `test_care_api.py` 已覆盖 `pushAudit` 序列化字段
- `test_care_push.py` 已覆盖忽略后 48h 冷却

## 10. 实施里程碑

### Phase 1 - 基础框架
- 已完成：数据模型、InspectionScanner、CareCenterPage、建议 API、微信推送主链路

### Phase 2 - 事件驱动与天气
- 已完成：CareEventProcessor、WeatherDataService（天气 API + HA 双源）、外部数据源配置 API、前端天气展示

### Phase 3 - 智能聚合与学习
- 已完成：完整聚合逻辑、优先级调节、FeedbackLearner、分批推送策略、忽略后 48h 冷却、关怀中心 push audit 展示

### Phase 4 - 规则配置
- 已完成：CareRulesPage、规则 CRUD API、用户自定义规则、condition_spec 校验、condition builder、字段推荐值/单位感知联动、更多字段预设、建议模板快捷插入
- 剩余细化：拖拽式模板

### Phase 5 - 脚本与组件整理
- 已完成：`tests/scripts/care/` 脚本目录、`CareSuggestionCard.vue`、`ConfirmActionDialog.vue`

### Phase 6 - 可视化解释
- 已完成：推送策略总览卡、push audit、聚合来源语义化展示

## 12. 当前剩余工作

- 文档与 README 持续对齐
- 规则配置器拖拽式模板编排
- 更多 care 自动化测试

## 11. 技术依赖

| 依赖 | 用途 | 状态 |
|------|------|------|
| Celery/APScheduler | 定时任务 | 已有 |
| Django ORM | 数据模型 | 已有 |
| 微信 iLink SDK | 推送 | 已有 |
| Mission/DeviceExecutor | 执行链路 | 复用 |
| 天气 API | 外部数据 | 新增配置 |
| UserProfile/ProactiveLog | 记忆系统 | 扩展复用 |
