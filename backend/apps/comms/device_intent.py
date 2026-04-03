from __future__ import annotations

import re
from typing import Any

from asgiref.sync import sync_to_async

from comms.ai import AIAgent
from comms.initial_keywords import normalize_keyword
from comms.keyword_loader import KeywordLoader
from devices.models import DeviceSnapshot
from utils.telemetry import get_tracer


tracer = get_tracer(__name__)


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
    r"奔驰",
    r"车辆",
    r"汽车",
    r"油量",
    r"续航",
    r"车锁",
]

ROOM_HINTS = ["客厅", "卧室", "厨房", "书房", "卫生间", "浴室", "阳台", "玄关", "餐厅"]
DEVICE_HINTS = ["奔驰", "车辆", "汽车", "车", "空调", "主灯", "灯", "风扇", "窗帘", "扫地机", "扫地机器人", "加湿器", "电视", "冰箱", "洗衣机"]

CONTROL_HINT_ALIASES = {
    "亮度": "brightness",
    "亮一点": "brightness",
    "暗一点": "brightness",
    "温度": "temperature",
    "多少度": "temperature",
    "油量": "tanklevelpercent",
    "剩余油量": "tanklevelpercent",
    "汽油": "tanklevelpercent",
    "续航": "rangeelectric",
    "车锁": "doorlockstatusvehicle",
    "风速": "fan_mode",
    "模式": "mode",
    "电源": "power",
    "开关": "power",
}

AI_CONTROL_KEY_NORMALIZERS = {
    "target_temperature": "temperature",
    "targettemperature": "temperature",
    "temperature": "temperature",
    "brightness": "brightness",
    "power": "power",
    "tanklevelpercent": "tanklevelpercent",
    "rangeelectric": "rangeelectric",
    "doorlockstatusvehicle": "doorlockstatusvehicle",
    "fanmode": "fan_mode",
    "fan_mode": "fan_mode",
    "mode": "mode",
}

QUERY_PHRASES = (
    "查询",
    "看看",
    "看下",
    "多少",
    "状态",
    "几度",
    "是不是",
    "是否",
    "有没有",
    "开着吗",
    "关着吗",
    "亮着吗",
    "暗着吗",
    "还开着吗",
    "还亮着吗",
    "还关着吗",
    "开着没",
    "关着没",
    "亮着没",
    "锁上了吗",
    "锁了吗",
    "锁着吗",
    "锁着没有",
    "锁着没",
    "开没开",
    "亮没亮",
    "关没关",
    "有没有开",
    "有没有关",
    "是不是亮着",
    "是不是开着",
    "是不是关着",
)

QUERY_NORMALIZED_TOKENS = (
    "check",
    "query",
    "status",
    "howmuch",
    "howmany",
    "whether",
    "isiton",
    "isitoff",
    "stillon",
    "stilloff",
    "isitstillon",
    "isitlocked",
    "locked",
    "whatsthetemperature",
)

ENGLISH_QUERY_PATTERNS = (
    r"\bis\s+the\b",
    r"\bis\s+it\b",
    r"\bare\s+the\b",
    r"\bare\s+there\b",
    r"\bwhat(?:'s|\s+is)\b",
    r"\bhow\s+(?:hot|cold|bright|dim)\b",
    r"\bhow\s+much\b",
    r"\bhow\s+many\b",
)


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


