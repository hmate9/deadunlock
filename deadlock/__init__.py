"""Public API for interacting with Deadlock.

The heavy ESP module depends on :mod:`numpy` which is not required by the
aimbot.  To keep binary start-up lightweight, it is imported lazily on first
access.
"""

from .memory import DeadlockMemory
from .aimbot import Aimbot, AimbotSettings
from .heroes import HeroIds

__all__ = [
    "DeadlockMemory",
    "Aimbot",
    "AimbotSettings",
    "HeroIds",
    "ESP",
]


def __getattr__(name: str):
    """Lazily import optional modules on demand."""
    if name == "ESP":
        from .esp import ESP

        return ESP
    raise AttributeError(name)
