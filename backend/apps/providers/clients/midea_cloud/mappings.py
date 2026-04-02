from __future__ import annotations

import importlib.util
import sys
import types
from functools import lru_cache
from pathlib import Path
from typing import Any


UPSTREAM_MAPPING_ROOT = Path(__file__).resolve().parent / "upstream_device_mapping"


class _Namespace:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __getattr__(self, item: str):
        value = item.lower()
        setattr(self, item, value)
        return value


def _ensure_homeassistant_compat() -> None:
    if "homeassistant.const" in sys.modules:
        return

    homeassistant = types.ModuleType("homeassistant")
    components = types.ModuleType("homeassistant.components")
    const = types.ModuleType("homeassistant.const")
    sensor = types.ModuleType("homeassistant.components.sensor")
    binary_sensor = types.ModuleType("homeassistant.components.binary_sensor")
    switch = types.ModuleType("homeassistant.components.switch")
    humidifier = types.ModuleType("homeassistant.components.humidifier")
    fan = types.ModuleType("homeassistant.components.fan")

    const.Platform = _Namespace(
        BINARY_SENSOR="binary_sensor",
        SENSOR="sensor",
        SWITCH="switch",
        CLIMATE="climate",
        SELECT="select",
        WATER_HEATER="water_heater",
        FAN="fan",
        LIGHT="light",
        HUMIDIFIER="humidifier",
        NUMBER="number",
        BUTTON="button",
        VACUUM="vacuum",
    )
    const.PERCENTAGE = "%"
    const.DEGREE = "°"
    const.PRECISION_HALVES = 0.5
    const.PRECISION_WHOLE = 1
    const.CONCENTRATION_PARTS_PER_MILLION = "ppm"
    const.CONCENTRATION_MICROGRAMS_PER_CUBIC_METER = "ug/m3"
    const.UnitOfTemperature = _Namespace(CELSIUS="°C")
    const.UnitOfTime = _Namespace(HOURS="h", MINUTES="min", SECONDS="s")
    const.UnitOfArea = _Namespace(SQUARE_METERS="m²")
    const.UnitOfPressure = _Namespace(KPA="kPa")
    const.UnitOfElectricPotential = _Namespace(VOLT="V")
    const.UnitOfVolume = _Namespace(LITERS="L")
    const.UnitOfEnergy = _Namespace(KILO_WATT_HOUR="kWh")
    const.UnitOfPower = _Namespace(WATT="W")
    const.UnitOfVolumeFlowRate = _Namespace(CUBIC_METERS_PER_HOUR="m³/h")

    sensor.SensorStateClass = _Namespace(MEASUREMENT="measurement", TOTAL="total", TOTAL_INCREASING="total_increasing")
    sensor.SensorDeviceClass = _Namespace(
        TEMPERATURE="temperature",
        HUMIDITY="humidity",
        ENUM="enum",
        BATTERY="battery",
        AREA="area",
        DURATION="duration",
        WEIGHT="weight",
        DATA_RATE="data_rate",
        POWER="power",
        ENERGY="energy",
        PM25="pm25",
        VOLTAGE="voltage",
    )
    binary_sensor.BinarySensorDeviceClass = _Namespace(
        RUNNING="running",
        BATTERY_CHARGING="battery_charging",
        PROBLEM="problem",
        LIGHT="light",
        DOOR="door",
        PLUG="plug",
        OPENING="opening",
    )
    switch.SwitchDeviceClass = _Namespace(SWITCH="switch")
    humidifier.HumidifierDeviceClass = _Namespace(HUMIDIFIER="humidifier", DEHUMIDIFIER="dehumidifier")
    fan.DIRECTION_FORWARD = "forward"
    fan.DIRECTION_REVERSE = "reverse"

    homeassistant.components = components

    sys.modules["homeassistant"] = homeassistant
    sys.modules["homeassistant.const"] = const
    sys.modules["homeassistant.components"] = components
    sys.modules["homeassistant.components.sensor"] = sensor
    sys.modules["homeassistant.components.binary_sensor"] = binary_sensor
    sys.modules["homeassistant.components.switch"] = switch
    sys.modules["homeassistant.components.humidifier"] = humidifier
    sys.modules["homeassistant.components.fan"] = fan


