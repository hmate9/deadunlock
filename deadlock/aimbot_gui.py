from __future__ import annotations

"""Simple Tkinter GUI for configuring and running the aimbot."""

import json
import logging
import os
import queue
import sys
import threading
import time
import tkinter as tk
from dataclasses import asdict
from tkinter import messagebox, scrolledtext, ttk

from .aimbot import Aimbot, AimbotSettings
from .memory import DeadlockMemory
from .update_checker import ensure_up_to_date, update_available, _get_current_version

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


def _get_build_sha() -> str:
    """Return the short commit SHA for the current build."""
    try:
        sha = _get_current_version()
        if sha:
            return sha[:7]
    except Exception:
        pass
    return "unknown"


class UpdateProgressDialog:
    """Progress dialog for showing update status."""
    
    def __init__(self, parent: tk.Tk):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Updating DeadUnlock")
        self.dialog.geometry("600x400")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center the dialog
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (600 // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (400 // 2)
        self.dialog.geometry(f"600x400+{x}+{y}")
        
        # Set up the UI
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill="both", expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="Updating DeadUnlock", font=("Arial", 16, "bold"))
        title_label.pack(pady=(0, 15))
        
        # Progress frame
        progress_frame = ttk.Frame(main_frame)
        progress_frame.pack(fill="x", pady=(0, 10))
        
        # Progress bar (indeterminate initially)
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, mode='indeterminate', length=500)
        self.progress_bar.pack(pady=(0, 5))
        self.progress_bar.start()
        
        # Progress percentage label
        self.progress_label = ttk.Label(progress_frame, text="", font=("Arial", 9))
        self.progress_label.pack()
        
        # Status text
        self.status_label = ttk.Label(main_frame, text="Initializing update...", wraplength=550, font=("Arial", 11))
        self.status_label.pack(pady=(0, 15))
        
        # Detailed log area
        log_frame = ttk.LabelFrame(main_frame, text="Progress Details", padding=10)
        log_frame.pack(fill="both", expand=True, pady=(10, 0))
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=12, width=70, state="disabled")
        self.log_text.configure(background="#f8f8f8", foreground="#333333", font=("Consolas", 9))
        self.log_text.pack(fill="both", expand=True)
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill="x", pady=(15, 0))
        
        # Close button (initially disabled)
        self.close_button = ttk.Button(button_frame, text="Close", command=self.close_dialog, state="disabled")
        self.close_button.pack(side="right")
        
        # Cancel button (for during update)
        self.cancel_button = ttk.Button(button_frame, text="Cancel", command=self.cancel_update, state="disabled")
        self.cancel_button.pack(side="right", padx=(0, 10))
        
        self.dialog.protocol("WM_DELETE_WINDOW", self.on_window_close)
        self.closed = False
        self.cancelled = False
        
    def update_status(self, message: str, is_error: bool = False):
        """Update the status label and add to log."""
        if self.closed:
            return
            
        self.status_label.config(text=message)
        
        # Add to log with timestamp
        self.log_text.config(state='normal')
        timestamp = time.strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        
        # Color code different types of messages
        if is_error:
            self.log_text.insert(tk.END, log_entry)
            # Highlight the last line in red
            self.log_text.tag_add("error", "end-2c linestart", "end-2c")
            self.log_text.tag_config("error", foreground="#cc0000")
        elif "complete" in message.lower() or "success" in message.lower():
            self.log_text.insert(tk.END, log_entry)
            # Highlight in green
            self.log_text.tag_add("success", "end-2c linestart", "end-2c")
            self.log_text.tag_config("success", foreground="#008000")
        elif "warning" in message.lower():
            self.log_text.insert(tk.END, log_entry)
            # Highlight in orange
            self.log_text.tag_add("warning", "end-2c linestart", "end-2c")
            self.log_text.tag_config("warning", foreground="#ff8800")
        else:
            self.log_text.insert(tk.END, log_entry)
            
        self.log_text.see(tk.END)
        self.log_text.config(state='disabled')
        
        # Handle progress bar based on message content
        if "%" in message and "Downloading" in message:
            try:
                # Extract percentage and switch to determinate mode
                import re
                match = re.search(r'(\d+\.?\d*)%', message)
                if match:
                    percent = float(match.group(1))
                    if self.progress_bar['mode'] != 'determinate':
                        self.progress_bar.stop()
                        self.progress_bar.config(mode='determinate', maximum=100)
                    self.progress_bar['value'] = percent
                    self.progress_label.config(text=f"{percent:.1f}%")
            except:
                pass
        elif is_error:
            self.progress_bar.stop()
            self.progress_bar.config(mode='determinate', maximum=100, value=0)
            self.progress_label.config(text="Failed")
            self.close_button.config(state="normal")
            self.cancel_button.config(state="disabled")
        elif "complete" in message.lower() or "launched" in message.lower():
            self.progress_bar.stop()
            self.progress_bar.config(mode='determinate', maximum=100, value=100)
            self.progress_label.config(text="Complete")
            self.cancel_button.config(state="disabled")
            if "restart" in message.lower():
                self.status_label.config(text="Update complete! Application will restart shortly...")
                self.dialog.after(3000, self.close_dialog)  # Auto-close after 3 seconds
            else:
                self.close_button.config(state="normal")
        elif "preparing" in message.lower() or "creating" in message.lower() or "verifying" in message.lower():
            # Switch back to indeterminate for non-download tasks
            if self.progress_bar['mode'] == 'determinate' and self.progress_bar['value'] < 100:
                pass  # Keep determinate mode if we're in middle of download
            elif "download" not in message.lower():
                self.progress_bar.config(mode='indeterminate')
                self.progress_label.config(text="")
                if not self.progress_bar.cget('mode') == 'indeterminate':
                    self.progress_bar.start()
        
        self.dialog.update()
        
    def set_progress(self, value: float, maximum: float = 100.0):
        """Set progress bar value."""
        if self.closed:
            return
        self.progress_bar.stop()
        self.progress_bar.config(mode='determinate', maximum=maximum, value=value)
        self.progress_label.config(text=f"{(value/maximum)*100:.1f}%")
        
    def enable_close(self):
        """Enable the close button."""
        self.close_button.config(state="normal")
        self.cancel_button.config(state="disabled")
        
    def cancel_update(self):
        """Cancel the update process."""
        self.cancelled = True
        self.cancel_button.config(state="disabled")
        self.update_status("Update cancelled by user", is_error=True)
        
    def close_dialog(self):
        """Close the dialog."""
        self.closed = True
        self.dialog.destroy()
        
    def on_window_close(self):
        """Handle window close event."""
        # Don't allow closing during active update unless cancel is available
        if self.close_button['state'] == 'normal' or self.cancel_button['state'] == 'normal':
            if self.cancel_button['state'] == 'normal':
                self.cancel_update()
            self.close_dialog()


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

        self._build_widgets()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # Start log processing
        self._process_log_queue()

        self._notify_if_outdated()

    def _notify_if_outdated(self) -> None:
        """Show a warning dialog if the local repo is outdated."""
        if update_available():
            # Check if we're running as a binary
            if getattr(sys, 'frozen', False):
                # For binary releases, the update will be automatic
                result = messagebox.askyesno(
                    "Update available",
                    "A newer DeadUnlock version is available. Would you like to update now?\n\n"
                    "The application will download and install the update automatically.\n"
                    "You'll see detailed progress during the update process.",
                )
                if result:
                    self._perform_update_with_progress()
            else:
                # For source installations, show git pull message
                messagebox.showwarning(
                    "Update available",
                    "A newer DeadUnlock version is available. Please run 'git pull'.",
                )

    def _perform_update_with_progress(self, force: bool = False):
        """Perform update with detailed progress dialog."""
        progress_dialog = UpdateProgressDialog(self.root)
        
        def progress_callback(message: str):
            """Callback to update progress dialog."""
            progress_dialog.update_status(message, is_error="failed" in message.lower() or "error" in message.lower())
        
        def update_thread():
            """Run update in separate thread."""
            try:
                # Add initial version info
                current_version = _get_current_version()
                if current_version:
                    progress_callback(f"Current version: {current_version[:7]}")
                else:
                    progress_callback("Current version: Unknown")
                
                # Get latest release info for version comparison
                from .update_checker import _get_latest_release
                latest_release = _get_latest_release()
                if latest_release:
                    tag_name = latest_release.get("tag_name", "")
                    if tag_name.startswith("build-"):
                        latest_commit = tag_name[6:][:7]  # Get first 7 chars of commit after "build-"
                        progress_callback(f"Latest version: {latest_commit}")
                        
                        # Show release info if available
                        published_at = latest_release.get("published_at", "")
                        if published_at:
                            import datetime
                            try:
                                # Parse ISO date and format it nicely
                                dt = datetime.datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                                formatted_date = dt.strftime("%Y-%m-%d %H:%M")
                                progress_callback(f"Release date: {formatted_date}")
                            except:
                                pass
                
                # Start the actual update process
                ensure_up_to_date(progress_callback, force=force)
            except SystemExit:
                # Expected when update completes successfully
                pass
            except Exception as e:
                progress_callback(f"Update failed: {str(e)}")
                progress_dialog.enable_close()
        
        # Start update in background thread
        threading.Thread(target=update_thread, daemon=True).start()

    def _check_for_updates(self) -> None:
        """Manually check for updates and offer to update if available."""
        try:
            if update_available():
                # Check if we're running as a binary
                if getattr(sys, 'frozen', False):
                    # For binary releases, offer automatic update
                    result = messagebox.askyesno(
                        "Update Available",
                        "A newer DeadUnlock version is available. Would you like to update now?\n\n"
                        "The application will download and install the update automatically.\n"
                        "You'll see detailed progress during the update process.",
                    )
                    if result:
                        self._perform_update_with_progress()
                else:
                    # For source installations, show git pull message
                    messagebox.showinfo(
                        "Update Available",
                        "A newer DeadUnlock version is available. Please run 'git pull' to update.",
                    )
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

    def _force_update(self) -> None:
        """Download and install the latest update regardless of version."""
        try:
            result = messagebox.askyesno(
                "Force Update",
                "Download and install the latest version now?\n\n"
                "This will restart the application and show detailed progress.",
            )
            if result:
                self._perform_update_with_progress(force=True)
        except Exception as exc:
            messagebox.showerror("Force Update Failed", f"Failed to update: {exc}")

    def _build_widgets(self) -> None:
        # apply a slightly more modern theme if available
        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        default_font = ("Segoe UI", 10)
        self.root.option_add("*Font", default_font)
        style.configure("TButton", padding=6)
        style.configure("TLabel", padding=(2, 2))
        style.configure("TCheckbutton", padding=(2, 2))

        # Create menu bar
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="Check for Updates", command=self._check_for_updates)
        help_menu.add_command(label="Force Update", command=self._force_update)
        
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

        # Hero ability lock keybinds
        hero_frame = ttk.LabelFrame(settings_frame, text="Hero Ability Locks", padding=5)
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
        
        self.log_text = scrolledtext.ScrolledText(log_frame, width=50, height=20, state="disabled")
        self.log_text.configure(background="#1e1e1e", foreground="#dcdcdc", insertbackground="#ffffff")
        self.log_text.pack(fill="both", expand=True)

        # Clear log button
        ttk.Button(log_frame, text="Clear Log", command=self.clear_log).pack(pady=(5, 0))

        # Build SHA label (small, bottom-right)
        sha = _get_build_sha()
        self.build_label = ttk.Label(main_frame, text=f"build {sha}", font=("TkDefaultFont", 8))
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
                        "A newer version is available. Update now before starting?",
                    )
                    if result:
                        progress_dialog = UpdateProgressDialog(self.root)
                        
                        def progress_callback(message: str):
                            progress_dialog.update_status(message, is_error="failed" in message.lower())
                        
                        def update_thread():
                            try:
                                ensure_up_to_date(progress_callback)
                            except SystemExit:
                                pass
                            except Exception as e:
                                progress_callback(f"Update failed: {str(e)}")
                                progress_dialog.enable_close()
                        
                        threading.Thread(target=update_thread, daemon=True).start()
                        return  # Don't start aimbot if updating
            
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