def should_check_device_intent(content: str, *, keyword_cache: dict[str, Any] | None = None) -> bool:
    normalized = normalize_keyword(content)
    if any(re.search(pattern, normalized, flags=re.IGNORECASE) for pattern in DEVICE_HINT_PATTERNS):
        return True
    base_cache = keyword_cache or KeywordLoader.base_cache()
    for token in (
        *base_cache["devices"],
        *base_cache["rooms"],
        *base_cache["controls"],
        *base_cache["actions"],
    ):
        if token and token in normalized:
            return True
    return False


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
    allow_normalize: bool = False,
) -> dict:
    with tracer.start_as_current_span("device.analyze_intent") as span:
        span.set_attribute("device.command_mode", command_mode)
        span.set_attribute("device.normalizer.allowed", allow_normalize)
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

        keyword_cache = await KeywordLoader.get_keywords_for_account(getattr(account, "id", None))
        heuristic_result = _heuristic_parse_device_intent(
            normalized_msg,
            command_mode=command_mode,
            keyword_cache=keyword_cache,
        )
        if heuristic_result:
            span.set_attribute("device.heuristic.hit", True)
            span.set_attribute("device.normalizer.invoked", False)
            span.set_attribute("device.ai_fallback", False)
            span.set_attribute("device.intent_type", str(heuristic_result.get("type") or ""))
            return heuristic_result
        span.set_attribute("device.heuristic.hit", False)

        if allow_normalize:
            from comms.normalizer import CommandNormalizer

            span.set_attribute("device.normalizer.invoked", True)
            normalized_candidate = await CommandNormalizer.normalize(normalized_msg)
            if normalize_keyword(normalized_candidate) != normalize_keyword(normalized_msg):
                span.set_attribute("device.normalizer.changed", True)
                heuristic_result = _heuristic_parse_device_intent(
                    normalized_candidate,
                    command_mode=command_mode,
                    keyword_cache=keyword_cache,
                )
                if heuristic_result:
                    span.set_attribute("device.heuristic.hit_after_normalize", True)
                    span.set_attribute("device.ai_fallback", False)
                    span.set_attribute("device.intent_type", str(heuristic_result.get("type") or ""))
                    span.set_attribute("device.normalized", True)
                    return heuristic_result
                normalized_msg = normalized_candidate
            else:
                span.set_attribute("device.normalizer.changed", False)
        else:
            span.set_attribute("device.normalizer.invoked", False)

        device_list, control_capabilities = await _build_device_prompt_context(account)
        span.set_attribute("device.ai_fallback", True)
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
        result = _postprocess_ai_result(result, user_msg=normalized_msg)
        intent_type = result.get("type")
        if intent_type == "simple":
            if command_mode:
                span.set_attribute("device.intent_type", "UNSUPPORTED_COMMAND")
                return {
                    "type": "UNSUPPORTED_COMMAND",
                    "response": "这是命令模式，但我还没理解您希望我执行什么操作。",
                    "reason": "device_intent_invalid_json",
                }
            span.set_attribute("device.intent_type", "CHAT")
            return {
                "type": "CHAT",
                "response": "我刚才没有理解清楚，您可以换种说法再发一次。",
            }
        if command_mode and intent_type == "CHAT":
            span.set_attribute("device.intent_type", "UNSUPPORTED_COMMAND")
            return {
                "type": "UNSUPPORTED_COMMAND",
                "response": "这是命令模式，但我还没理解您希望我执行什么操作。",
                "reason": "chat_not_allowed_in_command_mode",
            }
        if not intent_type:
            span.set_attribute("device.intent_type", "UNKNOWN")
            return {
                "type": "UNSUPPORTED_COMMAND" if command_mode else "CHAT",
                "response": "我暂时没能理解这条消息。",
                "reason": "missing_type",
            }
        span.set_attribute("device.intent_type", str(intent_type))
        return result


def _normalize_ai_control_key(control_key: str | None) -> str:
    normalized = normalize_keyword(control_key)
    if not normalized:
        return ""
    for pattern, canonical in AI_CONTROL_KEY_NORMALIZERS.items():
        if pattern in normalized:
            return canonical
    for alias, canonical in CONTROL_HINT_ALIASES.items():
        if normalize_keyword(alias) in normalized:
            return canonical
    return str(control_key or "").strip()


def _infer_control_key_from_user_msg(user_msg: str, current_control_key: str) -> str:
    normalized = normalize_keyword(user_msg)
    normalized_control = normalize_keyword(current_control_key)
    if any(token in normalized for token in ("油量", "剩余油量", "汽油", "fuel", "多少油", "剩多少油", "还剩多少油", "油")):
        return "tanklevelpercent"
    if any(token in normalized for token in ("续航", "range")):
        return "rangeelectric"
    if any(token in normalized for token in ("车锁", "锁车", "锁上", "锁了吗", "锁着", "锁没锁", "locked", "doorlock")):
        return "doorlockstatusvehicle"
    if any(
        token in normalized
        for token in ("温度", "几度", "多热", "多冷", "temperature", "hot", "cold")
    ):
        return "temperature"
    if any(token in normalized for token in ("亮着", "亮没亮")):
        return "brightness" if normalized_control == "brightness" else "power"
    return current_control_key if normalized_control else ""


