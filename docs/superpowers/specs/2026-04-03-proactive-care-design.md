# 主动巡检与人文关怀功能设计

## 1. 功能概述

为 Wanny 增加"主动巡检"和"人文关怀"两类智能建议能力：

- **主动巡检**：设备保养提醒（滤芯更换、清洁周期）、健康监控（离线、异常功耗）、用户自定义规则
- **人文关怀**：环境联动（天气变化→设备调节）、生活节奏（作息习惯）、特殊事件（极端天气、节假日）

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
    aggregated_from: list[int]                         # 合并来源 ID 列表
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
  "ha_entity_id": "weather.home",
  "ha_base_url": "http://homeassistant.local:8123"
}
```

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
    ├── source_type = "care_suggestion"
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
├── comms/                   # 扩展
│   ├── models.py           # Mission 增加 source_type: "care_suggestion"
│   └── executor.py         # 支持 CareSuggestion 关联
│
├── memory/                  # 扩展
│   ├── models.py           # ProactiveLog 增加 source: "care"
│   └── services.py         # 支持画像融合
```

### 4.2 服务职责

| 服务 | 职责 | 输入 | 输出 |
|------|------|------|------|
| InspectionScanner | 定时巡检 | InspectionRule 列表 | 原始建议列表 |
| SuggestionAggregator | 聚合去重 | 原始建议 | CareSuggestion |
| CareEventProcessor | 事件处理 | 天气/设备变化 | 原始建议 |
| WeatherDataService | 天气获取 | 位置、配置 | 天气快照 |
| FeedbackLearner | 反馈学习 | 用户反馈 | 权重 + UserProfile |

### 4.3 定时任务配置

```python
CELERYBEAT_SCHEDULE = {
    'inspection-daily': {
        'task': 'care.services.scanner.run_daily_inspection',
        'schedule': crontab(hour=8, minute=0),
    },
    'weather-fetch': {
        'task': 'care.services.weather.fetch_weather_data',
        'schedule': crontab(minute='*/30'),
    },
    'rule-specific-checks': {
        'task': 'care.services.scanner.run_rule_checks',
        'schedule': crontab(minute='*/5'),
    },
}
```

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
├── CareRulesPage.vue        # 规则配置
│   ├── 系统预置规则
│   ├── 用户自定义规则
│   ├── 启用/禁用开关
│   └── 频率调整
│
└── SettingsPage.vue         # 扩展
    └── 天气 API 配置
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
- **aggregated_from** 记录原始 ID 列表

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

### 9.1 单元测试

```
tests/unit/care/
├── test_scanner.py
├── test_aggregator.py
├── test_processor.py
├── test_learner.py
├── test_weather.py
└── test_rule_condition.py
```

### 9.2 集成测试

```
tests/integration/care/
├── test_inspection_flow.py
├── test_care_event_flow.py
├── test_feedback_learning.py
├── test_execution_chain.py
├── test_aggregation_merge.py
└── test_external_data_source.py
```

### 9.3 验证脚本

```
tests/scripts/care/
├── simulate_weather_change.py
├── simulate_device_telemetry.py
├── test_push_notification.py
└── benchmark_aggregator.py
```

## 10. 实施里程碑

### Phase 1 - 基础框架（1-2 周）

- 数据模型：CareSuggestion, InspectionRule, ExternalDataSource
- InspectionScanner（基础定时巡检）
- SuggestionAggregator（简单聚合）
- 建议列表 API + CareCenterPage 基础展示
- 微信推送集成

### Phase 2 - 事件驱动与天气（1 周）

- CareEventProcessor
- WeatherDataService（天气 API + HA 双源）
- 外部数据源配置 API
- 前端天气展示

### Phase 3 - 智能聚合与学习（1 周）

- 完整聚合逻辑
- 优先级计算公式
- FeedbackLearner（权重 + 画像融合）
- 分批推送策略

### Phase 4 - 规则配置（1 周）

- CareRulesPage
- 规则 CRUD API
- 用户自定义规则
- condition_spec 校验与可视化配置

## 11. 技术依赖

| 依赖 | 用途 | 状态 |
|------|------|------|
| Celery/APScheduler | 定时任务 | 已有 |
| Django ORM | 数据模型 | 已有 |
| 微信 iLink SDK | 推送 | 已有 |
| Mission/DeviceExecutor | 执行链路 | 复用 |
| 天气 API | 外部数据 | 新增配置 |
| UserProfile/ProactiveLog | 记忆系统 | 扩展复用 |