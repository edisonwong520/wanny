"""
测试脚本：插入 Brain 模块的 Mock 数据（HomeMode + HabitPolicy）。
用法：uv run python tests/test_insert_mock_data.py
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

from brain.models import HomeMode, HabitPolicy

def run():
    print("清空旧的 Mock 数据...")
    HomeMode.objects.all().delete()
    HabitPolicy.objects.all().delete()

    print("创建测试场景模式: Away (离家)...")
    away_mode = HomeMode.objects.create(name="Away", is_active=True)

    print("创建测试场景模式: Home (在家)...")
    HomeMode.objects.create(name="Home", is_active=False)

    print("创建测试策略: 离家模式下，mocked_light_001 的 power 必须为 off，策略是 ASK...")
    HabitPolicy.objects.create(
        mode=away_mode,
        device_did="mocked_light_001",
        property="power",
        value="off",
        policy=HabitPolicy.PolicyChoices.ASK
    )

    print("创建测试策略: 离家模式下，mocked_ac_002 的 power 必须为 off，策略是 ALWAYS (直接管)...")
    HabitPolicy.objects.create(
        mode=away_mode,
        device_did="mocked_ac_002",
        property="power",
        value="off",
        policy=HabitPolicy.PolicyChoices.ALWAYS
    )

    print("Mock 数据插入完成！Monitor 检测到 mocked_light_001 为 on 时，将触发拦截器。")

if __name__ == "__main__":
    run()
