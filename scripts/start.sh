#!/bin/bash

# 定位到后端目录
cd "$(dirname "$0")/../backend" || exit

echo "========== Wanny 服务启动脚本 =========="
echo "正在检查并停止残留的后台服务..."

# 使用 pkill 精准匹配 manage.py 的服务名，防止误杀其他无关 python 进程
pkill -f "python manage.py runwechatbot" 2>/dev/null
pkill -f "python manage.py runserver" 2>/dev/null

sleep 1

echo "清理完成！"
echo "========== 启动主 Web API 服务 =========="
# 后台启动 Django 服务器
uv run python manage.py runserver &
DJANGO_PID=$!
echo "[Django API] PID: $DJANGO_PID"

echo "========== 启动微信自动代理守护进程 =========="
# 后台启动 微信机器人 监听服务
uv run python manage.py runwechatbot &
WECHAT_PID=$!
echo "[WeChat Bot] PID: $WECHAT_PID"

echo ""
echo "🚀 两个服务均已在后台启动并将日志合并输出至当前控制台。"
echo "💡 (如果微信未登录，请注意上面终端打印的微信扫码授权链接...)"
echo "🛑 请在此窗口按下 Ctrl + C 即可同时温和停止以上所有服务！"
echo "=========================================="

# 捕捉中断信号 (Ctrl+C 等)，确保一键全停不残留
trap "echo -e '\n\n🛑 接收到停止信号，正在关停所有 Wanny 服务...'; kill $DJANGO_PID $WECHAT_PID 2>/dev/null; exit 0" SIGINT SIGTERM

# 等待后台任务运行，保持主进程不要退出
wait $DJANGO_PID $WECHAT_PID
