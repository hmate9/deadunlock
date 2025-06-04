from __future__ import annotations

"""Simple Tkinter GUI for configuring and running the aimbot."""

import json
import logging
import os
import queue
import threading
import tkinter as tk
from dataclasses import asdict
from tkinter import messagebox, scrolledtext, ttk

from .aimbot import Aimbot, AimbotSettings
from .memory import DeadlockMemory
from .update_checker import ensure_up_to_date, update_available

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


class GUILogHandler(logging.Handler):
    """Custom log handler that sends log messages to a queue for GUI display."""
    
    def __init__(self, log_queue: queue.Queue):
        super().__init__()
        self.log_queue = log_queue
    
    def emit(self, record: logging.LogRecord) -> None:
        """Send log record to the queue."""
        try:
            log_entry = self.format(record)
            self.log_queue.put(log_entry)
        except Exception:
            pass  # Ignore errors in logging


class AimbotApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("DeadUnlock Aimbot")
        self.settings = load_saved_settings()
        self.bot: Aimbot | None = None
        self.bot_thread: threading.Thread | None = None
        self.is_running = False
        self.is_paused = False
        
        # Set up logging
        self.log_queue = queue.Queue()
        self.log_handler = GUILogHandler(self.log_queue)
        self.log_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
        
        # Add handler to aimbot logger
        aimbot_logger = logging.getLogger('deadlock.aimbot')
        aimbot_logger.addHandler(self.log_handler)
        aimbot_logger.setLevel(logging.INFO)

        self._build_widgets()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # Start log processing
        self._process_log_queue()

        self._notify_if_outdated()

    def _notify_if_outdated(self) -> None:
        """Show a warning dialog if the local repo is outdated."""
        if update_available():
            messagebox.showwarning(
                "Update available",
                "A newer DeadUnlock version is available. Please run 'git pull'.",
            )

    def _build_widgets(self) -> None:
        # Main container
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        
        # Settings frame
        settings_frame = ttk.LabelFrame(main_frame, text="Settings", padding=10)
        settings_frame.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        
        row = 0
        ttk.Label(settings_frame, text="Headshot probability").grid(row=row, column=0, sticky="w")
        self.headshot_var = tk.DoubleVar(value=self.settings.headshot_probability)
        ttk.Entry(settings_frame, textvariable=self.headshot_var, width=5).grid(row=row, column=1, sticky="w")
        row += 1

        ttk.Label(settings_frame, text="Target select").grid(row=row, column=0, sticky="w")
        self.target_var = tk.StringVar(value=self.settings.target_select_type)
        ttk.Combobox(settings_frame, textvariable=self.target_var, values=["fov", "distance"], width=8).grid(row=row, column=1, sticky="w")
        row += 1

        ttk.Label(settings_frame, text="Smooth speed").grid(row=row, column=0, sticky="w")
        self.smooth_var = tk.DoubleVar(value=self.settings.smooth_speed)
        ttk.Entry(settings_frame, textvariable=self.smooth_var, width=5).grid(row=row, column=1, sticky="w")
        row += 1

        # Grey Talon
        self.grey_enabled = tk.BooleanVar(value=self.settings.grey_talon_lock_enabled)
        ttk.Checkbutton(settings_frame, text="Grey Talon lock", variable=self.grey_enabled).grid(row=row, column=0, sticky="w")
        self.grey_key = tk.StringVar(value=chr(self.settings.grey_talon_key))
        ttk.Entry(settings_frame, textvariable=self.grey_key, width=3).grid(row=row, column=1, sticky="w")
        row += 1

        # Yamato
        self.yamato_enabled = tk.BooleanVar(value=self.settings.yamato_lock_enabled)
        ttk.Checkbutton(settings_frame, text="Yamato lock", variable=self.yamato_enabled).grid(row=row, column=0, sticky="w")
        self.yamato_key = tk.StringVar(value=chr(self.settings.yamato_key))
        ttk.Entry(settings_frame, textvariable=self.yamato_key, width=3).grid(row=row, column=1, sticky="w")
        row += 1

        # Vindicta
        self.vindicta_enabled = tk.BooleanVar(value=self.settings.vindicta_lock_enabled)
        ttk.Checkbutton(settings_frame, text="Vindicta lock", variable=self.vindicta_enabled).grid(row=row, column=0, sticky="w")
        self.vindicta_key = tk.StringVar(value=chr(self.settings.vindicta_key))
        ttk.Entry(settings_frame, textvariable=self.vindicta_key, width=3).grid(row=row, column=1, sticky="w")
        row += 1

        # Control buttons
        control_frame = ttk.Frame(settings_frame)
        control_frame.grid(row=row, column=0, columnspan=2, pady=10, sticky="ew")
        
        self.start_button = ttk.Button(control_frame, text="Start", command=self.start)
        self.start_button.pack(side="left", padx=(0, 5))
        
        self.pause_button = ttk.Button(control_frame, text="Pause", command=self.toggle_pause, state="disabled")
        self.pause_button.pack(side="left", padx=(0, 5))
        
        self.stop_button = ttk.Button(control_frame, text="Stop", command=self.stop, state="disabled")
        self.stop_button.pack(side="left")
        
        # Status frame
        status_frame = ttk.LabelFrame(main_frame, text="Status", padding=5)
        status_frame.grid(row=1, column=0, sticky="ew", pady=(10, 0), padx=(0, 5))
        
        self.status_label = ttk.Label(status_frame, text="Status: Stopped", foreground="red")
        self.status_label.pack()
        
        # Log frame
        log_frame = ttk.LabelFrame(main_frame, text="Log", padding=5)
        log_frame.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=(5, 0))
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(0, weight=1)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, width=50, height=20, state='disabled')
        self.log_text.pack(fill="both", expand=True)
        
        # Clear log button
        ttk.Button(log_frame, text="Clear Log", command=self.clear_log).pack(pady=(5, 0))

    def _process_log_queue(self) -> None:
        """Process log messages from queue and display them in the log text widget."""
        try:
            while True:
                log_message = self.log_queue.get_nowait()
                self.log_text.config(state='normal')
                self.log_text.insert(tk.END, log_message + '\n')
                self.log_text.see(tk.END)
                self.log_text.config(state='disabled')
        except queue.Empty:
            pass
        finally:
            # Schedule next check
            self.root.after(100, self._process_log_queue)
    
    def clear_log(self) -> None:
        """Clear the log display."""
        self.log_text.config(state='normal')
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state='disabled')
    
    def _update_status(self, status: str, color: str = "black") -> None:
        """Update the status label."""
        self.status_label.config(text=f"Status: {status}", foreground=color)
    
    def _update_button_states(self) -> None:
        """Update button states based on current aimbot status."""
        if not self.is_running:
            self.start_button.config(state="normal")
            self.pause_button.config(state="disabled", text="Pause")
            self.stop_button.config(state="disabled")
        else:
            self.start_button.config(state="disabled")
            self.pause_button.config(state="normal")
            self.stop_button.config(state="normal")
            if self.is_paused:
                self.pause_button.config(text="Resume")
            else:
                self.pause_button.config(text="Pause")
        """Update :attr:`settings` from widget values."""
    def _apply_widget_values(self) -> None:
        """Update :attr:`settings` from widget values."""
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

    def start(self) -> None:
        """Start the aimbot."""
        if self.is_running:
            return
            
        self._apply_widget_values()
        save_settings(self.settings)

        try:
            ensure_up_to_date()
            mem = DeadlockMemory()
            self.bot = Aimbot(mem, self.settings)
            
            self.is_running = True
            self.is_paused = False
            self._update_status("Running", "green")
            self._update_button_states()
            
            # Start aimbot in a separate thread
            self.bot_thread = threading.Thread(target=self._run_aimbot, daemon=True)
            self.bot_thread.start()
            
            self.log_text.config(state='normal')
            self.log_text.insert(tk.END, "Aimbot started successfully.\n")
            self.log_text.see(tk.END)
            self.log_text.config(state='disabled')
            
        except Exception as e:
            self._update_status("Error", "red")
            self.is_running = False
            self._update_button_states()
            messagebox.showerror("Error", f"Failed to start aimbot: {str(e)}")
    
    def _run_aimbot(self) -> None:
        """Run the aimbot loop with pause support."""
        if self.bot:
            try:
                self.bot.run()
            except Exception as e:
                self.log_queue.put(f"Aimbot error: {str(e)}")
                self.is_running = False
                self.root.after(0, lambda: (
                    self._update_status("Error", "red"),
                    self._update_button_states()
                ))
    
    def toggle_pause(self) -> None:
        """Toggle pause state of the aimbot."""
        if not self.is_running or not self.bot:
            return
            
        self.is_paused = not self.is_paused
        if self.is_paused:
            self.bot.pause()
            self._update_status("Paused", "orange")
            self.log_text.config(state='normal')
            self.log_text.insert(tk.END, "Aimbot paused.\n")
            self.log_text.see(tk.END)
            self.log_text.config(state='disabled')
        else:
            self.bot.resume()
            self._update_status("Running", "green")
            self.log_text.config(state='normal')
            self.log_text.insert(tk.END, "Aimbot resumed.\n")
            self.log_text.see(tk.END)
            self.log_text.config(state='disabled')
        
        self._update_button_states()
    
    def stop(self) -> None:
        """Stop the aimbot."""
        if not self.is_running:
            return
            
        if self.bot:
            self.bot.stop()
            
        self.is_running = False
        self.is_paused = False
        self.bot = None
        
        self._update_status("Stopped", "red")
        self._update_button_states()
        
        self.log_text.config(state='normal')
        self.log_text.insert(tk.END, "Aimbot stopped.\n")
        self.log_text.see(tk.END)
        self.log_text.config(state='disabled')

    def on_close(self) -> None:
        """Handle window close event."""
        self._apply_widget_values()
        save_settings(self.settings)
        
        if self.is_running:
            self.stop()
        
        # Clean up logging handler
        if hasattr(self, 'log_handler'):
            aimbot_logger = logging.getLogger('deadlock.aimbot')
            aimbot_logger.removeHandler(self.log_handler)
            
        self.root.destroy()


def main() -> None:
    """Main entry point for the GUI application."""
    # Ensure only one instance can run
    try:
        root = tk.Tk()
        root.resizable(True, True)
        app = AimbotApp(root)
        root.mainloop()
    except Exception as e:
        print(f"Error starting GUI: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