def _postprocess_ai_result(result: dict, *, user_msg: str) -> dict:
    if not isinstance(result, dict):
        return result
    intent_type = str(result.get("type") or "")
    if intent_type not in {"DEVICE_CONTROL", "DEVICE_QUERY"}:
        return result

    normalized = dict(result)
    control_key = _normalize_ai_control_key(result.get("control_key"))
    if intent_type == "DEVICE_QUERY":
        control_key = _infer_control_key_from_user_msg(user_msg, control_key)
    normalized["control_key"] = control_key or result.get("control_key") or ""
    return normalized


def _is_question_like(user_msg: str, normalized_text: str) -> bool:
    raw_text = str(user_msg or "").strip()
    if not raw_text:
        return False
    if any(token in raw_text for token in QUERY_PHRASES):
        return True
    if any(token in normalized_text for token in QUERY_NORMALIZED_TOKENS):
        return True
    lowered = raw_text.lower()
    if any(re.search(pattern, lowered) for pattern in ENGLISH_QUERY_PATTERNS):
        return True
    if raw_text.endswith(("吗", "么", "? ", "？")) or raw_text.endswith(("?", "？")):
        return True
    if "是不是" in raw_text or "是否" in raw_text or "有没有" in raw_text:
        return True
    return False


def _merge_payload(target: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    merged = dict(target)
    for key in ("room", "device", "control_key", "action", "value", "unit"):
        value = payload.get(key)
        if value not in (None, "") and merged.get(key) in (None, "", []):
            merged[key] = value
    return merged


def _pick_longest_match(tokens: set[str], normalized_text: str) -> str:
    for token in sorted(tokens, key=len, reverse=True):
        if token and token in normalized_text:
            return token
    return ""


def _heuristic_parse_device_intent(
    user_msg: str,
    *,
    command_mode: bool,
    keyword_cache: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    normalized = user_msg.strip()
    if not normalized:
        return None

    cache = keyword_cache or KeywordLoader.base_cache()
    normalized_text = normalize_keyword(normalized)
    room_keyword = _pick_longest_match(set(cache.get("rooms", set())), normalized_text)
    device_keyword = _pick_longest_match(set(cache.get("devices", set())), normalized_text)
    control_keyword = _pick_longest_match(set(cache.get("controls", set())), normalized_text)
    action_keyword = _pick_longest_match(set(cache.get("actions", set())), normalized_text)

    intent_hints: dict[str, Any] = {
        "room": cache.get("mapping", {}).get(room_keyword, ""),
        "device": cache.get("mapping", {}).get(device_keyword, ""),
        "control_key": cache.get("mapping", {}).get(control_keyword, ""),
        "action": "",
        "value": None,
        "unit": None,
    }
    for keyword in (room_keyword, device_keyword, control_keyword, action_keyword):
        if keyword:
            intent_hints = _merge_payload(intent_hints, cache.get("payloads", {}).get(keyword, {}))

    room = intent_hints.get("room") or next((item for item in ROOM_HINTS if item in normalized), "")
    device = intent_hints.get("device") or next((item for item in sorted(DEVICE_HINTS, key=len, reverse=True) if item in normalized), "")
    control_key = intent_hints.get("control_key") or ""
    for alias, canonical in CONTROL_HINT_ALIASES.items():
        if alias in normalized:
            control_key = canonical
            break

    is_query = _is_question_like(normalized, normalized_text)
    automotive_query_control_keys = {"tanklevelpercent", "rangeelectric", "doorlockstatusvehicle"}
    if device or room or (is_query and control_key in automotive_query_control_keys):
        if is_query:
            inferred_query_control_key = _infer_control_key_from_user_msg(normalized, control_key)
            return {
                "type": "DEVICE_QUERY",
                "room": room,
                "device": device,
                "control_key": inferred_query_control_key
                or ("temperature" if "温" in normalized or "度" in normalized else "power"),
                "payload_hints": intent_hints,
                "suggested_reply": "",
            }

        lowered = normalized.lower()
        value: Any = intent_hints.get("value")
        action = intent_hints.get("action") or "set_property"
        if any(token in normalized for token in ("关", "关闭", "关掉", "熄灭")):
            value = False
            control_key = control_key or "power"
        elif any(token in normalized for token in ("开", "打开", "开启")):
            value = True
            control_key = control_key or "power"
        elif "turnoff" in normalized_text:
            value = False
            control_key = control_key or "power"
        elif "turnon" in normalized_text:
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
                "unit": intent_hints.get("unit") or ("°C" if control_key == "temperature" and isinstance(value, int) else None),
                "payload_hints": intent_hints,
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
