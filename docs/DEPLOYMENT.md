# Docker 部署指南

本文档说明如何用 Docker Compose 在单机或 VPS 上部署 Wanny。默认部署包含：

- MySQL 8.4
- Redis 7
- Django backend，使用 Daphne/ASGI 启动
- Vue frontend，使用 nginx 托管并反向代理 `/api/`

可选服务：

- `worker`: 设备同步 worker
- `wechatbot`: 微信 bot 运行进程

## 前置条件

服务器需要安装：

- Docker Engine
- Docker Compose v2
- Git

建议服务器至少准备 2 CPU / 4 GB RAM。若开启真实 AI 语义、Chroma 向量检索、多个设备平台同步，建议更高配置。

## 1. 拉取代码

```bash
git clone <your-repo-url> wanny
cd wanny
git submodule update --init --recursive
```

如果你的环境不需要参考子模块，也可以先跳过 submodule，但部分第三方适配开发资料会缺失。

## 2. 准备 Docker Compose 环境变量

复制 Compose 环境示例：

```bash
cp docker/.env.example docker/.env
```

编辑 `docker/.env`：

```env
MYSQL_ROOT_PASSWORD=change-this-root-password
MYSQL_DATABASE=wanny
MYSQL_USER=wanny
MYSQL_PASSWORD=change-this-app-password
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,your-domain.example
VITE_API_BASE_URL=
```

说明：

- `MYSQL_ROOT_PASSWORD` 和 `MYSQL_PASSWORD` 必须改成强密码。
- `DJANGO_ALLOWED_HOSTS` 需要包含你访问服务使用的域名或公网 IP。
- 当前 compose 让前端 nginx 和后端共用同一源，`VITE_API_BASE_URL` 通常保持为空即可。

## 3. 准备后端环境变量

复制后端环境示例：

```bash
cp backend/.env.example backend/.env
```

至少修改下面这些项：

```env
DJANGO_SECRET_KEY=<generate-a-long-random-secret>
DJANGO_DEBUG=False

AI_BASE_URL=<your-openai-compatible-base-url>
AI_API_KEY=<your-ai-api-key>
AI_MODEL=<your-model>

GEMINI_API_KEY=<optional-google-gemini-key>
EMBEDDING_API_KEY=<optional-google-gemini-embedding-key>
```

生成 Django secret key 的示例：

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
```

数据库和 Redis 在 compose 中会被容器环境变量覆盖，因此 `backend/.env` 里的 `DB_HOST=127.0.0.1`、`REDIS_URL=redis://127.0.0.1:6379/0` 不需要手动改成容器地址。

## 4. 构建并启动基础服务

```bash
docker compose --env-file docker/.env up -d --build
```

首次启动时，`backend` 容器会自动执行：

```bash
uv run python manage.py migrate
```

然后启动 Daphne：

```bash
uv run daphne -b 0.0.0.0 -p 8000 wanny_server.asgi:application
```

查看服务状态：

```bash
docker compose --env-file docker/.env ps
```

查看日志：

```bash
docker compose --env-file docker/.env logs -f backend
docker compose --env-file docker/.env logs -f frontend
```

默认访问地址：

```text
http://localhost:8080/wanny/
```

如果部署在服务器上，把 `localhost` 换成服务器域名或公网 IP。

## 5. 初始化后台数据

进入后端容器运行管理命令：

```bash
docker compose --env-file docker/.env exec backend uv run python manage.py createsuperuser
docker compose --env-file docker/.env exec backend uv run python manage.py seedsystemkeywords
```

管理后台入口：

```text
http://localhost:8080/admin/
```

## 6. 启动可选 worker

设备同步 worker 默认不随基础服务启动。需要 Redis 队列处理时运行：

```bash
docker compose --env-file docker/.env --profile worker up -d worker
```

查看 worker 日志：

```bash
docker compose --env-file docker/.env logs -f worker
```

停止 worker：

```bash
docker compose --env-file docker/.env stop worker
```

## 7. 启动微信 bot

微信 bot 依赖你先在控制台完成微信授权，或者已有可用的授权记录。启动：

```bash
docker compose --env-file docker/.env --profile wechat up -d wechatbot
```

查看日志：

```bash
docker compose --env-file docker/.env logs -f wechatbot
```

如果日志显示正在等待微信授权，先打开控制台完成授权流程。

## 8. 持久化数据

Compose 使用 Docker volumes 保存运行数据：

- `mysql_data`: MySQL 数据
- `redis_data`: Redis 数据
- `backend_chroma`: Chroma 向量库
- `backend_credentials`: 第三方平台凭据文件
- `backend_logs`: 后端日志
- `backend_runtime_cache`: 运行时缓存

查看 volumes：

```bash
docker volume ls | grep wanny
```

备份 MySQL：

```bash
docker compose --env-file docker/.env exec mysql \
  mysqldump -u root -p"${MYSQL_ROOT_PASSWORD}" wanny > wanny-backup.sql
```

如果 shell 没有加载 `MYSQL_ROOT_PASSWORD`，可以直接输入密码：

```bash
docker compose --env-file docker/.env exec mysql \
  mysqldump -u root -p wanny > wanny-backup.sql
```

## 9. 更新部署

```bash
git pull
git submodule update --init --recursive
docker compose --env-file docker/.env up -d --build
```

`backend` 容器启动时会自动执行迁移。更新后建议看一次日志：

```bash
docker compose --env-file docker/.env logs -f backend
```

## 10. 生产反向代理建议

Compose 内置 nginx 只负责容器内前端托管和 API 代理。公网生产环境建议在宿主机或云服务层再放一层 HTTPS 反向代理，例如 Caddy、Traefik 或 Nginx。

外层反代到：

```text
http://127.0.0.1:8080
```

需要保留：

- `/wanny/` 前端路径
- `/api/` 后端 API 路径
- `/admin/` Django 管理后台路径

如果前端和后端拆成不同域名部署，需要设置：

- `docker/.env` 中的 `VITE_API_BASE_URL`
- `docker/.env` 中的 `DJANGO_ALLOWED_HOSTS`
- 额外的 CORS/CSRF 策略。目前仓库默认按同源部署设计，推荐优先使用同源反代。

## 11. 常用排查命令

检查收集到的默认测试：

```bash
docker compose --env-file docker/.env exec backend uv run pytest --collect-only -q
```

运行默认测试：

```bash
docker compose --env-file docker/.env exec backend uv run pytest -q
```

进入后端 shell：

```bash
docker compose --env-file docker/.env exec backend sh
```

检查数据库连接：

```bash
docker compose --env-file docker/.env exec backend uv run python manage.py showmigrations
```

重启服务：

```bash
docker compose --env-file docker/.env restart backend frontend
```

完全停止基础服务：

```bash
docker compose --env-file docker/.env down
```

谨慎删除全部持久化数据：

```bash
docker compose --env-file docker/.env down -v
```

`down -v` 会删除数据库、向量库、凭据和缓存数据，只应在确认要重建环境时使用。