@lru_cache(maxsize=128)
def _load_upstream_device_mappings(device_type: int) -> dict[str, Any]:
    _ensure_homeassistant_compat()
    file_path = UPSTREAM_MAPPING_ROOT / f"T0x{device_type:02X}.py"
    if not file_path.exists():
        return {}

    module_name = f"wanny_midea_mapping_{device_type:02X}"
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        return {}

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, "DEVICE_MAPPING", {}) or {}


def _select_upstream_mapping(
    device_mappings: dict[str, Any],
    *,
    sn8: str = "",
    subtype: int | None = None,
    category: str | None = None,
) -> dict[str, Any]:
    if not device_mappings:
        return {}

    result = None
    if subtype is not None:
        subtype_str = str(subtype)
        for key, config in device_mappings.items():
            if isinstance(key, tuple) and len(key) == 2 and key[0] == "subtype" and str(key[1]) == subtype_str:
                result = config
                break

    if result is None and sn8:
        for key, config in device_mappings.items():
            if key == sn8 or (isinstance(key, tuple) and sn8 in key):
                result = config
                break

    if result is None and category:
        category_key = f"default_{str(category).replace('-', '_')}"
        result = device_mappings.get(category_key)

    if result is None:
        result = device_mappings.get("default", {})

    return result or {}


def _option_records(options: dict[str, Any]) -> list[dict[str, Any]]:
    records = []
    for option_label, option_payload in (options or {}).items():
        records.append(
            {
                "label": str(option_label),
                "value": option_label,
                "control": option_payload if isinstance(option_payload, dict) else {str(option_label): option_payload},
            }
        )
    return records


def _resolve_attribute_key(entity_key: str, config: dict[str, Any] | None) -> str:
    if isinstance(config, dict) and config.get("attribute"):
        return str(config.get("attribute"))
    return str(entity_key)


def _resolve_label(entity_key: str, config: dict[str, Any] | None) -> str:
    if isinstance(config, dict):
        if config.get("translation_key"):
            return str(config.get("translation_key")).replace("_", " ").title()
        if config.get("name"):
            return str(config.get("name"))
        if config.get("name_attribute"):
            return str(config.get("name_attribute"))
    return str(entity_key).replace("_", " ").title()


def _toggle_actions(control_key: str, rationale: list[Any] | None = None) -> dict[str, dict[str, Any]]:
    values = list(rationale or [])
    off_value = values[0] if len(values) >= 1 else "off"
    on_value = values[1] if len(values) >= 2 else "on"
    return {
        "turn_on": {str(control_key): on_value},
        "turn_off": {str(control_key): off_value},
    }


def _sensor_group_label(device_class: str | None) -> str:
    normalized = str(device_class or "").lower()
    if normalized in {"temperature", "humidity", "pm25", "illuminance"}:
        return "环境"
    if normalized in {"battery", "voltage", "power", "energy"}:
        return "电源"
    if normalized in {"duration", "enum", "opening", "door", "problem", "running"}:
        return "状态"
    if normalized in {"water", "water_heater"}:
        return "水路"
    if normalized in {"wind_direction"}:
        return "送风"
    return "状态"


