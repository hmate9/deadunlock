"""Helpers for downloading and installing binary updates."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
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
    
    # Also clean up any leftover helper scripts
    import glob
    exe_dir = os.path.dirname(exe_path)
    helper_pattern = os.path.join(exe_dir, "tmp*.py")
    patterns.extend(glob.glob(helper_pattern))
    
    for pattern in patterns:
        if "*" in pattern:
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


def _create_update_helper(current_exe: str, new_exe: str, backup_path: str) -> str:
    """Create a simple update helper script that waits for the main process to exit."""
    helper_code = f'''import os
import shutil
import time
import sys

current_exe = r"{current_exe}"
new_exe = r"{new_exe}"
backup_path = r"{backup_path}"

# Wait a moment for the main process to fully exit
time.sleep(2)

try:
    # Replace the executable
    shutil.copy2(new_exe, current_exe)
    print("Update completed successfully!")
    
    # Clean up temporary files
    if os.path.exists(new_exe):
        os.remove(new_exe)
    if os.path.exists(backup_path):
        os.remove(backup_path)
        
except Exception as e:
    print(f"Update failed: {{e}}")
    # Try to restore backup
    try:
        if os.path.exists(backup_path):
            shutil.copy2(backup_path, current_exe)
            print("Restored backup")
    except Exception:
        print("Failed to restore backup - manual intervention required")

# Clean up this helper script
try:
    os.remove(__file__)
except Exception:
    pass
'''
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
        f.write(helper_code)
        return f.name


def download_and_replace_executable(download_url: str, current_exe_path: str, progress_callback: Callable[[str], None] | None = None, cancel_check: Callable[[], bool] | None = None) -> bool:
    """Download new executable and create helper to replace it after exit."""
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
        progress_callback("Preparing update helper...")
    
    try:
        # Create update helper script
        helper_path = _create_update_helper(current_exe_path, temp_path, backup_path)
        
        if progress_callback:
            progress_callback("Update ready! Close the application to complete the update.")
            progress_callback("The update will be applied automatically when you exit.")
        
        # Launch the helper script in the background to run after exit
        if sys.platform == 'win32':
            subprocess.Popen([sys.executable, helper_path], 
                           creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            subprocess.Popen([sys.executable, helper_path])
        
        return True
        
    except Exception as e:
        if progress_callback:
            progress_callback(f"Failed to prepare update: {e}")
        
        # Clean up on failure
        if os.path.exists(temp_path):
            os.remove(temp_path)
        if os.path.exists(backup_path):
            os.remove(backup_path)
        return False

