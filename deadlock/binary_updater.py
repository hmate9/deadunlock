"""Helpers for downloading and installing binary updates."""

from __future__ import annotations

import os
import shutil
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
    """Download new executable and replace the current one."""
    if progress_callback:
        progress_callback("Initializing download...")
    cleanup_old_update_files(current_exe_path, progress_callback)

    # Download the new executable
    temp_path = _download_file(download_url, cancel_check, progress_callback)
    if not temp_path:
        return False

    if cancel_check and cancel_check():
        if progress_callback:
            progress_callback("Update cancelled")
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return False

    # Create backup of current executable
    backup_path = _create_backup(current_exe_path, progress_callback)
    
    if progress_callback:
        progress_callback("Replacing executable...")
    
    try:
        # Replace the current executable with the new one
        shutil.copy2(temp_path, current_exe_path)
        if progress_callback:
            progress_callback("Update completed successfully! Please restart the application.")
        
        # Clean up temporary file
        os.remove(temp_path)
        return True
        
    except Exception as e:
        if progress_callback:
            progress_callback(f"Failed to replace executable: {e}")
        # Restore backup if replacement failed
        try:
            if os.path.exists(backup_path):
                shutil.copy2(backup_path, current_exe_path)
                if progress_callback:
                    progress_callback("Restored backup due to update failure")
        except Exception:
            if progress_callback:
                progress_callback("Failed to restore backup - manual intervention may be required")
        
        # Clean up temporary file
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return False