def _translate_climate_controls(config: dict[str, Any], *, default_rationale: list[Any] | None = None) -> list[dict[str, Any]]:
    controls = []
    power_key = config.get("power")
    if power_key:
        controls.append(
            {
                "key": str(power_key),
                "label": "电源",
                "kind": "toggle",
                "group_label": "整机",
                "writable": True,
                "value_key": str(power_key),
                "actions": _toggle_actions(str(power_key), config.get("rationale") or default_rationale),
            }
        )
    for key, label in (
        ("hvac_modes", "运行模式"),
        ("preset_modes", "预设模式"),
        ("swing_modes", "扫风模式"),
        ("fan_modes", "风速"),
    ):
        if config.get(key):
            control_key = {
                "hvac_modes": "hvac_mode",
                "preset_modes": "preset_mode",
                "swing_modes": "swing_mode",
                "fan_modes": "fan_mode",
            }[key]
            controls.append(
                {
                    "key": control_key,
                    "label": label,
                    "kind": "enum",
                    "group_label": "整机",
                    "writable": True,
                    "value_key": config.get("pre_mode") if key == "hvac_modes" else control_key,
                    "options": _option_records(config[key]),
                }
            )
    target_temperature = config.get("target_temperature")
    if target_temperature:
        value_key = target_temperature[0] if isinstance(target_temperature, list) else str(target_temperature)
        control_record = {
            "key": "target_temperature",
            "label": "目标温度",
            "kind": "range",
            "group_label": "整机",
            "writable": True,
            "value_key": str(value_key),
            "range_spec": {
                "min": config.get("min_temp", 16),
                "max": config.get("max_temp", 30),
                "step": config.get("precision", 1),
            },
            "control_template": {str(value_key): "{value}"},
            "unit": config.get("temperature_unit", "°C"),
        }
        if isinstance(target_temperature, list) and len(target_temperature) >= 2 and config.get("precision") == 0.5:
            control_record["value_transform"] = {
                "type": "temperature_halves",
                "integer_key": str(target_temperature[0]),
                "fraction_key": str(target_temperature[1]),
            }
        controls.append(
            control_record
        )
    current_temperature = config.get("current_temperature")
    if current_temperature:
        controls.append(
            {
                "key": "current_temperature",
                "label": "当前温度",
                "kind": "sensor",
                "group_label": "环境",
                "writable": False,
                "value_key": str(current_temperature),
                "unit": config.get("temperature_unit", "°C"),
            }
        )
    aux_heat = config.get("aux_heat")
    if aux_heat:
        controls.append(
            {
                "key": str(aux_heat),
                "label": "辅热",
                "kind": "toggle",
                "group_label": "整机",
                "writable": True,
                "value_key": str(aux_heat),
                "actions": _toggle_actions(str(aux_heat), config.get("rationale") or default_rationale),
            }
        )
    return controls


def _translate_vacuum_controls(config: dict[str, Any]) -> list[dict[str, Any]]:
    controls = []
    control_key = config.get("control")
    if control_key:
        options = []
        for action_label, action_value in (config.get("control_actions") or {}).items():
            options.append(
                {
                    "label": action_label,
                    "value": action_label,
                    "control": {str(control_key): action_value},
                }
            )
        controls.append(
            {
                "key": str(control_key),
                "label": "工作状态",
                "kind": "enum",
                "group_label": "任务",
                "writable": True,
                "value_key": str(control_key),
                "options": options,
            }
        )
    fan_speeds = config.get("fan_speeds")
    if fan_speeds:
        controls.append(
            {
                "key": "fan_speed",
                "label": "吸力档位",
                "kind": "enum",
                "group_label": "清扫",
                "writable": True,
                "value_key": "fan_level",
                "options": _option_records(fan_speeds),
            }
        )
    battery_key = config.get("battery_level")
    if battery_key:
        controls.append(
            {
                "key": str(battery_key),
                "label": "电量",
                "kind": "sensor",
                "group_label": "状态",
                "writable": False,
                "value_key": str(battery_key),
                "unit": "%",
            }
        )
    return controls


def _translate_fan_controls(config: dict[str, Any], *, default_rationale: list[Any] | None = None) -> list[dict[str, Any]]:
    controls = []
    power_key = config.get("power")
    if power_key:
        controls.append(
            {
                "key": str(power_key),
                "label": "电源",
                "kind": "toggle",
                "group_label": "整机",
                "writable": True,
                "value_key": str(power_key),
                "actions": _toggle_actions(str(power_key), config.get("rationale") or default_rationale),
            }
        )
    if config.get("speeds"):
        controls.append(
            {
                "key": "fan_speed",
                "label": "风速",
                "kind": "enum",
                "group_label": "送风",
                "writable": True,
                "value_key": next(iter((config.get("speeds") or [{}])[0].keys()), "fan_speed")
                if isinstance(config.get("speeds"), list) and config.get("speeds")
                else "fan_speed",
                "options": [
                    {
                        "label": str(index + 1),
                        "value": str(index + 1),
                        "control": item,
                    }
                    for index, item in enumerate(config.get("speeds") or [])
                    if isinstance(item, dict)
                ],
            }
        )
    if config.get("preset_modes"):
        controls.append(
            {
                "key": "preset_mode",
                "label": "预设模式",
                "kind": "enum",
                "group_label": "送风",
                "writable": True,
                "value_key": "preset_mode",
                "options": _option_records(config.get("preset_modes") or {}),
            }
        )
    if config.get("direction"):
        controls.append(
            {
                "key": "direction",
                "label": "转向",
                "kind": "enum",
                "group_label": "送风",
                "writable": True,
                "value_key": "direction",
                "options": _option_records(config.get("direction") or {}),
            }
        )
    if config.get("oscillate"):
        oscillate_key = config.get("oscillate")
        controls.append(
            {
                "key": str(oscillate_key),
                "label": "摆风",
                "kind": "toggle",
                "group_label": "送风",
                "writable": True,
                "value_key": str(oscillate_key),
                "actions": _toggle_actions(str(oscillate_key), config.get("rationale") or default_rationale),
            }
        )
    return controls


