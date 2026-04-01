"""
连接真实 Home Assistant，基于本地已有快照数据验证冰箱冷藏区温度控制是否可下发。

默认行为：
1. 读取数据库中的有效 HA 授权；
2. 直接从本地已有的 DeviceSnapshot / DeviceControl 中定位设备和控件；
3. 下发目标温度（默认 2°C）；
4. 不主动 refresh，不重新拉取 HA 图谱。

运行示例：
    cd backend
    uv run python tests/scripts/verify_ha_fridge_temperature_control_live.py --email 1404233501@qq.com

    uv run python tests/scripts/verify_ha_fridge_temperature_control_live.py \
      --email 1404233501@qq.com \
      --device-name 多开门冰箱 \
      --target 2
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BACKEND_DIR / "apps"))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "wanny_server.settings")

import django

django.setup()

from accounts.models import Account
from devices.models import DeviceSnapshot
from devices.models import DeviceControl
from devices.services import DeviceDashboardService
from providers.models import PlatformAuth
from providers.services import HomeAssistantAuthService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="验证真实 HA 冰箱冷藏区温度控制")
    parser.add_argument("--email", help="账户邮箱；如果不传，则自动尝试选择唯一有效的 HA 授权账户")
    parser.add_argument("--device-name", default="多开门冰箱", help="目标设备名称，默认：多开门冰箱")
    parser.add_argument("--group-label", default="冷藏区", help="目标控件分组，默认：冷藏区")
    parser.add_argument("--target", type=float, default=2, help="目标温度，默认：2")
    return parser.parse_args()


def pick_account(email: str | None) -> Account:
    queryset = PlatformAuth.objects.filter(
        is_active=True,
        platform_name__in=HomeAssistantAuthService.platform_aliases,
        account__isnull=False,
    ).select_related("account").order_by("account__email", "platform_name")

    if email:
        auth = queryset.filter(account__email=email).first()
        if not auth or not auth.account:
            raise SystemExit(f"未找到邮箱为 {email} 的有效 Home Assistant 授权")
        return auth.account

    accounts = []
    seen = set()
    for auth in queryset:
        if auth.account_id in seen:
            continue
        seen.add(auth.account_id)
        account = auth.account
        if account is not None:
            accounts.append(account)

    non_test_accounts = [
        account for account in accounts
        if not account.email.endswith("@example.com")
    ]

    if len(non_test_accounts) == 1:
        return non_test_accounts[0]
    if len(accounts) == 1:
        return accounts[0]

    print("检测到多个有效的 HA 授权账户，请显式传入 --email：")
    for account in non_test_accounts or accounts:
        print(f"  - {account.email}")
    raise SystemExit(2)


def find_device(account: Account, device_name: str) -> DeviceSnapshot:
    queryset = DeviceSnapshot.objects.filter(
        account=account,
        external_id__startswith="home_assistant:",
    ).order_by("sort_order", "id")

    exact = list(queryset.filter(name=device_name))
    if len(exact) == 1:
        return exact[0]

    fuzzy = list(queryset.filter(name__icontains=device_name))
    if len(fuzzy) == 1:
        return fuzzy[0]

    fridge_like = list(queryset.filter(category__icontains="冰箱")) or list(queryset.filter(name__icontains="冰箱"))
    print(f"未能唯一定位设备：{device_name}")
    if fridge_like:
        print("当前本地快照中的冰箱设备：")
        for device in fridge_like:
            print(f"  - {device.name} [{device.external_id}]")
    else:
        print("当前本地快照中未发现 HA 冰箱设备。")
    raise SystemExit(3)


def find_temperature_control(device: DeviceSnapshot, group_label: str) -> DeviceControl:
    queryset = DeviceControl.objects.filter(
        account=device.account,
        device=device,
        source_type=DeviceControl.SourceTypeChoices.HA_ENTITY,
        writable=True,
        kind=DeviceControl.KindChoices.RANGE,
    ).order_by("sort_order", "id")

    candidates = list(queryset.filter(group_label=group_label))
    if len(candidates) == 1:
        return candidates[0]

    fallback = [
        control for control in queryset
        if "温度" in str(control.label) or "temp" in str(control.key).lower()
    ]
    if len(fallback) == 1:
        return fallback[0]

    print(f"未能唯一定位控件，目标分组：{group_label}")
    print("当前设备本地快照中的可写控件：")
    for control in queryset:
        print(
            f"  - {control.label} "
            f"[id={control.external_id}, kind={control.kind}, group={control.group_label}, value={control.value}]"
        )
    raise SystemExit(4)


def main() -> int:
    args = parse_args()
    account = pick_account(args.email)
    auth = HomeAssistantAuthService.get_auth_record(account=account, active_only=True)
    payload = HomeAssistantAuthService._extract_payload(auth)
    base_url = payload.get("base_url", "")

    print(f"账户: {account.email}")
    print(f"HA 地址: {base_url}")
    print("Step 1: 直接读取本地已有 HA 快照数据...")
    device = find_device(account, args.device_name)
    control = find_temperature_control(device, args.group_label)
    before_value = control.value

    print(f"Step 2: 目标设备: {device.name} [{device.external_id}]")
    print(
        "Step 3: 目标控件: "
        f"{control.label} [{control.external_id}] "
        f"当前值={before_value}{control.unit or ''} "
        f"目标值={args.target}{control.unit or ''}"
    )
    print("  action_params:", control.action_params)

    print("Step 4: 直接下发温度控制，不触发 refresh ...")
    DeviceDashboardService._execute_home_assistant_control(
        account,
        control=control,
        action="",
        value=args.target,
    )
    print("\nPASS: 控制请求已发送到真实 HA。")
    print("说明：该脚本不会 refresh，本地快照值不会被自动更新。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
