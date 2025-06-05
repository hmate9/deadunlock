from __future__ import annotations

"""Simple Tkinter GUI for configuring and running the aimbot."""

import logging
import os
import queue
import sys
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

from .aimbot import Aimbot, AimbotSettings
from .memory import DeadlockMemory
from .gui_utils import (
    GUILogHandler,
    load_saved_settings,
    save_settings,
    get_build_sha,
)
from .update_checker import update_available, open_release_page




class AimbotApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("DeadUnlock Aimbot")
        self.root.geometry("750x520")
        self.root.minsize(620, 480)
        
        # Set window icon
        try:
            icon_path = os.path.join(os.path.dirname(__file__), "..", "img", "deadunlock_icon.png")
            if os.path.exists(icon_path):
                icon = tk.PhotoImage(file=icon_path)
                self.root.iconphoto(True, icon)
        except Exception:
            pass  # Ignore if icon can't be loaded
        
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
        
        # Add handler to offset finder logger to show initialization progress
        offset_finder_logger = logging.getLogger('offset_finder')
        offset_finder_logger.addHandler(self.log_handler)
        offset_finder_logger.setLevel(logging.INFO)

        self._build_widgets()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # Start log processing
        self._process_log_queue()

        self._notify_if_outdated()

    def _notify_if_outdated(self) -> None:
        """Show a warning dialog if the local repo is outdated."""
        if update_available():
            result = messagebox.askyesno(
                "Update available",
                "A newer DeadUnlock version is available. Open the download page?",
            )
            if result:
                open_release_page()


    def _check_for_updates(self) -> None:
        """Manually check for updates and offer to update if available."""
        try:
            if update_available():
                result = messagebox.askyesno(
                    "Update Available",
                    "A newer DeadUnlock version is available. Open the download page?",
                )
                if result:
                    open_release_page()
            else:
                messagebox.showinfo(
                    "No Updates",
                    "You are running the latest version of DeadUnlock.",
                )
        except Exception as e:
            messagebox.showerror(
                "Update Check Failed",
                f"Failed to check for updates: {e}"
            )

    def _build_widgets(self) -> None:
        """Create and arrange the GUI widgets."""
        self._configure_style()
        self._create_menu()

        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        self._build_settings_frame(main_frame)
        self._build_status_frame(main_frame)
        self._build_log_frame(main_frame)
        self._add_build_label(main_frame)
    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        default_font = ("Segoe UI", 10)
        self.root.option_add("*Font", default_font)
        style.configure("TButton", padding=6)
        style.configure("TLabel", padding=(2, 2))
        style.configure("TCheckbutton", padding=(2, 2))

    def _create_menu(self) -> None:
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="Check for Updates", command=self._check_for_updates)

    def _build_settings_frame(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Settings", padding=10)
        frame.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        row = 0
        ttk.Label(frame, text="Headshot probability").grid(row=row, column=0, sticky="w")
        self.headshot_var = tk.DoubleVar(value=self.settings.headshot_probability)
        ttk.Entry(frame, textvariable=self.headshot_var, width=5).grid(row=row, column=1, sticky="w")
        row += 1
        ttk.Label(frame, text="Target select").grid(row=row, column=0, sticky="w")
        self.target_var = tk.StringVar(value=self.settings.target_select_type)
        ttk.Combobox(frame, textvariable=self.target_var, values=["fov", "distance"], width=8).grid(row=row, column=1, sticky="w")
        row += 1
        ttk.Label(frame, text="Smooth speed").grid(row=row, column=0, sticky="w")
        self.smooth_var = tk.DoubleVar(value=self.settings.smooth_speed)
        ttk.Entry(frame, textvariable=self.smooth_var, width=5).grid(row=row, column=1, sticky="w")
        row += 1
        hero_frame = ttk.LabelFrame(frame, text="Hero Ability Locks", padding=5)
        hero_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(5, 0))
        hero_row = 0
        ttk.Label(hero_frame, text="Hero").grid(row=hero_row, column=0, sticky="w")
        ttk.Label(hero_frame, text="Keybind").grid(row=hero_row, column=1, sticky="w")
        hero_row += 1
        self.grey_enabled = tk.BooleanVar(value=self.settings.grey_talon_lock_enabled)
        ttk.Checkbutton(hero_frame, text="Grey Talon", variable=self.grey_enabled).grid(row=hero_row, column=0, sticky="w")
        self.grey_key = tk.StringVar(value=chr(self.settings.grey_talon_key))
        ttk.Entry(hero_frame, textvariable=self.grey_key, width=3).grid(row=hero_row, column=1, sticky="w")
        hero_row += 1
        self.yamato_enabled = tk.BooleanVar(value=self.settings.yamato_lock_enabled)
        ttk.Checkbutton(hero_frame, text="Yamato", variable=self.yamato_enabled).grid(row=hero_row, column=0, sticky="w")
        self.yamato_key = tk.StringVar(value=chr(self.settings.yamato_key))
        ttk.Entry(hero_frame, textvariable=self.yamato_key, width=3).grid(row=hero_row, column=1, sticky="w")
        hero_row += 1
        self.vindicta_enabled = tk.BooleanVar(value=self.settings.vindicta_lock_enabled)
        ttk.Checkbutton(hero_frame, text="Vindicta", variable=self.vindicta_enabled).grid(row=hero_row, column=0, sticky="w")
        self.vindicta_key = tk.StringVar(value=chr(self.settings.vindicta_key))
        ttk.Entry(hero_frame, textvariable=self.vindicta_key, width=3).grid(row=hero_row, column=1, sticky="w")
        hero_row += 1
        row += 1
        control_frame = ttk.Frame(frame)
        control_frame.grid(row=row, column=0, columnspan=2, pady=10, sticky="ew")
        self.start_button = ttk.Button(control_frame, text="Start", command=self.start)
        self.start_button.pack(side="left", padx=(0, 5))
        self.pause_button = ttk.Button(control_frame, text="Pause", command=self.toggle_pause, state="disabled")
        self.pause_button.pack(side="left", padx=(0, 5))
        self.stop_button = ttk.Button(control_frame, text="Stop", command=self.stop, state="disabled")
        self.stop_button.pack(side="left")

    def _build_status_frame(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Status", padding=5)
        frame.grid(row=1, column=0, sticky="ew", pady=(10, 0), padx=(0, 5))
        self.status_label = ttk.Label(frame, text="Status: Stopped", foreground="red")
        self.status_label.pack()

    def _build_log_frame(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Log", padding=5)
        frame.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=(5, 0))
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(0, weight=1)
        self.log_text = scrolledtext.ScrolledText(frame, width=50, height=20, state="disabled")
        self.log_text.configure(background="#1e1e1e", foreground="#dcdcdc", insertbackground="#ffffff")
        self.log_text.pack(fill="both", expand=True)
        ttk.Button(frame, text="Clear Log", command=self.clear_log).pack(pady=(5, 0))

    def _add_build_label(self, parent: ttk.Frame) -> None:
        sha = get_build_sha()
        self.build_label = ttk.Label(parent, text=f"build {sha}", font=("TkDefaultFont", 8))
        self.build_label.grid(row=2, column=1, sticky="e", padx=(0, 2), pady=(2, 0))
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
            # For binary releases, update check is handled in _notify_if_outdated
            # For source installations, we can still do a quick check here
            if not getattr(sys, 'frozen', False):
                # Show a simple progress dialog for source updates too
                if update_available():
                    result = messagebox.askyesno(
                        "Update Available",
                        "A newer version is available. Open the download page?",
                    )
                    if result:
                        open_release_page()
                        return

            self.is_running = True
            self.is_paused = False
            self._update_status("Starting...", "blue")
            self._update_button_states()

            # Start initialisation and aimbot in a separate thread
            self.bot_thread = threading.Thread(
                target=self._initialise_and_run, daemon=True
            )
            self.bot_thread.start()

        except Exception as e:
            self._update_status("Error", "red")
            self.is_running = False
            self._update_button_states()
            messagebox.showerror("Error", f"Failed to start aimbot: {str(e)}")

    def _initialise_and_run(self) -> None:
        """Initialise memory and run the aimbot."""
        try:
            mem = DeadlockMemory()
            self.bot = Aimbot(mem, self.settings)
            self.log_queue.put("Aimbot started successfully.")
            self.root.after(0, lambda: (
                self._update_status("Running", "green"),
                self._update_button_states()
            ))
            self._run_aimbot()
        except Exception as exc:
            self.is_running = False
            msg = str(exc)
            self.log_queue.put(f"Aimbot init error: {msg}")
            self.root.after(0, lambda: (
                self._update_status("Error", "red"),
                self._update_button_states(),
                messagebox.showerror("Error", f"Failed to start aimbot: {msg}")
            ))
    
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
            
            # Also clean up offset finder logger
            offset_finder_logger = logging.getLogger('offset_finder')
            offset_finder_logger.removeHandler(self.log_handler)
            
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