def _translate_humidifier_controls(config: dict[str, Any], *, default_rationale: list[Any] | None = None) -> list[dict[str, Any]]:
    controls = []
    power_key = config.get("power")
    if power_key:
        controls.append(
            {
                "key": str(power_key),
                "label": "电源",
                "kind": "toggle",
                "group_label": "整机",
                "writable": True,
                "value_key": str(power_key),
                "actions": _toggle_actions(str(power_key), config.get("rationale") or default_rationale),
            }
        )
    target_humidity = config.get("target_humidity")
    if target_humidity:
        controls.append(
            {
                "key": "target_humidity",
                "label": "目标湿度",
                "kind": "range",
                "group_label": "整机",
                "writable": True,
                "value_key": str(target_humidity),
                "range_spec": {
                    "min": config.get("min_humidity", 30),
                    "max": config.get("max_humidity", 80),
                    "step": 1,
                },
                "control_template": {str(target_humidity): "{value}"},
                "unit": "%",
            }
        )
    current_humidity = config.get("current_humidity")
    if current_humidity:
        controls.append(
            {
                "key": "current_humidity",
                "label": "当前湿度",
                "kind": "sensor",
                "group_label": "环境",
                "writable": False,
                "value_key": str(current_humidity),
                "unit": "%",
            }
        )
    if config.get("available_modes"):
        controls.append(
            {
                "key": "humidifier_mode",
                "label": "模式",
                "kind": "enum",
                "group_label": "整机",
                "writable": True,
                "value_key": "humidifier_mode",
                "options": _option_records(config.get("available_modes") or {}),
            }
        )
    return controls


def _translate_water_heater_controls(config: dict[str, Any], *, default_rationale: list[Any] | None = None) -> list[dict[str, Any]]:
    controls = []
    power_key = config.get("power")
    if power_key:
        controls.append(
            {
                "key": str(power_key),
                "label": "电源",
                "kind": "toggle",
                "group_label": "整机",
                "writable": True,
                "value_key": str(power_key),
                "actions": _toggle_actions(str(power_key), config.get("rationale") or default_rationale),
            }
        )
    target_temperature = config.get("target_temperature")
    if target_temperature:
        controls.append(
            {
                "key": "target_temperature",
                "label": "目标温度",
                "kind": "range",
                "group_label": "整机",
                "writable": True,
                "value_key": str(target_temperature),
                "range_spec": {
                    "min": config.get("min_temp", 30),
                    "max": config.get("max_temp", 75),
                    "step": 1,
                },
                "control_template": {str(target_temperature): "{value}"},
                "unit": config.get("temperature_unit", "°C"),
            }
        )
    current_temperature = config.get("current_temperature")
    if current_temperature:
        controls.append(
            {
                "key": "current_temperature",
                "label": "当前温度",
                "kind": "sensor",
                "group_label": "状态",
                "writable": False,
                "value_key": str(current_temperature),
                "unit": config.get("temperature_unit", "°C"),
            }
        )
    if config.get("operation_modes"):
        controls.append(
            {
                "key": "operation_mode",
                "label": "运行模式",
                "kind": "enum",
                "group_label": "整机",
                "writable": True,
                "value_key": "operation_mode",
                "options": _option_records(config.get("operation_modes") or {}),
            }
        )
    return controls


