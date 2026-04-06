"""
真实联调海信账号，列出家庭和设备。

运行方式：
    cd backend
    uv run python tests/scripts/test_hisense_devices.py

也支持环境变量：
    HISENSE_USERNAME=188xxxxxxxx HISENSE_PASSWORD=xxxx uv run python tests/scripts/test_hisense_devices.py
"""

from __future__ import annotations

import os
import sys
from getpass import getpass
from pathlib import Path
from pprint import pprint


BACKEND_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BACKEND_DIR / "apps"))

from providers.clients.hisense_ha.client import HisenseHAClient


def prompt_credentials() -> tuple[str, str]:
    username = os.environ.get("HISENSE_USERNAME", "").strip()
    password = os.environ.get("HISENSE_PASSWORD", "").strip()

    if not username:
        username = input("Hisense username: ").strip()
    if not password:
        password = getpass("Hisense password: ")

    if not username or not password:
        raise ValueError("Hisense username/password is required")
    return username, password


def main() -> int:
    username, password = prompt_credentials()

    print("Step 1: 登录海信云...")
    client = HisenseHAClient({"username": username, "password": password})
    auth_state = client._login()
    print("  登录成功")
    print("  access_token:", f"{auth_state['access_token'][:8]}...")
    print("  refresh_token:", f"{auth_state['refresh_token'][:8]}...")

    print("\nStep 2: 获取家庭列表...")
    homes = client.list_homes(access_token=auth_state["access_token"])
    if not homes:
        print("  未获取到任何家庭。")
        return 1

    for index, home in enumerate(homes, start=1):
        print(f"  HOME#{index}: id={home['home_id']} name={home['home_name']}")

    print("\nStep 3: 逐个家庭拉取原始设备列表和空调设备列表...")
    for home in homes:
        print(f"\n  家庭: {home['home_name']} ({home['home_id']})")
        raw_payload = client._request_json(
            "GET",
            f"{client.api_base}/wg/dm/getHomeDeviceList",
            params={
                "sign": "",
                "languageId": "0",
                "version": "8.0",
                "accessToken": auth_state["access_token"],
                "homeId": home["home_id"],
                "timezone": "28800",
                "format": "1",
                "timeStamp": str(client._timestamp_ms()),
            },
            headers=client._api_headers(),
        )
        response = raw_payload.get("response") if isinstance(raw_payload.get("response"), dict) else {}
        raw_devices = response.get("deviceList") if isinstance(response.get("deviceList"), list) else []
        print(f"    原始 deviceList 数量: {len(raw_devices)}")
        if raw_devices:
            for idx, item in enumerate(raw_devices, start=1):
                print(f"    RAW#{idx}:")
                pprint(
                    {
                        "deviceId": item.get("deviceId"),
                        "deviceName": item.get("deviceName"),
                        "deviceNickName": item.get("deviceNickName"),
                        "deviceTypeName": item.get("deviceTypeName"),
                        "roomName": item.get("roomName"),
                        "wifiId": item.get("wifiId"),
                    },
                    sort_dicts=False,
                    width=120,
                )
        else:
            print("    原始 deviceList 为空")

        ac_devices = client.list_home_devices(access_token=auth_state["access_token"], home_id=home["home_id"])
        print(f"    筛选出的空调数量: {len(ac_devices)}")
        if ac_devices:
            for idx, item in enumerate(ac_devices, start=1):
                print(f"    AC#{idx}:")
                pprint(item, sort_dicts=False, width=120)
        else:
            print("    未筛选出任何空调设备")

    print("\nPASS: 海信家庭与设备列表拉取完成。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
