from __future__ import annotations

from copy import deepcopy


def normalize_keyword(value: str | None) -> str:
    return "".join(str(value or "").strip().lower().split())


SYSTEM_KEYWORDS: list[dict] = [
    {"keyword": "客厅", "category": "room", "canonical": "客厅"},
    {"keyword": "卧室", "category": "room", "canonical": "卧室"},
    {"keyword": "主卧", "category": "room", "canonical": "主卧"},
    {"keyword": "厨房", "category": "room", "canonical": "厨房"},
    {"keyword": "卫生间", "category": "room", "canonical": "卫生间"},
    {"keyword": "浴室", "category": "room", "canonical": "浴室"},
    {"keyword": "书房", "category": "room", "canonical": "书房"},
    {"keyword": "阳台", "category": "room", "canonical": "阳台"},
    {"keyword": "玄关", "category": "room", "canonical": "玄关"},
    {"keyword": "餐厅", "category": "room", "canonical": "餐厅"},
    {"keyword": "living room", "category": "room", "canonical": "客厅"},
    {"keyword": "bedroom", "category": "room", "canonical": "卧室"},
    {"keyword": "master bedroom", "category": "room", "canonical": "主卧"},
    {"keyword": "kitchen", "category": "room", "canonical": "厨房"},
    {"keyword": "bathroom", "category": "room", "canonical": "卫生间"},
    {"keyword": "study", "category": "room", "canonical": "书房"},
    {"keyword": "灯", "category": "device", "canonical": "灯"},
    {"keyword": "主灯", "category": "device", "canonical": "主灯"},
    {"keyword": "空调", "category": "device", "canonical": "空调"},
    {"keyword": "风扇", "category": "device", "canonical": "风扇"},
    {"keyword": "窗帘", "category": "device", "canonical": "窗帘"},
    {"keyword": "扫地机", "category": "device", "canonical": "扫地机"},
    {"keyword": "扫地机器人", "category": "device", "canonical": "扫地机"},
    {"keyword": "电视", "category": "device", "canonical": "电视"},
    {"keyword": "加湿器", "category": "device", "canonical": "加湿器"},
    {"keyword": "冰箱", "category": "device", "canonical": "冰箱"},
    {"keyword": "洗衣机", "category": "device", "canonical": "洗衣机"},
    {"keyword": "奔驰", "category": "device", "canonical": "奔驰"},
    {"keyword": "车辆", "category": "device", "canonical": "车辆"},
    {"keyword": "汽车", "category": "device", "canonical": "汽车"},
    {"keyword": "车", "category": "device", "canonical": "车"},
    {"keyword": "light", "category": "device", "canonical": "灯"},
    {"keyword": "lights", "category": "device", "canonical": "灯"},
    {"keyword": "ac", "category": "device", "canonical": "空调"},
    {"keyword": "air conditioner", "category": "device", "canonical": "空调"},
    {"keyword": "fan", "category": "device", "canonical": "风扇"},
    {"keyword": "curtain", "category": "device", "canonical": "窗帘"},
    {"keyword": "vacuum", "category": "device", "canonical": "扫地机"},
    {"keyword": "tv", "category": "device", "canonical": "电视"},
    {"keyword": "fridge", "category": "device", "canonical": "冰箱"},
    {"keyword": "refrigerator", "category": "device", "canonical": "冰箱"},
    {"keyword": "car", "category": "device", "canonical": "车"},
    {"keyword": "油量", "category": "control", "canonical": "tanklevelpercent"},
    {"keyword": "剩余油量", "category": "control", "canonical": "tanklevelpercent"},
    {"keyword": "汽油", "category": "control", "canonical": "tanklevelpercent"},
    {"keyword": "续航", "category": "control", "canonical": "rangeelectric"},
    {"keyword": "车锁", "category": "control", "canonical": "doorlockstatusvehicle"},
    {"keyword": "亮度", "category": "control", "canonical": "brightness"},
    {"keyword": "温度", "category": "control", "canonical": "temperature"},
    {"keyword": "多少度", "category": "control", "canonical": "temperature"},
    {"keyword": "风速", "category": "control", "canonical": "fan_mode"},
    {"keyword": "模式", "category": "control", "canonical": "mode"},
    {"keyword": "电源", "category": "control", "canonical": "power"},
    {"keyword": "开关", "category": "control", "canonical": "power"},
    {"keyword": "fuel", "category": "control", "canonical": "tanklevelpercent"},
    {"keyword": "range", "category": "control", "canonical": "rangeelectric"},
    {"keyword": "lock", "category": "control", "canonical": "doorlockstatusvehicle"},
    {"keyword": "turn on", "category": "action", "canonical": "打开", "canonical_payload": {"control_key": "power", "action": "set_property", "value": True, "unit": None}},
    {"keyword": "turn off", "category": "action", "canonical": "关闭", "canonical_payload": {"control_key": "power", "action": "set_property", "value": False, "unit": None}},
    {"keyword": "打开", "category": "action", "canonical": "打开", "canonical_payload": {"control_key": "power", "action": "set_property", "value": True, "unit": None}},
    {"keyword": "开启", "category": "action", "canonical": "打开", "canonical_payload": {"control_key": "power", "action": "set_property", "value": True, "unit": None}},
    {"keyword": "关闭", "category": "action", "canonical": "关闭", "canonical_payload": {"control_key": "power", "action": "set_property", "value": False, "unit": None}},
    {"keyword": "关掉", "category": "action", "canonical": "关闭", "canonical_payload": {"control_key": "power", "action": "set_property", "value": False, "unit": None}},
    {"keyword": "亮一点", "category": "action", "canonical": "调亮", "canonical_payload": {"control_key": "brightness", "action": "set_property", "value": "+10%", "unit": None}},
    {"keyword": "暗一点", "category": "action", "canonical": "调暗", "canonical_payload": {"control_key": "brightness", "action": "set_property", "value": "-10%", "unit": None}},
    {"keyword": "热一点", "category": "action", "canonical": "调高温度", "canonical_payload": {"control_key": "temperature", "action": "set_property", "value": "+1", "unit": None}},
    {"keyword": "冷一点", "category": "action", "canonical": "调低温度", "canonical_payload": {"control_key": "temperature", "action": "set_property", "value": "-1", "unit": None}},
    {"keyword": "warmer", "category": "action", "canonical": "调高温度", "canonical_payload": {"control_key": "temperature", "action": "set_property", "value": "+1", "unit": None}},
    {"keyword": "cooler", "category": "action", "canonical": "调低温度", "canonical_payload": {"control_key": "temperature", "action": "set_property", "value": "-1", "unit": None}},
    {"keyword": "brighter", "category": "action", "canonical": "调亮", "canonical_payload": {"control_key": "brightness", "action": "set_property", "value": "+10%", "unit": None}},
    {"keyword": "dimmer", "category": "action", "canonical": "调暗", "canonical_payload": {"control_key": "brightness", "action": "set_property", "value": "-10%", "unit": None}},
    {"keyword": "can you", "category": "colloquial", "canonical": "can you"},
    {"keyword": "please", "category": "colloquial", "canonical": "please"},
    {"keyword": "a bit", "category": "colloquial", "canonical": "a bit"},
    {"keyword": "kind of", "category": "colloquial", "canonical": "kind of"},
    {"keyword": "那个", "category": "colloquial", "canonical": "那个"},
    {"keyword": "这个", "category": "colloquial", "canonical": "这个"},
    {"keyword": "弄", "category": "colloquial", "canonical": "弄"},
    {"keyword": "搞", "category": "colloquial", "canonical": "搞"},
    {"keyword": "有点", "category": "colloquial", "canonical": "有点"},
    {"keyword": "帮我", "category": "colloquial", "canonical": "帮我"},
    {"keyword": "太热", "category": "colloquial", "canonical": "太热"},
    {"keyword": "太冷", "category": "colloquial", "canonical": "太冷"},
    {"keyword": "太亮", "category": "colloquial", "canonical": "太亮"},
    {"keyword": "太暗", "category": "colloquial", "canonical": "太暗"},
]


