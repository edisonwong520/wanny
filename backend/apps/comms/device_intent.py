from __future__ import annotations

import re
from typing import Any

from asgiref.sync import sync_to_async

from comms.ai import AIAgent
from devices.models import DeviceSnapshot


WAKEUP_PATTERNS = [
    r"^\s*jarvis[\s,:，：]+",
    r"^\s*贾维斯[\s,:，：]+",
]

DEVICE_HINT_PATTERNS = [
    r"开",
    r"关",
    r"调",
    r"亮",
    r"暗",
    r"温度",
    r"亮度",
    r"空调",
    r"灯",
    r"风扇",
    r"扫地",
    r"窗帘",
    r"模式",
    r"状态",
    r"多少度",
]

ROOM_HINTS = ["客厅", "卧室", "厨房", "书房", "卫生间", "浴室", "阳台", "玄关", "餐厅"]
DEVICE_HINTS = ["空调", "主灯", "灯", "风扇", "窗帘", "扫地机", "扫地机器人", "加湿器", "电视", "冰箱", "洗衣机"]

CONTROL_HINT_ALIASES = {
    "亮度": "brightness",
    "亮一点": "brightness",
    "暗一点": "brightness",
    "温度": "temperature",
    "多少度": "temperature",
    "风速": "fan_mode",
    "模式": "mode",
    "电源": "power",
    "开关": "power",
}


def detect_command_mode(content: str) -> str:
    normalized = (content or "").strip()
    if any(re.match(pattern, normalized, flags=re.IGNORECASE) for pattern in WAKEUP_PATTERNS):
        return "command"
    return "default"


def strip_wakeup_prefix(content: str) -> str:
    normalized = content or ""
    for pattern in WAKEUP_PATTERNS:
        next_value = re.sub(pattern, "", normalized, count=1, flags=re.IGNORECASE)
        if next_value != normalized:
            return next_value.strip()
    return normalized.strip()


def should_check_device_intent(content: str) -> bool:
    normalized = (content or "").strip().lower()
    return any(re.search(pattern, normalized, flags=re.IGNORECASE) for pattern in DEVICE_HINT_PATTERNS)


async def _build_device_prompt_context(account) -> tuple[str, str]:
    devices = await sync_to_async(list)(
        DeviceSnapshot.objects.filter(account=account)
        .select_related("room")
        .prefetch_related("controls")
        .order_by("room__sort_order", "sort_order", "id")
    )
    if not devices:
        return "无设备", "无控制能力"

    device_lines: list[str] = []
    capability_lines: list[str] = []
    for device in devices:
        room_name = device.room.name if device.room else "未分组"
        status_label = device.get_status_display()
        device_lines.append(
            f'- room="{room_name}" device_name="{device.name}" device_external_id="{device.external_id}" status="{status_label}"'
        )
        for control in device.controls.all():
            capability_lines.append(
                (
                    f'- device_external_id="{device.external_id}" control_external_id="{control.external_id}" '
                    f'key="{control.key}" label="{control.label}" kind="{control.kind}" writable={str(control.writable).lower()} '
                    f'unit="{control.unit}" options={control.options} range_spec={control.range_spec}'
                )
            )
    return "\n".join(device_lines), "\n".join(capability_lines)


