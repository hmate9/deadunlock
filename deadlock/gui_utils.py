"""GUI helper classes and functions for DeadUnlock."""

from __future__ import annotations

import json
import os
import sys
import time
import logging
import queue
import threading
import tkinter as tk
from dataclasses import asdict
from tkinter import scrolledtext, ttk, messagebox

from .update_checker import _get_current_version
from .aimbot import AimbotSettings

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(__file__)

SETTINGS_FILE = os.path.join(BASE_DIR, "aimbot_settings.json")


def load_saved_settings() -> AimbotSettings:
    """Return stored :class:`AimbotSettings` or defaults."""
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return AimbotSettings(**data)
    except Exception:
        return AimbotSettings()


def save_settings(settings: AimbotSettings) -> None:
    """Persist ``settings`` to :data:`SETTINGS_FILE`."""
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as fh:
            json.dump(asdict(settings), fh, indent=2)
    except Exception as exc:
        print(f"Failed to save settings: {exc}")


def get_build_sha() -> str:
    """Return the short commit SHA for the current build."""
    try:
        sha = _get_current_version()
        if sha:
            return sha[:7]
    except Exception:
        pass
    return "unknown"


class GUILogHandler(logging.Handler):
    """Simple log handler that forwards records to a queue."""

    def __init__(self, log_queue: queue.Queue) -> None:
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.log_queue.put(self.format(record))
        except Exception:
            pass



