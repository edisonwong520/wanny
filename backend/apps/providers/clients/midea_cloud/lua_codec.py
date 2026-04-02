from __future__ import annotations

import base64
import importlib.util
import json
import logging
import threading
from functools import lru_cache
from pathlib import Path
from typing import Any

try:
    from lupa import LuaError
    from lupa.lua51 import LuaRuntime as LupaLuaRuntime
except Exception:  # pragma: no cover - dependency import fallback
    LuaError = Exception
    LupaLuaRuntime = None


logger = logging.getLogger(__name__)

UPSTREAM_ROOT = Path(__file__).resolve().parents[5] / "third_party" / "midea_auto_cloud" / "custom_components" / "midea_auto_cloud"
UPSTREAM_CONST_FILE = UPSTREAM_ROOT / "const.py"


def lua_runtime_available() -> bool:
    return LupaLuaRuntime is not None


@lru_cache(maxsize=1)
def _load_upstream_lua_support() -> tuple[str, str]:
    if not UPSTREAM_CONST_FILE.exists():
        raise FileNotFoundError(f"Upstream const.py not found: {UPSTREAM_CONST_FILE}")

    spec = importlib.util.spec_from_file_location("wanny_midea_upstream_const", UPSTREAM_CONST_FILE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load upstream constants from {UPSTREAM_CONST_FILE}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    cjson_lua = base64.b64decode(getattr(module, "CJSON_LUA").encode("utf-8")).decode("utf-8")
    bit_lua = base64.b64decode(getattr(module, "BIT_LUA").encode("utf-8")).decode("utf-8")
    return cjson_lua, bit_lua


def ensure_lua_support_files(path: Path) -> tuple[Path, Path]:
    path.mkdir(parents=True, exist_ok=True)
    cjson_path = path / "cjson.lua"
    bit_path = path / "bit.lua"
    cjson_lua, bit_lua = _load_upstream_lua_support()

    if not cjson_path.exists():
        cjson_path.write_text(cjson_lua, encoding="utf-8")
    if not bit_path.exists():
        bit_path.write_text(bit_lua, encoding="utf-8")

    return cjson_path, bit_path


class MideaLuaCodec:
    def __init__(
        self,
        file: str | Path,
        *,
        device_type: str | None = None,
        sn: str | None = None,
        subtype: str | None = None,
        suppress_output: bool = True,
    ) -> None:
        if LupaLuaRuntime is None:
            raise RuntimeError("lupa is not installed")

        self.file = Path(file).resolve()
        self.device_type = device_type
        self.sn = sn
        self.subtype = subtype
        ensure_lua_support_files(self.file.parent)

        runtime = LupaLuaRuntime()
        if suppress_output:
            runtime.execute(
                """
                print = function(...) end
                if io ~= nil then
                  io.write = function(...) end
                end
                """
            )

        lua_dir = str(self.file.parent).replace("\\", "/").replace('"', '\\"')
        lua_file = str(self.file).replace("\\", "/").replace('"', '\\"')
        runtime.execute(f'package.path = package.path .. ";{lua_dir}/?.lua"')
        runtime.execute('require "cjson"')
        runtime.execute('require "bit"')
        runtime.execute(f'dofile("{lua_file}")')

        self._runtime = runtime
        self._lock = threading.Lock()
        self._json_to_data = runtime.eval("function(param) return jsonToData(param) end")
        self._data_to_json = runtime.eval("function(param) return dataToJson(param) end")

    def _build_base_dict(self) -> dict[str, Any]:
        device_info = {}
        if self.sn:
            device_info["deviceSN"] = self.sn
        if self.subtype:
            device_info["deviceSubType"] = self.subtype
        return {"deviceinfo": device_info}

    def json_to_data(self, payload: str) -> str:
        with self._lock:
            return self._json_to_data(payload)

    def data_to_json(self, payload: str) -> str:
        with self._lock:
            return self._data_to_json(payload)

    def build_query(self, append: dict[str, Any] | None = None) -> str | None:
        payload = self._build_base_dict()
        payload["query"] = {} if append is None else append
        return self._safe_json_to_data(payload, "build_query")

    def build_control(
        self,
        append: dict[str, Any] | None = None,
        *,
        status: dict[str, Any] | None = None,
    ) -> str | None:
        payload = self._build_base_dict()
        payload["control"] = {} if append is None else append
        payload["status"] = {} if status is None else status

        if self.device_type == "T0xD9":
            control_keys = list((append or {}).keys())
            prefix = control_keys[0].split("_")[0] if control_keys else "db"
            payload["control"]["bucket"] = prefix
        elif self.device_type == "T0x9C":
            control_keys = list((append or {}).keys())
            prefix = control_keys[0].split("_")[0] if control_keys else "total"
            payload["control"]["type"] = prefix
        elif self.device_type == "T0xCF":
            payload["control"]["control_type"] = "0x11"

        return self._safe_json_to_data(payload, "build_control")

    def build_status(self, append: dict[str, Any] | None = None) -> str | None:
        payload = self._build_base_dict()
        payload["status"] = {} if append is None else append
        return self._safe_json_to_data(payload, "build_status")

    def decode_status(self, data: str) -> dict[str, Any] | None:
        payload = self._build_base_dict()
        payload["msg"] = {"data": data}
        try:
            result = self.data_to_json(json.dumps(payload))
            status = json.loads(result)
        except (LuaError, ValueError, TypeError) as exc:
            logger.warning("Failed to decode Midea lua status from %s: %s", self.file, exc)
            return None
        return status.get("status") if isinstance(status, dict) else None

    def _safe_json_to_data(self, payload: dict[str, Any], operation: str) -> str | None:
        json_payload = json.dumps(payload, ensure_ascii=False)
        try:
            return self.json_to_data(json_payload)
        except LuaError as exc:
            logger.warning("Lua codec %s failed for %s: %s", operation, self.file, exc)
            return None
