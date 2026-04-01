# Wanny (Wechat+Nanny) Backend

Wanny 是一个连接微信与智能家居的“全能管家”系统。它采用 Django 作为核心后端，利用其强大的管理后台和 ORM，结合 AI 驱动的逻辑，实现对智能家居的监控、控制与主动关怀。

## 🚀 技术栈 (Tech Stack)

*   **核心框架:** Django 5.x, Python 3.12+ 
*   **依赖管理:** [uv](https://github.com/astral-sh/uv)
*   **通信架构:** Django Channels (WebSocket 服务), Uvicorn / Daphne
*   **核心存储:** MySQL

## 📁 核心应用结构 (App Architecture)

本项目采用模块化单体架构，所有的核心业务逻辑被封装在 `apps/` 目录下的各个子模块中：

*   `apps/brain`: LLM 核心代理、意图识别与大语言模型通信层
*   `apps/comms`: 微信环境网关及消息接收器 (对接 WeChat)
*   `apps/database`: 核心业务存储及领域数据模型
*   `apps/memory`: 记忆管理系统，负责用户的短期/长期记忆存留与上下文分析
*   `apps/providers`: 外部第三方服务及 API 接入（核心云端能力接入）
*   `apps/devices`: 硬件设备网关（例如 MiCloud 设备轮询及控制）

## ⚙️ 快速开始 (Getting Started)

### 1. 安装配置环境

项目使用 `uv` 管理所有的 Python 依赖包。

```bash
# 确保你已经安装了 uv (https://docs.astral.sh/uv/)
# 在具有 uv 的环境下执行依赖拉取
uv sync
```

### 2. 数据库配置

默认配置将寻找对应的数据库参数。如果使用 MySQL，由于驱动依赖，可能需要确保系统中存在原生的  `mysql-client` 及 `pkg-config` 依赖：

* **macOS:** `brew install mysql-client pkg-config`
* **Linux (Ubuntu):** `sudo apt install libmariadb-dev pkg-config`

配置好 `.env`（如果需要）并将数据库指向 MySQL。

### 3. 本地运行

在正确初始化依赖且建好表结构后，可以运用 `uv run` 挂载 Django 启动服务。

```bash
# 执行数据库迁移
uv run manage.py makemigrations
uv run manage.py migrate

# 启动 Django 测试服务器
uv run manage.py runserver 
```

若想要测试或启动基于 Channels 提供 WebSocket 能力的异步监听，你可以利用 daphne：

```bash
uv run daphne wanny_server.asgi:application
```

### 4. 运行 Python 脚本 (执行数据库查询/调试)

当需要运行涉及 Django ORM 的 Python 脚本时，**必须使用 `uv run python`**，而不是 `uv run manage.py shell`：

```bash
# 正确方式：使用 uv run python 并手动调用 django.setup()
uv run python -c "
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wanny_server.settings')
django.setup()

from accounts.models import Account
# 现在可以正常使用 Django ORM
account = Account.objects.filter(id=1).first()
print(account.email)
"

# 错误方式：uv run manage.py shell -c "..." 会有模块导入问题
```

**注意：** 所有 Django 脚本必须包含以下初始化代码：
```python
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wanny_server.settings')
django.setup()
```

## 📖 参考文档

关于 Wanny 进一步的需求意图与技术规范细节，请参阅根目录的 `docs/` 文档库，尤其是架构规划设计：
- `docs/superpowers/specs/2026-03-29-wanny-design.md`