def _translate_light_controls(config: dict[str, Any], *, default_rationale: list[Any] | None = None) -> list[dict[str, Any]]:
    controls = []
    power_key = config.get("power")
    if power_key:
        controls.append(
            {
                "key": str(power_key),
                "label": "电源",
                "kind": "toggle",
                "group_label": "整机",
                "writable": True,
                "value_key": str(power_key),
                "actions": _toggle_actions(str(power_key), config.get("rationale") or default_rationale),
            }
        )
    brightness = config.get("brightness")
    if brightness:
        controls.append(
            {
                "key": "brightness",
                "label": "亮度",
                "kind": "range",
                "group_label": "灯光",
                "writable": True,
                "value_key": str(brightness),
                "range_spec": {"min": 0, "max": 100, "step": 1},
                "control_template": {str(brightness): "{value}"},
                "unit": "%",
            }
        )
    color_temp = config.get("color_temp")
    if color_temp:
        controls.append(
            {
                "key": "color_temp",
                "label": "色温",
                "kind": "range",
                "group_label": "灯光",
                "writable": True,
                "value_key": str(color_temp),
                "range_spec": {"min": 0, "max": 100, "step": 1},
                "control_template": {str(color_temp): "{value}"},
                "unit": "",
            }
        )
    effect_list = config.get("effect_list")
    if effect_list:
        controls.append(
            {
                "key": "effect",
                "label": "灯效",
                "kind": "enum",
                "group_label": "灯光",
                "writable": True,
                "value_key": "effect",
                "options": _option_records(effect_list),
            }
        )
    return controls


def _translate_button_controls(entity_key: str, config: dict[str, Any]) -> list[dict[str, Any]]:
    attribute_key = _resolve_attribute_key(str(entity_key), config or {})
    return [
        {
            "key": attribute_key,
            "label": str(config.get("name_attribute") or config.get("name") or "执行动作"),
            "kind": "action",
            "group_label": "动作",
            "writable": True,
            "value_key": attribute_key,
            "name_attribute": config.get("name_attribute"),
            "options": _option_records({"press": config.get("command") or {"action": "press"}}),
        }
    ]


