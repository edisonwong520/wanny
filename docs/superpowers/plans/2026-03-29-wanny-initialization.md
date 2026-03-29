# Wanny 后端项目初始化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将根目录的功能组件移动到 `backend/apps/` 目录下，并使用 `uv` 初始化一个单体 Django 项目。

**Architecture:** 采用 Django + Django Channels 的单体架构，所有核心逻辑封装在 `backend/apps/` 下的独立 App 中，通过 `sys.path` 扩展实现干净的导入。

**Tech Stack:** Python 3.12, UV, Django 5.x, Django Channels, MySQL, Uvicorn.

---

### Task 1: 目录结构重组 (Directory Restructuring)

**Files:**
- Move: `brain/` -> `backend/apps/brain/`
- Move: `comms/` -> `backend/apps/comms/`
- Move: `database/` -> `backend/apps/database/`
- Move: `memory/` -> `backend/apps/memory/`
- Move: `providers/` -> `backend/apps/providers/`
- Move: `tests/` -> `backend/tests/`
- Delete: `backend/main.py` (不再需要，改为 Django 入口)

- [ ] **Step 1: 创建目标目录并移动现有模块**

Run:
```bash
mkdir -p backend/apps
mv brain comms database memory providers backend/apps/
mv tests backend/tests
rm backend/main.py
```

- [ ] **Step 2: 验证目录结构**

Run: `ls -R backend/apps`
Expected: 看到各模块已成功移动。

- [ ] **Step 3: Commit**

```bash
git add .
git commit -m "refactor: move core modules to backend/apps and cleanup root"
```

---

### Task 2: 使用 UV 初始化后端环境 (UV Initialization)

**Files:**
- Modify: `backend/pyproject.toml`
- Create: `backend/.python-version`

- [ ] **Step 1: 更新 `pyproject.toml` 并安装依赖**

```bash
cd backend
uv add django django-channels daphne mysqlclient uvicorn
```

- [ ] **Step 2: 验证环境**

Run: `uv run python -m django --version`
Expected: 输出 Django 5.x 版本号。

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "chore: initialize uv environment and add django dependencies"
```

---

### Task 3: 创建 Django 项目与配置 (Django Project Setup)

**Files:**
- Create: `backend/manage.py`
- Create: `backend/wanny_server/settings.py`
- Modify: `backend/wanny_server/settings.py` (添加 apps 路径)

- [ ] **Step 1: 初始化 Django 项目**

Run:
```bash
cd backend
uv run django-admin startproject wanny_server .
```

- [ ] **Step 2: 配置 `settings.py` 以支持 `apps/` 目录**

在 `backend/wanny_server/settings.py` 顶部添加：
```python
import os
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, os.path.join(BASE_DIR, 'apps'))
```

并在 `INSTALLED_APPS` 中注册这些 app。

- [ ] **Step 3: 验证 Django 启动**

Run: `uv run python manage.py check`
Expected: System check identified no issues.

- [ ] **Step 4: Commit**

```bash
git add manage.py wanny_server/
git commit -m "feat: initialize django project wanny_server"
```

---

### Task 4: 将模块转换为 Django Apps (Convert to Apps)

**Files:**
- Create: `backend/apps/*/apps.py`
- Create: `backend/apps/*/__init__.py`

- [ ] **Step 1: 为每个模块添加 `apps.py` 配置**

例如 `backend/apps/brain/apps.py`:
```python
from django.apps import AppConfig

class BrainConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'brain'
```

- [ ] **Step 2: 验证导入**

Run: `uv run python manage.py shell -c "import brain; print('Brain app loaded')"`
Expected: 输出 "Brain app loaded"。

- [ ] **Step 3: Commit**

```bash
git add backend/apps/
git commit -m "feat: convert core modules to django apps"
```
