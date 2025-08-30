from __future__ import annotations

"""Modern Tkinter GUI for configuring and running the aimbot.

This module provides a lightweight, modernised interface using ttk
widgets, a custom dark theme, and an improved layout with a header,
tabbed content, and a status bar. Functionality remains the same while
presenting a cleaner, more professional experience.
"""

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
    """Main application controller for the DeadUnlock GUI."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("DeadUnlock")
        self.root.geometry("860x580")
        self.root.minsize(720, 520)

        # Set window icon (best-effort)
        try:
            icon_path = os.path.join(
                os.path.dirname(__file__), "..", "img", "deadunlock_icon.png"
            )
            if os.path.exists(icon_path):
                icon = tk.PhotoImage(file=icon_path)
                self.root.iconphoto(True, icon)
        except Exception:
            pass

        self.settings = load_saved_settings()
        self.bot: Aimbot | None = None
        self.bot_thread: threading.Thread | None = None
        self.is_running = False
        self.is_paused = False

        # Set up logging
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.log_handler = GUILogHandler(self.log_queue)
        self.log_handler.setFormatter(
            logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
        )

        # Attach loggers
        aimbot_logger = logging.getLogger('deadlock.aimbot')
        aimbot_logger.addHandler(self.log_handler)
        aimbot_logger.setLevel(logging.INFO)

        offset_finder_logger = logging.getLogger('offset_finder')
        offset_finder_logger.addHandler(self.log_handler)
        offset_finder_logger.setLevel(logging.INFO)

        self._build_widgets()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Start log processing and do initial update check
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

        # Root grid: header, notebook, statusbar
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        self._build_header()
        self._build_tabs()
        self._build_statusbar()

    def _configure_style(self) -> None:
        """Create a clean dark ttk theme with accent buttons and sliders."""
        style = ttk.Style(self.root)
        base_theme = "clam" if "clam" in style.theme_names() else style.theme_use()
        if "deadunlock" not in style.theme_names():
            # Palette
            bg = "#0f1115"
            surface = "#151923"
            border = "#2a2f3a"
            fg = "#e5e7eb"
            muted = "#9ca3af"
            accent = "#2563eb"
            accent_active = "#1d4ed8"
            danger = "#ef4444"
            danger_active = "#dc2626"

            style.theme_create(
                "deadunlock",
                parent=base_theme,
                settings={
                    ".": {
                        "configure": {
                            "background": bg,
                            "foreground": fg,
                        }
                    },
                    "TFrame": {
                        "configure": {"background": bg}
                    },
                    "TLabelframe": {
                        "configure": {
                            "background": surface,
                            "bordercolor": border,
                            "relief": "groove",
                            "padding": 10,
                        }
                    },
                    "TLabelframe.Label": {
                        "configure": {"foreground": muted, "font": ("Segoe UI", 10, "bold")}
                    },
                    "TLabel": {
                        "configure": {"background": bg, "foreground": fg}
                    },
                    "TButton": {
                        "configure": {
                            "padding": 8,
                            "background": surface,
                            "foreground": fg,
                            "bordercolor": border,
                            "relief": "flat",
                        },
                        "map": {
                            "background": [
                                ("active", "#1f2430"),
                                ("disabled", surface),
                            ],
                            "foreground": [("disabled", muted)],
                        },
                    },
                    "Accent.TButton": {
                        "configure": {
                            "background": accent,
                            "foreground": "#ffffff",
                        },
                        "map": {
                            "background": [("active", accent_active)],
                            "foreground": [("disabled", "#c7d2fe")],
                        },
                    },
                    "Danger.TButton": {
                        "configure": {
                            "background": danger,
                            "foreground": "#ffffff",
                        },
                        "map": {
                            "background": [("active", danger_active)],
                            "foreground": [("disabled", "#fecaca")],
                        },
                    },
                    "TCheckbutton": {
                        "configure": {"background": bg, "foreground": fg, "padding": (2, 2)}
                    },
                    "TEntry": {
                        "configure": {"fieldbackground": surface, "foreground": fg}
                    },
                    "TCombobox": {
                        "configure": {
                            "selectbackground": surface,
                            "fieldbackground": surface,
                            "foreground": fg,
                        }
                    },
                    "Horizontal.TScale": {
                        "configure": {"background": bg},
                    },
                    "TNotebook": {
                        "configure": {"background": bg}
                    },
                    "TNotebook.Tab": {
                        "configure": {"padding": (12, 6)}
                    },
                },
            )
        style.theme_use("deadunlock" if "deadunlock" in style.theme_names() else base_theme)

        default_font = ("Segoe UI", 10)
        self.root.option_add("*Font", default_font)
        try:
            self.root.configure(bg="#0f1115")
        except Exception:
            pass

    def _create_menu(self) -> None:
        """Create the application menubar."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(
            label="Check for Updates", command=self._check_for_updates
        )

    def _build_header(self) -> None:
        """Create the top header with title and primary controls."""
        header = ttk.Frame(self.root, padding=(12, 12, 12, 6))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(2, weight=1)

        # Title + icon
        title_frame = ttk.Frame(header)
        title_frame.grid(row=0, column=0, sticky="w")
        try:
            icon_path = os.path.join(
                os.path.dirname(__file__), "..", "img", "deadunlock_icon.png"
            )
            if os.path.exists(icon_path):
                icon = tk.PhotoImage(file=icon_path)
                icon_label = ttk.Label(title_frame, image=icon)
                icon_label.image = icon  # keep reference
                icon_label.grid(row=0, column=0, padx=(0, 8))
        except Exception:
            pass
        ttk.Label(
            title_frame, text="DeadUnlock", font=("Segoe UI", 14, "bold")
        ).grid(row=0, column=1, sticky="w")

        # Spacer
        ttk.Frame(header).grid(row=0, column=1, padx=10)

        # Controls: single Start/Stop toggle for clarity
        controls = ttk.Frame(header)
        controls.grid(row=0, column=2, sticky="e")
        self.toggle_button = ttk.Button(
            controls,
            text="Start",
            style="Accent.TButton",
            command=self.toggle_run,
            width=14,
        )
        self.toggle_button.grid(row=0, column=0, padx=(0, 0))

    def _build_tabs(self) -> None:
        """Create the main notebook and its tabs."""
        self.notebook = ttk.Notebook(self.root)
        self.notebook.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 8))

        settings_tab = ttk.Frame(self.notebook, padding=10)
        log_tab = ttk.Frame(self.notebook, padding=10)

        self.notebook.add(settings_tab, text="Settings")
        self.notebook.add(log_tab, text="Logs")

        self._build_settings_frame(settings_tab)
        self._build_log_frame(log_tab)

    def _build_statusbar(self) -> None:
        """Create a slim status bar at the bottom."""
        bar = ttk.Frame(self.root, padding=(12, 6))
        bar.grid(row=2, column=0, sticky="ew")
        bar.columnconfigure(0, weight=1)

        self.status_label = ttk.Label(bar, text="Status: Stopped", foreground="red")
        self.status_label.grid(row=0, column=0, sticky="w")

        sha = get_build_sha()
        ttk.Label(
            bar, text=f"build {sha}", font=("Segoe UI", 9)
        ).grid(row=0, column=1, sticky="e")

    def _build_settings_frame(self, parent: ttk.Frame) -> None:
        """Build the settings tab content."""
        # Aim settings
        frame = ttk.LabelFrame(parent, text="Aim Settings")
        frame.grid(row=0, column=0, sticky="ew")
        frame.columnconfigure(1, weight=1)

        row = 0
        ttk.Label(frame, text="Headshot probability").grid(row=row, column=0, sticky="w")
        self.headshot_var = tk.DoubleVar(value=self.settings.headshot_probability)
        self.headshot_percent = ttk.Label(frame, text=f"{int(self.headshot_var.get()*100)}%")
        self.headshot_percent.grid(row=row, column=2, sticky="e")
        hs_scale = ttk.Scale(
            frame,
            variable=self.headshot_var,
            from_=0.0,
            to=1.0,
            orient=tk.HORIZONTAL,
            length=220,
            command=lambda _evt=None: self._on_headshot_change(),
        )
        hs_scale.grid(row=row, column=1, sticky="ew", padx=8)

        self.headshot_warning = ttk.Label(
            frame,
            text="High headshot values may flag your account!",
            foreground="red",
        )
        row += 1
        self.headshot_warning.grid(row=row, column=0, columnspan=3, sticky="w", pady=(4, 0))
        self.headshot_warning.grid_remove()
        self._update_headshot_warning()

        row += 1
        self.acquire_headshot_var = tk.BooleanVar(
            value=self.settings.headshot_on_acquire
        )
        ttk.Checkbutton(
            frame,
            text="Headshot on acquire",
            variable=self.acquire_headshot_var,
        ).grid(row=row, column=0, columnspan=3, sticky="w", pady=(6, 0))

        row += 1
        ttk.Label(frame, text="Target selection").grid(row=row, column=0, sticky="w")
        self.target_var = tk.StringVar(value=self.settings.target_select_type)
        ttk.Combobox(
            frame,
            textvariable=self.target_var,
            values=["fov", "distance"],
            width=10,
            state="readonly",
        ).grid(row=row, column=1, sticky="w", padx=8)

        row += 1
        ttk.Label(frame, text="Smooth speed").grid(row=row, column=0, sticky="w")
        self.smooth_var = tk.DoubleVar(value=self.settings.smooth_speed)
        self.smooth_value_label = ttk.Label(frame, text=f"{self.smooth_var.get():.1f}")
        self.smooth_value_label.grid(row=row, column=2, sticky="e")
        sm_scale = ttk.Scale(
            frame,
            variable=self.smooth_var,
            from_=1.0,
            to=20.0,
            orient=tk.HORIZONTAL,
            length=220,
            command=lambda _evt=None: self._on_smooth_change(),
        )
        sm_scale.grid(row=row, column=1, sticky="ew", padx=8)

        # Hero settings
        row += 1
        hero_frame = ttk.LabelFrame(parent, text="Hero Ability Locks")
        hero_frame.grid(row=row, column=0, sticky="ew", pady=(10, 0))

        hero_row = 0
        ttk.Label(hero_frame, text="Hero").grid(row=hero_row, column=0, sticky="w")
        ttk.Label(hero_frame, text="Key 1").grid(row=hero_row, column=1, sticky="w")
        ttk.Label(hero_frame, text="Key 2").grid(row=hero_row, column=2, sticky="w")
        hero_row += 1

        self.grey_enabled = tk.BooleanVar(value=self.settings.grey_talon_lock_enabled)
        ttk.Checkbutton(
            hero_frame, text="Grey Talon", variable=self.grey_enabled
        ).grid(row=hero_row, column=0, sticky="w")
        self.grey_key = tk.StringVar(value=chr(self.settings.grey_talon_key))
        ttk.Entry(hero_frame, textvariable=self.grey_key, width=4).grid(
            row=hero_row, column=1, sticky="w"
        )
        hero_row += 1

        self.yamato_enabled = tk.BooleanVar(value=self.settings.yamato_lock_enabled)
        ttk.Checkbutton(hero_frame, text="Yamato", variable=self.yamato_enabled).grid(
            row=hero_row, column=0, sticky="w"
        )
        self.yamato_key = tk.StringVar(value=chr(self.settings.yamato_key))
        ttk.Entry(hero_frame, textvariable=self.yamato_key, width=4).grid(
            row=hero_row, column=1, sticky="w"
        )
        hero_row += 1

        self.vindicta_enabled = tk.BooleanVar(
            value=self.settings.vindicta_lock_enabled
        )
        ttk.Checkbutton(
            hero_frame, text="Vindicta", variable=self.vindicta_enabled
        ).grid(row=hero_row, column=0, sticky="w")
        self.vindicta_key = tk.StringVar(value=chr(self.settings.vindicta_key))
        ttk.Entry(hero_frame, textvariable=self.vindicta_key, width=4).grid(
            row=hero_row, column=1, sticky="w"
        )
        hero_row += 1

        self.paradox_enabled = tk.BooleanVar(value=self.settings.paradox_shortcut_enabled)
        ttk.Checkbutton(hero_frame, text="Paradox", variable=self.paradox_enabled).grid(
            row=hero_row, column=0, sticky="w"
        )
        self.paradox_r_key = tk.StringVar(value=chr(self.settings.paradox_r_key))
        ttk.Entry(hero_frame, textvariable=self.paradox_r_key, width=4).grid(
            row=hero_row, column=1, sticky="w"
        )
        self.paradox_e_key = tk.StringVar(value=chr(self.settings.paradox_e_key))
        ttk.Entry(hero_frame, textvariable=self.paradox_e_key, width=4).grid(
            row=hero_row, column=2, sticky="w"
        )

    def _build_status_frame(self, parent: ttk.Frame) -> None:
        """Deprecated: status is now in the status bar."""
        # Kept for backward compatibility if referenced elsewhere.
        pass

    def _build_log_frame(self, parent: ttk.Frame) -> None:
        """Build the log tab with a dark console-like view."""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        self.log_text = scrolledtext.ScrolledText(
            parent, width=50, height=20, state="disabled"
        )
        self.log_text.configure(
            background="#111318",
            foreground="#dcdcdc",
            insertbackground="#ffffff",
            borderwidth=0,
            relief="flat",
            padx=8,
            pady=8,
        )
        self.log_text.grid(row=0, column=0, sticky="nsew")
        ttk.Button(parent, text="Clear Log", command=self.clear_log).grid(
            row=1, column=0, sticky="e", pady=(8, 0)
        )

    def _add_build_label(self, parent: ttk.Frame) -> None:
        """Deprecated: build label is shown in status bar."""
        # Preserved to avoid accidental removal; no-op now.
        pass
    def _process_log_queue(self) -> None:
        """Process log messages from queue and display them."""
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
        """Update the status label in the status bar."""
        self.status_label.config(text=f"Status: {status}", foreground=color)
    
    def _update_button_states(self) -> None:
        """Update the single toggle button to reflect running state."""
        if not self.is_running:
            self.toggle_button.config(
                text="Start",
                style="Accent.TButton",
                state="normal",
            )
        else:
            self.toggle_button.config(
                text="Stop",
                style="Danger.TButton",
                state="normal",
            )

    def toggle_run(self) -> None:
        """Toggle between starting and stopping the aimbot."""
        if self.is_running:
            self.stop()
        else:
            self.start()

    def _update_headshot_warning(self) -> None:
        """Show or hide the headshot probability warning."""
        try:
            value = float(self.headshot_var.get())
        except tk.TclError:
            value = 0.0
        if value > 0.35:
            self.headshot_warning.grid()
        else:
            self.headshot_warning.grid_remove()

    def _on_headshot_change(self) -> None:
        """Update headshot percentage label and warning visibility."""
        try:
            val = max(0.0, min(1.0, float(self.headshot_var.get())))
        except tk.TclError:
            val = 0.0
        self.headshot_percent.config(text=f"{int(val * 100)}%")
        self._update_headshot_warning()

    def _on_smooth_change(self) -> None:
        """Update the smooth speed display label."""
        try:
            val = float(self.smooth_var.get())
        except tk.TclError:
            val = 0.0
        self.smooth_value_label.config(text=f"{val:.1f}")

    def _apply_widget_values(self) -> None:
        """Update :attr:`settings` from widget values."""
        # Clamp values to expected ranges
        try:
            self.settings.headshot_probability = max(
                0.0, min(1.0, float(self.headshot_var.get()))
            )
        except Exception:
            self.settings.headshot_probability = 0.25
        self.settings.target_select_type = self.target_var.get()
        try:
            self.settings.smooth_speed = max(0.1, float(self.smooth_var.get()))
        except Exception:
            self.settings.smooth_speed = 5.0
        self.settings.headshot_on_acquire = self.acquire_headshot_var.get()

        self.settings.grey_talon_lock_enabled = self.grey_enabled.get()
        if self.grey_key.get():
            self.settings.grey_talon_key = ord(self.grey_key.get().upper()[0])

        self.settings.yamato_lock_enabled = self.yamato_enabled.get()
        if self.yamato_key.get():
            self.settings.yamato_key = ord(self.yamato_key.get().upper()[0])

        self.settings.vindicta_lock_enabled = self.vindicta_enabled.get()
        if self.vindicta_key.get():
            self.settings.vindicta_key = ord(self.vindicta_key.get().upper()[0])

        self.settings.paradox_shortcut_enabled = self.paradox_enabled.get()
        if self.paradox_r_key.get():
            self.settings.paradox_r_key = ord(self.paradox_r_key.get().upper()[0])
        if self.paradox_e_key.get():
            self.settings.paradox_e_key = ord(self.paradox_e_key.get().upper()[0])

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
            self._update_status("Starting...", "#60a5fa")
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
                self._update_status("Running", "#10b981"),
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
            self._update_status("Paused", "#f59e0b")
            self.log_text.config(state='normal')
            self.log_text.insert(tk.END, "Aimbot paused.\n")
            self.log_text.see(tk.END)
            self.log_text.config(state='disabled')
        else:
            self.bot.resume()
            self._update_status("Running", "#10b981")
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
