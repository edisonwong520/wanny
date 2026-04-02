from __future__ import annotations

import importlib.util
import sys
import types
from functools import lru_cache
from pathlib import Path


PROTO_ROOT = (
    Path(__file__).resolve().parents[5]
    / "third_party"
    / "mbapi2020"
    / "custom_components"
    / "mbapi2020"
    / "proto"
)

PACKAGE_NAMES = (
    "custom_components",
    "custom_components.mbapi2020",
    "custom_components.mbapi2020.proto",
)

MODULE_ORDER = (
    "gogo_pb2",
    "protos_pb2",
    "service_activation_pb2",
    "user_events_pb2",
    "vehicle_commands_pb2",
    "vehicle_events_pb2",
    "vehicleapi_pb2",
    "client_pb2",
)


def _ensure_package(name: str, path: Path | None = None) -> None:
    if name in sys.modules:
        return
    module = types.ModuleType(name)
    module.__path__ = [str(path)] if path else []  # type: ignore[attr-defined]
    sys.modules[name] = module


def _load_module(module_name: str):
    full_name = f"custom_components.mbapi2020.proto.{module_name}"
    if full_name in sys.modules:
        return sys.modules[full_name]

    module_path = PROTO_ROOT / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(full_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load protobuf module: {full_name}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = module
    spec.loader.exec_module(module)
    return module


@lru_cache(maxsize=1)
def load_proto_modules() -> dict[str, object]:
    _ensure_package("custom_components")
    _ensure_package("custom_components.mbapi2020")
    _ensure_package("custom_components.mbapi2020.proto", PROTO_ROOT)

    loaded: dict[str, object] = {}
    for module_name in MODULE_ORDER:
        loaded[module_name] = _load_module(module_name)
    return loaded

