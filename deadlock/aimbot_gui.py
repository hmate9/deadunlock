from __future__ import annotations

"""Simple Tkinter GUI for configuring and running the aimbot."""

import threading
import tkinter as tk
from tkinter import ttk

from .aimbot import Aimbot, AimbotSettings
from .memory import DeadlockMemory
from .update_checker import ensure_up_to_date


class AimbotApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("DeadUnlock Aimbot")
        self.settings = AimbotSettings()
        self.bot: Aimbot | None = None

        self._build_widgets()

    def _build_widgets(self) -> None:
        frm = ttk.Frame(self.root, padding=10)
        frm.grid(row=0, column=0, sticky="nsew")

        row = 0
        ttk.Label(frm, text="Headshot probability").grid(row=row, column=0, sticky="w")
        self.headshot_var = tk.DoubleVar(value=self.settings.headshot_probability)
        ttk.Entry(frm, textvariable=self.headshot_var, width=5).grid(row=row, column=1)
        row += 1

        ttk.Label(frm, text="Target select").grid(row=row, column=0, sticky="w")
        self.target_var = tk.StringVar(value=self.settings.target_select_type)
        ttk.Combobox(frm, textvariable=self.target_var, values=["fov", "distance"], width=8).grid(row=row, column=1)
        row += 1

        ttk.Label(frm, text="Smooth speed").grid(row=row, column=0, sticky="w")
        self.smooth_var = tk.DoubleVar(value=self.settings.smooth_speed)
        ttk.Entry(frm, textvariable=self.smooth_var, width=5).grid(row=row, column=1)
        row += 1

        # Grey Talon
        self.grey_enabled = tk.BooleanVar(value=self.settings.grey_talon_lock_enabled)
        ttk.Checkbutton(frm, text="Grey Talon lock", variable=self.grey_enabled).grid(row=row, column=0, sticky="w")
        self.grey_key = tk.StringVar(value=chr(self.settings.grey_talon_key))
        ttk.Entry(frm, textvariable=self.grey_key, width=3).grid(row=row, column=1)
        row += 1

        # Yamato
        self.yamato_enabled = tk.BooleanVar(value=self.settings.yamato_lock_enabled)
        ttk.Checkbutton(frm, text="Yamato lock", variable=self.yamato_enabled).grid(row=row, column=0, sticky="w")
        self.yamato_key = tk.StringVar(value=chr(self.settings.yamato_key))
        ttk.Entry(frm, textvariable=self.yamato_key, width=3).grid(row=row, column=1)
        row += 1

        # Vindicta
        self.vindicta_enabled = tk.BooleanVar(value=self.settings.vindicta_lock_enabled)
        ttk.Checkbutton(frm, text="Vindicta lock", variable=self.vindicta_enabled).grid(row=row, column=0, sticky="w")
        self.vindicta_key = tk.StringVar(value=chr(self.settings.vindicta_key))
        ttk.Entry(frm, textvariable=self.vindicta_key, width=3).grid(row=row, column=1)
        row += 1

        ttk.Button(frm, text="Start", command=self.start).grid(row=row, column=0, columnspan=2, pady=5)

    def start(self) -> None:
        self.settings.headshot_probability = float(self.headshot_var.get())
        self.settings.target_select_type = self.target_var.get()
        self.settings.smooth_speed = float(self.smooth_var.get())

        self.settings.grey_talon_lock_enabled = self.grey_enabled.get()
        if self.grey_key.get():
            self.settings.grey_talon_key = ord(self.grey_key.get().upper()[0])

        self.settings.yamato_lock_enabled = self.yamato_enabled.get()
        if self.yamato_key.get():
            self.settings.yamato_key = ord(self.yamato_key.get().upper()[0])

        self.settings.vindicta_lock_enabled = self.vindicta_enabled.get()
        if self.vindicta_key.get():
            self.settings.vindicta_key = ord(self.vindicta_key.get().upper()[0])

        ensure_up_to_date()
        mem = DeadlockMemory()
        self.bot = Aimbot(mem, self.settings)
        threading.Thread(target=self.bot.run, daemon=True).start()


def main() -> None:
    root = tk.Tk()
    AimbotApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