async def analyze_device_intent(
    user_msg: str,
    account,
    memory_context: str = "",
    command_mode: bool = False,
) -> dict:
    normalized_msg = (user_msg or "").strip()
    if not normalized_msg:
        return {
            "type": "UNSUPPORTED_COMMAND" if command_mode else "CHAT",
            "response": "我没有收到有效的设备指令。",
            "reason": "empty_message",
        }

    if account is None:
        return {
            "type": "UNSUPPORTED_COMMAND" if command_mode else "CHAT",
            "response": "当前账号还没有可用的设备上下文，暂时无法处理设备命令。",
            "reason": "missing_account",
        }

    heuristic_result = _heuristic_parse_device_intent(normalized_msg, command_mode=command_mode)
    if heuristic_result:
        return heuristic_result

    device_list, control_capabilities = await _build_device_prompt_context(account)
    system_prompt = """
你是 Wanny 的设备控制解析引擎。请把用户消息解析为严格 JSON。

允许的 type:
- DEVICE_CONTROL
- DEVICE_QUERY
- CHAT
- UNSUPPORTED_COMMAND

返回字段要求：
- DEVICE_CONTROL: type, action, room, device, control_key, value, unit, confidence, ambiguous, alternatives, suggested_reply, error_hint
- DEVICE_QUERY: type, room, device, control_key, suggested_reply
- CHAT: type, response
- UNSUPPORTED_COMMAND: type, response, reason

规则：
1. 只有设备操作、设备状态查询，才返回 DEVICE_CONTROL 或 DEVICE_QUERY。
2. command_mode=true 时，绝不能返回 CHAT；无法映射为设备命令时必须返回 UNSUPPORTED_COMMAND。
3. 房间、设备、control_key 允许缺失，但不要臆造不存在的设备。
4. 如果用户在做连续调节类操作（如亮一点、调高一点），尽量输出对应 control_key。
5. 只返回 JSON，不要 Markdown。
""".strip()

    user_prompt = (
        f"command_mode={str(command_mode).lower()}\n"
        f"device_list:\n{device_list}\n\n"
        f"control_capabilities:\n{control_capabilities}\n\n"
        f"memory_context:\n{memory_context or '无'}\n\n"
        f"user_msg:\n{normalized_msg}"
    )
    agent = AIAgent()
    result = await agent.generate_json(system_prompt, user_prompt)
    intent_type = result.get("type")
    if command_mode and intent_type == "CHAT":
        return {
            "type": "UNSUPPORTED_COMMAND",
            "response": "这是命令模式，但我还没理解您希望我执行什么操作。",
            "reason": "chat_not_allowed_in_command_mode",
        }
    if not intent_type:
        return {
            "type": "UNSUPPORTED_COMMAND" if command_mode else "CHAT",
            "response": "我暂时没能理解这条消息。",
            "reason": "missing_type",
        }
    return result


def _heuristic_parse_device_intent(user_msg: str, *, command_mode: bool) -> dict[str, Any] | None:
    normalized = user_msg.strip()
    if not normalized:
        return None

    room = next((item for item in ROOM_HINTS if item in normalized), "")
    device = next((item for item in sorted(DEVICE_HINTS, key=len, reverse=True) if item in normalized), "")
    control_key = ""
    for alias, canonical in CONTROL_HINT_ALIASES.items():
        if alias in normalized:
            control_key = canonical
            break

    is_query = any(token in normalized for token in ("查询", "看看", "看下", "多少", "状态", "几度"))
    if device or room:
        if is_query:
            return {
                "type": "DEVICE_QUERY",
                "room": room,
                "device": device,
                "control_key": control_key or ("temperature" if "温" in normalized or "度" in normalized else "power"),
                "suggested_reply": "",
            }

        lowered = normalized.lower()
        value: Any = None
        action = "set_property"
        if any(token in normalized for token in ("关", "关闭", "关掉", "熄灭")):
            value = False
            control_key = control_key or "power"
        elif any(token in normalized for token in ("开", "打开", "开启")):
            value = True
            control_key = control_key or "power"

        temp_match = re.search(r"(\d{1,2})\s*度", normalized)
        if temp_match:
            value = int(temp_match.group(1))
            control_key = "temperature"
        elif any(token in normalized for token in ("调高一点", "升高一点", "热一点")):
            value = "+1"
            control_key = "temperature"
        elif any(token in normalized for token in ("调低一点", "降低一点", "冷一点")):
            value = "-1"
            control_key = "temperature"
        elif any(token in normalized for token in ("亮一点", "调亮")):
            value = "+10%"
            control_key = "brightness"
        elif any(token in normalized for token in ("暗一点", "调暗")):
            value = "-10%"
            control_key = "brightness"

        if any(token in normalized for token in ("模式", "制冷", "制热", "除湿", "睡眠模式")):
            action = "set_property"
            control_key = control_key or "mode"
            for mode_name in ("制冷", "制热", "除湿", "睡眠"):
                if mode_name in normalized:
                    value = mode_name
                    break

        if control_key:
            return {
                "type": "DEVICE_CONTROL",
                "action": action,
                "room": room,
                "device": device,
                "control_key": control_key,
                "value": value,
                "unit": "°C" if control_key == "temperature" and isinstance(value, int) else None,
                "confidence": 0.82,
                "ambiguous": not bool(device),
                "alternatives": [],
                "suggested_reply": "",
                "error_hint": None,
            }

    if command_mode:
        return {
            "type": "UNSUPPORTED_COMMAND",
            "response": "这是命令模式，但我还没理解您希望我执行什么操作。",
            "reason": "heuristic_unmatched",
        }
    return None
