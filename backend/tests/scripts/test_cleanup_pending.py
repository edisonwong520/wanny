"""
测试脚本：清理数据库中残留的僵尸 PendingCommand 工单。
用法：uv run python tests/test_cleanup_pending.py
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent

# 强制加载最新 .env
load_dotenv(BACKEND_DIR / '.env', override=True)

# 确保 Django 能找到项目模块
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BACKEND_DIR / 'apps'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wanny_server.settings')

import django
django.setup()

from comms.models import Mission

def run():
    count = Mission.objects.filter(status=Mission.StatusChoices.PENDING).count()
    print(f"发现 {count} 条待审批任务，正在清理...")
    Mission.objects.filter(status=Mission.StatusChoices.PENDING).delete()
    print("清理完成！")

if __name__ == "__main__":
    run()
