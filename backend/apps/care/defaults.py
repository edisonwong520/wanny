from care.models import InspectionRule


DEFAULT_SYSTEM_RULES = [
    {
        "system_key": "water_filter_low_life",
        "rule_type": InspectionRule.RuleTypeChoices.MAINTENANCE,
        "device_category": "water_purifier",
        "name": "滤芯寿命过低提醒",
        "description": "当净水设备的滤芯寿命较低时，提前提醒主人安排更换或检查。",
        "check_frequency": "hourly",
        "condition_spec": {"field": "control.filter_life_percent", "operator": "<", "threshold": 20},
        "suggestion_template": "{device_name} 的 {control_label} 仅剩 {current_value}，建议尽快处理。",
        "priority": 8,
        "cooldown_hours": 24,
        "action_spec": {},
    },
    {
        "system_key": "device_offline_too_long",
        "rule_type": InspectionRule.RuleTypeChoices.HEALTH,
        "device_category": "",
        "name": "设备离线过久提醒",
        "description": "当设备长时间没有心跳时，提示主人检查网络、供电或设备状态。",
        "check_frequency": "hourly",
        "condition_spec": {"field": "device_offline_hours", "operator": ">", "threshold": 24},
        "suggestion_template": "{device_name} 已离线较久，建议检查设备在线状态。",
        "priority": 6,
        "cooldown_hours": 12,
        "action_spec": {},
    },
    {
        "system_key": "pet_fountain_low_water",
        "rule_type": InspectionRule.RuleTypeChoices.HEALTH,
        "device_category": "宠物",
        "name": "宠物饮水机低水位提醒",
        "description": "宠物照护类设备应优先关注低水位和长时间异常状态。",
        "check_frequency": "hourly",
        "condition_spec": {"field": "control.water_level_percent", "operator": "<", "threshold": 20},
        "suggestion_template": "{device_name} 水位仅剩 {current_value}，建议尽快补水。",
        "priority": 9,
        "cooldown_hours": 6,
        "action_spec": {},
    },
]


def seed_system_rules() -> int:
    created_or_updated = 0
    for item in DEFAULT_SYSTEM_RULES:
        _, _created = InspectionRule.objects.update_or_create(
            account=None,
            system_key=item["system_key"],
            defaults={
                **item,
                "is_system_default": True,
                "is_active": True,
            },
        )
        created_or_updated += 1
    return created_or_updated

