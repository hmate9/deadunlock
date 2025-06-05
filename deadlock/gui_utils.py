"""GUI helper classes and functions for DeadUnlock."""

from __future__ import annotations

import json
import os
import time
import logging
import queue
import threading
import tkinter as tk
from dataclasses import asdict
from tkinter import scrolledtext, ttk, messagebox

from .update_checker import (
    _get_current_version,
    _get_latest_release,
    ensure_up_to_date,
)
from .aimbot import AimbotSettings

SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "aimbot_settings.json")


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


class UpdateProgressDialog:
    """Simple progress dialog used during updates."""

    def __init__(self, parent: tk.Tk) -> None:
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Updating DeadUnlock")
        self.dialog.geometry("600x400")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (600 // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (400 // 2)
        self.dialog.geometry(f"600x400+{x}+{y}")

        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill="both", expand=True)

        title_label = ttk.Label(main_frame, text="Updating DeadUnlock", font=("Arial", 16, "bold"))
        title_label.pack(pady=(0, 15))

        progress_frame = ttk.Frame(main_frame)
        progress_frame.pack(fill="x", pady=(0, 10))

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, mode='indeterminate', length=500)
        self.progress_bar.pack(pady=(0, 5))
        self.progress_bar.start()

        self.progress_label = ttk.Label(progress_frame, text="", font=("Arial", 9))
        self.progress_label.pack()

        self.status_label = ttk.Label(main_frame, text="Initializing update...", wraplength=550, font=("Arial", 11))
        self.status_label.pack(pady=(0, 15))

        log_frame = ttk.LabelFrame(main_frame, text="Progress Details", padding=10)
        log_frame.pack(fill="both", expand=True, pady=(10, 0))

        self.log_text = scrolledtext.ScrolledText(log_frame, height=12, width=70, state="disabled")
        self.log_text.configure(background="#f8f8f8", foreground="#333333", font=("Consolas", 9))
        self.log_text.pack(fill="both", expand=True)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill="x", pady=(15, 0))

        self.close_button = ttk.Button(button_frame, text="Close", command=self.close_dialog, state="disabled")
        self.close_button.pack(side="right")

        self.cancel_button = ttk.Button(button_frame, text="Cancel", command=self.cancel_update, state="disabled")
        self.cancel_button.pack(side="right", padx=(0, 10))

        self.dialog.protocol("WM_DELETE_WINDOW", self.on_window_close)
        self.closed = False
        self.cancelled = False

    def update_status(self, message: str, is_error: bool = False) -> None:
        """Update the status label and add to log."""
        if self.closed:
            return

        self.status_label.config(text=message)

        self.log_text.config(state='normal')
        timestamp = time.strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        if is_error:
            self.log_text.insert(tk.END, log_entry)
            self.log_text.tag_add("error", "end-2c linestart", "end-2c")
            self.log_text.tag_config("error", foreground="#cc0000")
        else:
            self.log_text.insert(tk.END, log_entry)
        self.log_text.see(tk.END)
        self.log_text.config(state='disabled')

    def set_progress(self, value: float, maximum: float = 100.0) -> None:
        """Set progress bar value."""
        if self.closed:
            return
        self.progress_bar.stop()
        self.progress_bar.config(mode='determinate', maximum=maximum, value=value)
        self.progress_label.config(text=f"{(value/maximum)*100:.1f}%")

    def enable_close(self) -> None:
        """Enable the close button."""
        self.close_button.config(state="normal")
        self.cancel_button.config(state="disabled")

    def cancel_update(self) -> None:
        """Cancel the update process."""
        self.cancelled = True
        self.cancel_button.config(state="disabled")
        self.update_status("Update cancelled by user", is_error=True)
        self.close_button.config(state="normal")

    def close_dialog(self) -> None:
        """Close the dialog."""
        self.closed = True
        self.dialog.destroy()

    def on_window_close(self) -> None:
        """Handle window close event."""
        if self.close_button['state'] == 'normal':
            self.close_dialog()
        elif self.cancel_button['state'] == 'normal':
            result = messagebox.askyesno("Cancel Update", "An update is in progress. Cancel?", parent=self.dialog)
            if result:
                self.cancel_update()
        else:
            result = messagebox.askyesno(
                "Force Close",
                "Update is in a critical phase. Force close?",
                parent=self.dialog,
            )
            if result:
                self.cancelled = True
                self.close_dialog()


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


def show_update_complete_dialog(parent: tk.Tk) -> None:
    """Show dialog informing user that update is ready and they need to close the app."""
    messagebox.showinfo(
        "Update Ready",
        "Update has been prepared successfully!\n\n"
        "Close the application now to complete the update automatically.\n"
        "The new version will be ready when you restart.",
        parent=parent
    )


def run_update_dialog(parent: tk.Tk, force: bool = False) -> None:
    """Show update progress dialog and execute the updater in a thread."""

    progress_dialog = UpdateProgressDialog(parent)

    def progress_callback(message: str) -> None:
        progress_dialog.update_status(
            message,
            is_error="fail" in message.lower() or "error" in message.lower(),
        )

    def update_thread() -> None:
        try:
            if progress_dialog.cancelled:
                return

            current_version = _get_current_version()
            if current_version:
                progress_callback(f"Current version: {current_version[:7]}")

            release = _get_latest_release()
            if release:
                tag = release.get("tag_name", "")
                if tag.startswith("build-"):
                    progress_callback(f"Latest version: {tag[6:][:7]}")

            if progress_dialog.cancelled:
                progress_callback("Update cancelled before download started")
                return

            ensure_up_to_date(
                progress_callback,
                force=force,
                cancel_check=lambda: progress_dialog.cancelled,
            )
            
            # Check if update was successful (no exceptions means success)
            if not progress_dialog.cancelled:
                # Update completed successfully, show completion dialog
                progress_dialog.dialog.after(500, lambda: show_update_complete_dialog(parent))
            
            # Enable close button
            progress_dialog.enable_close()
        except Exception as exc:
            progress_callback(f"Update failed: {exc}")
            progress_dialog.enable_close()

    threading.Thread(target=update_thread, daemon=True).start()
