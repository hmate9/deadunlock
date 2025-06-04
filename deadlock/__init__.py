"""Helper package exposing a minimal Deadlock API."""

from .memory import DeadlockMemory
from .heroes import HeroIds

__all__ = [
    "DeadlockMemory",
    "Aimbot",
    "AimbotSettings",
    "ESP",
    "HeroIds",
]


def __getattr__(name):
    """Lazily import heavy modules only when accessed."""

    if name in {"Aimbot", "AimbotSettings"}:
        from .aimbot import Aimbot, AimbotSettings
        globals()["Aimbot"] = Aimbot
        globals()["AimbotSettings"] = AimbotSettings
        return globals()[name]
    if name == "ESP":
        from .esp import ESP
        globals()["ESP"] = ESP
        return ESP
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