def _translate_upstream_mapping(selected_mapping: dict[str, Any]) -> dict[str, Any]:
    entities = selected_mapping.get("entities") or {}
    default_rationale = list(selected_mapping.get("rationale") or [])
    controls: list[dict[str, Any]] = []

    climate_entities = entities.get("climate") or {}
    for _, climate_config in climate_entities.items():
        controls.extend(_translate_climate_controls(climate_config or {}, default_rationale=default_rationale))

    vacuum_entities = entities.get("vacuum") or {}
    for _, vacuum_config in vacuum_entities.items():
        controls.extend(_translate_vacuum_controls(vacuum_config or {}))

    fan_entities = entities.get("fan") or {}
    for _, fan_config in fan_entities.items():
        controls.extend(_translate_fan_controls(fan_config or {}, default_rationale=default_rationale))

    humidifier_entities = entities.get("humidifier") or {}
    for _, humidifier_config in humidifier_entities.items():
        controls.extend(_translate_humidifier_controls(humidifier_config or {}, default_rationale=default_rationale))

    water_heater_entities = entities.get("water_heater") or {}
    for _, water_heater_config in water_heater_entities.items():
        controls.extend(_translate_water_heater_controls(water_heater_config or {}, default_rationale=default_rationale))

    light_entities = entities.get("light") or {}
    for _, light_config in light_entities.items():
        controls.extend(_translate_light_controls(light_config or {}, default_rationale=default_rationale))

    button_entities = entities.get("button") or {}
    for button_key, button_config in button_entities.items():
        controls.extend(_translate_button_controls(str(button_key), button_config or {}))

    for switch_key, switch_cfg in (entities.get("switch") or {}).items():
        attribute_key = _resolve_attribute_key(str(switch_key), switch_cfg or {})
        controls.append(
            {
                "key": attribute_key,
                "label": _resolve_label(str(switch_key), switch_cfg or {}),
                "kind": "toggle",
                "group_label": "开关",
                "writable": True,
                "value_key": attribute_key,
                "name_attribute": (switch_cfg or {}).get("name_attribute"),
                "actions": _toggle_actions(attribute_key, (switch_cfg or {}).get("rationale") or default_rationale),
            }
        )

    for select_key, select_cfg in (entities.get("select") or {}).items():
        attribute_key = _resolve_attribute_key(str(select_key), select_cfg or {})
        controls.append(
            {
                "key": attribute_key,
                "label": _resolve_label(str(select_key), select_cfg or {}),
                "kind": "enum",
                "group_label": "模式",
                "writable": True,
                "value_key": attribute_key,
                "name_attribute": (select_cfg or {}).get("name_attribute"),
                "options": _option_records((select_cfg or {}).get("options") or {}),
            }
        )

    for number_key, number_cfg in (entities.get("number") or {}).items():
        attribute_key = _resolve_attribute_key(str(number_key), number_cfg or {})
        controls.append(
            {
                "key": attribute_key,
                "label": _resolve_label(str(number_key), number_cfg or {}),
                "kind": "range",
                "group_label": "数值",
                "writable": True,
                "value_key": attribute_key,
                "name_attribute": (number_cfg or {}).get("name_attribute"),
                "range_spec": {
                    "min": (number_cfg or {}).get("min", 0),
                    "max": (number_cfg or {}).get("max", 100),
                    "step": (number_cfg or {}).get("step", 1),
                },
                "control_template": {attribute_key: "{value}"},
                "unit": (number_cfg or {}).get("unit_of_measurement", ""),
            }
        )

    for sensor_key, sensor_cfg in (entities.get("sensor") or {}).items():
        attribute_key = _resolve_attribute_key(str(sensor_key), sensor_cfg or {})
        device_class = str((sensor_cfg or {}).get("device_class") or "")
        controls.append(
            {
                "key": attribute_key,
                "label": _resolve_label(str(sensor_key), sensor_cfg or {}),
                "kind": "sensor",
                "group_label": _sensor_group_label(device_class),
                "writable": False,
                "value_key": attribute_key,
                "name_attribute": (sensor_cfg or {}).get("name_attribute"),
                "unit": (sensor_cfg or {}).get("unit_of_measurement", ""),
                "device_class": device_class,
                "state_class": str((sensor_cfg or {}).get("state_class") or ""),
                "translation_key": str((sensor_cfg or {}).get("translation_key") or ""),
            }
        )

    for sensor_key, sensor_cfg in (entities.get("binary_sensor") or {}).items():
        attribute_key = _resolve_attribute_key(str(sensor_key), sensor_cfg or {})
        device_class = str((sensor_cfg or {}).get("device_class") or "")
        controls.append(
            {
                "key": attribute_key,
                "label": _resolve_label(str(sensor_key), sensor_cfg or {}),
                "kind": "sensor",
                "group_label": _sensor_group_label(device_class),
                "writable": False,
                "value_key": attribute_key,
                "name_attribute": (sensor_cfg or {}).get("name_attribute"),
                "unit": (sensor_cfg or {}).get("unit_of_measurement", ""),
                "device_class": device_class,
                "state_class": str((sensor_cfg or {}).get("state_class") or ""),
                "translation_key": str((sensor_cfg or {}).get("translation_key") or ""),
            }
        )

    seen = set()
    deduped = []
    for control in controls:
        key = control["key"]
        if key in seen:
            continue
        seen.add(key)
        deduped.append(control)

    return {
        "queries": selected_mapping.get("queries") or [],
        "rationale": selected_mapping.get("rationale") or [],
        "centralized": selected_mapping.get("centralized") or [],
        "controls": deduped,
    }


FALLBACK_MAPPINGS = {
    0xAC: {
        "category": "空调",
    },
    0xB8: {
        "category": "扫地机器人",
    },
}


def get_device_mapping(
    device_type: int,
    *,
    sn8: str = "",
    subtype: Any | None = None,
    category: str | None = None,
) -> dict[str, Any]:
    upstream_device_mappings = _load_upstream_device_mappings(device_type)
    selected_mapping = _select_upstream_mapping(
        upstream_device_mappings,
        sn8=sn8,
        subtype=subtype,
        category=category,
    )
    translated = _translate_upstream_mapping(selected_mapping) if selected_mapping else {}
    merged = dict(FALLBACK_MAPPINGS.get(device_type, {}))
    merged.update(translated)
    return merged
