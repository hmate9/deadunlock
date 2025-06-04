"""Helper package exposing a minimal Deadlock API."""

from __future__ import annotations

import importlib

__all__ = [
    "DeadlockMemory",
    "Aimbot",
    "AimbotSettings",
    "ESP",
    "HeroIds",
]

_MODULES: dict[str, str] = {
    "DeadlockMemory": "memory",
    "Aimbot": "aimbot",
    "AimbotSettings": "aimbot",
    "ESP": "esp",
    "HeroIds": "heroes",
}


def __getattr__(name: str):
    module_name = _MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = importlib.import_module(f".{module_name}", __name__)
    return getattr(module, name)
