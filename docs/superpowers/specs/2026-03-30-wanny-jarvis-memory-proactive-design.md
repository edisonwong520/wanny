# Wanny Jarvis 长期记忆与主动关怀设计规范 v1.0

## 1. 目标 (Objectives)
赋予 Jarvis 持续进化的能力。通过记录、学习并反思用户的对话及行为习惯，构建个性化画像，并在合适的时间点通过微信提供主动的智能建议（如智能家居控制、生活关怀等）。

## 2. 记忆引擎 (Memory Engine)

### 2.1 双轨制存储架构
- **语义向量记忆 (Memory A - Assistant)**: 
    - **存储**: 使用向量数据库（如 ChromaDB/FAISS）存储原始对话片段和操作日志。
    - **用途**: 提供基于语义相似度的实时上下文检索。
- **结构化画像 (Memory B - Core)**:
    - **存储**: Django 数据库表 (`UserProfile`)，包含结构化的偏好（例如：`preferred_temp`, `frequent_movie_genres`, `bedtime_routine`）。
    - **用途**: 作为 Jarvis 决策的核心准则，提供高确定性的行为预测。

## 3. 提取与进化逻辑 (Insight & Evolution)

### 3.1 定时复盘机制 (Daily Review)
- **触发**: 每 24 小时（默认凌晨 3 点）执行一次 Celery 任务或 Cron 脚本。
- **逻辑**: 汇总过去 24 小时的所有对话流和设备操作记录，交给 Gemini 进行反思（Reflection），并生成画像更新建议。
- **更新示例**: "Sir 最近三天都在 20:00 左右打开了空气净化器，建议更新画像：`prefers_air_purifier_at_evening = true`。"

### 3.2 评分与推送算法 (Proactive Scoring)
- **Impact Score**: 每条建议根据“环境紧急度”、“画像匹配度”和“近期反馈权重”计算分值。
- **门禁控制**: 只有分值超过预设阈值时，才会通过微信发送推送，防止过度打扰。

## 4. 主动关怀场景示例 (Scenarios)
- **环境预警**: "Sir, 监测到室内 PM2.5 超标且您在家，是否为您开启空气净化器？"
- **习惯建议**: "Sir, 您平时周五晚上都会看科幻电影，我为您搜到了几部新资源，需要安排下载吗？"
- **模式提议**: "Sir, 我发现您最近睡觉时间提前了，需要我根据您的新习惯调整‘睡眠模式’的触发时间吗？"

## 5. 数据模型设计 (Data Models)

### 5.1 `UserProfile` (用户画像)
- `category`: 类别 (Environment, Entertainment, Habit, etc.)
- `key`: 偏好键 (e.g., "preferred_temp")
- `value`: 偏好值 (e.g., "24")
- `confidence`: 置信度 (0.0 - 1.0)
- `last_confirmed`: 上次用户确认的时间

### 5.2 `ProactiveLog` (推送日志)
- `message`: 推送内容
- `feedback`: 用户反馈 (APPROVED, DENIED, IGNORED)
- `score`: 推送时的评分
