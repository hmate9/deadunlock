"""Helpers for downloading and installing binary updates."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from typing import Callable, Optional

import requests


def _download_file(url: str, cancel_check: Callable[[], bool] | None, progress_callback: Callable[[str], None] | None) -> str:
    """Download ``url`` to a temporary file and return the path."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".exe") as temp_file:
        temp_path = temp_file.name

    if progress_callback:
        progress_callback("Connecting to download server...")

    if cancel_check and cancel_check():
        if progress_callback:
            progress_callback("Download cancelled")
        return ""

    resp = requests.get(url, stream=True, timeout=30)
    resp.raise_for_status()

    total_size = int(resp.headers.get("content-length", 0))
    downloaded = 0
    if progress_callback:
        if total_size > 0:
            progress_callback(f"Starting download ({total_size // 1024 // 1024:.1f} MB)...")
        else:
            progress_callback("Starting download (size unknown)...")

    with open(temp_path, "wb") as fh:
        for chunk in resp.iter_content(chunk_size=8192):
            if cancel_check and cancel_check():
                if progress_callback:
                    progress_callback("Download cancelled")
                os.remove(temp_path)
                return ""
            fh.write(chunk)
            downloaded += len(chunk)
            if progress_callback and total_size > 0:
                percent = (downloaded / total_size) * 100
                progress_callback(f"Downloading update... {percent:.1f}%")
    return temp_path


def _create_backup(exe_path: str, progress_callback: Callable[[str], None] | None) -> str:
    """Create a backup of ``exe_path`` and return backup path."""
    backup_path = exe_path + ".backup"
    if os.path.exists(backup_path):
        os.remove(backup_path)
    shutil.copy2(exe_path, backup_path)
    if progress_callback:
        size = os.path.getsize(backup_path)
        progress_callback(f"Backup created ({size // 1024 // 1024:.1f} MB)")
    return backup_path


def _write_helper_script(current_exe: str, new_exe: str, backup: str) -> str:
    """Write the update helper script and return its path."""
    helper_code = f'''import os, shutil, subprocess, sys, time, psutil
OLD=r"{current_exe}"
NEW=r"{new_exe}"
BACKUP=r"{backup}"
for _ in range(60):
    try:
        if not psutil.pid_exists({os.getpid()}):
            break
    except Exception:
        pass
    time.sleep(1)
shutil.copy2(NEW, OLD)
subprocess.Popen([OLD], cwd=os.path.dirname(OLD), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
'''
    with tempfile.NamedTemporaryFile(delete=False, suffix=".py", mode="w", encoding="utf-8") as helper:
        helper.write(helper_code)
        return helper.name


def cleanup_old_update_files(exe_path: str, progress_callback: Callable[[str], None] | None = None) -> None:
    """Remove backup and temp files from previous updates."""
    patterns = [exe_path + ".backup", exe_path + ".old_*", exe_path + ".test_write"]
    removed = 0
    for pattern in patterns:
        if "*" in pattern:
            import glob
            files = glob.glob(pattern)
        else:
            files = [pattern]
        for file_path in files:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    removed += 1
                except Exception:
                    pass
    if removed and progress_callback:
        progress_callback(f"Cleaned up {removed} old update files")


def download_and_replace_executable(download_url: str, current_exe_path: str, progress_callback: Callable[[str], None] | None = None, cancel_check: Callable[[], bool] | None = None) -> bool:
    """Download new executable and start helper for replacement."""
    if progress_callback:
        progress_callback("Initializing download...")
    cleanup_old_update_files(current_exe_path, progress_callback)

    temp_path = _download_file(download_url, cancel_check, progress_callback)
    if not temp_path:
        return False

    backup = _create_backup(current_exe_path, progress_callback)
    helper = _write_helper_script(current_exe_path, temp_path, backup)
    if progress_callback:
        progress_callback("Launching update helper...")
    subprocess.Popen([sys.executable, helper])
    return True