def empty_keyword_cache() -> dict:
    return {
        "devices": set(),
        "rooms": set(),
        "controls": set(),
        "actions": set(),
        "colloquial": set(),
        "mapping": {},
        "payloads": {},
    }


def build_keyword_cache(entries: list[dict]) -> dict:
    cache = empty_keyword_cache()
    category_map = {
        "device": "devices",
        "room": "rooms",
        "control": "controls",
        "action": "actions",
        "colloquial": "colloquial",
    }
    for entry in entries:
        keyword = normalize_keyword(entry.get("keyword"))
        if not keyword:
            continue
        bucket = category_map.get(entry.get("category"))
        if bucket:
            cache[bucket].add(keyword)
        canonical = str(entry.get("canonical") or "").strip()
        if canonical:
            cache["mapping"][keyword] = canonical
        payload = deepcopy(entry.get("canonical_payload") or {})
        if payload:
            cache["payloads"][keyword] = payload
    return cache


def get_initial_keyword_cache() -> dict:
    return build_keyword_cache(SYSTEM_KEYWORDS)


def iter_system_keyword_records() -> list[dict]:
    records: list[dict] = []
    for entry in SYSTEM_KEYWORDS:
        keyword = str(entry.get("keyword") or "").strip()
        normalized = normalize_keyword(keyword)
        if not keyword or not normalized:
            continue
        records.append(
            {
                "keyword": keyword,
                "normalized_keyword": normalized,
                "canonical": str(entry.get("canonical") or "").strip(),
                "canonical_payload": deepcopy(entry.get("canonical_payload") or {}),
                "category": str(entry.get("category") or "").strip(),
            }
        )
    return records
