# Wanny (Wechat+Nanny) 设计文档 v3.0 (Django 版)

## 1. 项目概述 (Overview)

Wanny 是一个连接微信与智能家居的“全能管家”系统。它采用 Django 作为核心后端，利用其强大的管理后台和 ORM，结合 AI 驱动的逻辑，实现对智能家居的监控、控制与主动关怀。

## 2. 系统组成 (System Components)

### 2.1 后端 (Backend - Django 5.x)

- **Core Engine**: 处理设备状态轮询、AI 意图识别及主动决策。
- **Django Admin**: 用于管理用户、设备列表、AI 性格配置及查看习惯记录。
- **Django Channels**: 提供 WebSocket 支持，实现前端状态的实时同步。
- **Device Providers**: 接入米家。
- **Database**: **MySQL** (核心存储)。

### 2.2 前端 (Frontend - Vue 3/Vite)

- **Landing Page**: 现代化风格的产品介绍页。
- **Admin Dashboard**:
  - 实时状态监控（通过 WebSocket 接收 Django Channels 的推送）。
  - 数据可视化看板（生活习惯分析）。

## 3. 目录结构 (Directory Structure)

```text
/wanny
  /backend           # Django 项目根目录 (wanny_server)
    /apps
      /devices       # 设备管理、MiCloud 驱动
      /brain         # LLM Agent、记忆系统
      /comms         # 微信网关 (weclaw) 接入
      /database      # 核心存储与 ORM 模型
      /memory        # 记忆系统实现
      /providers     # 第三方服务接入 (如 MiCloud)
    /wanny_server    # 项目配置、Channels 配置
    manage.py
  /frontend          # Vue 3 项目
  /docs              # 文档
  /tests             # 集成测试 (或移动至 backend/tests)
```

## 4. 关键流程 (Key Workflows)

### 4.1 实时同步 (Django Channels)

1. 后端 `MonitorService` 发现设备状态更新。
2. 通过 `Channels Group` 向所有连接的 WebSocket 客户端发送广播。
3. Vue 3 前端接收并更新 UI。

### 4.2 习惯学习

1. Django 定时任务 (Celery 或简单的 Background Task) 扫描 `device_states`。
2. 提取规律并存入 `UserHabits` 模型。
