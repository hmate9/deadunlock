import os
import shutil
import subprocess
import sys
import tempfile
from typing import Optional

import requests

REPO_API_COMMIT = "https://api.github.com/repos/hmate9/deadunlock/commits/main"
REPO_API_RELEASES = "https://api.github.com/repos/hmate9/deadunlock/releases/latest"


def _is_binary_release() -> bool:
    """Return True if running as a compiled binary (PyInstaller)."""
    return getattr(sys, 'frozen', False)


def _local_commit() -> Optional[str]:
    """Return the SHA of the current local commit or ``None`` on error."""
    try:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        out = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root)
        return out.decode().strip()
    except Exception:
        return None


def _remote_commit() -> Optional[str]:
    """Return the SHA of the latest commit on GitHub or ``None`` on error."""
    try:
        resp = requests.get(REPO_API_COMMIT, timeout=5)
        if resp.status_code == 200:
            return resp.json()["sha"]
    except Exception:
        pass
    return None


def _get_latest_release() -> Optional[dict]:
    """Return the latest release info from GitHub or ``None`` on error."""
    try:
        resp = requests.get(REPO_API_RELEASES, timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return None


def _get_current_version() -> Optional[str]:
    """Return current version string (commit SHA from tag) or None."""
    if _is_binary_release():
        # For binary releases, try to read version from bundled version.txt
        try:
            # PyInstaller bundles files in sys._MEIPASS
            if hasattr(sys, '_MEIPASS'):
                version_file = os.path.join(sys._MEIPASS, 'version.txt')
            else:
                # Fallback for development
                version_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'version.txt')
            
            if os.path.exists(version_file):
                with open(version_file, 'r', encoding='utf-8') as f:
                    return f.read().strip()
        except Exception:
            pass
        return None
    else:
        return _local_commit()


def _download_and_replace_executable(download_url: str, current_exe_path: str) -> bool:
    """Download new executable and replace current one. Return True on success."""
    try:
        print("Downloading update...")
        
        # Download to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.exe') as temp_file:
            temp_path = temp_file.name
            
        resp = requests.get(download_url, stream=True, timeout=30)
        resp.raise_for_status()
        
        with open(temp_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        
        print("Download complete. Replacing executable...")
        
        # Create backup of current executable
        backup_path = current_exe_path + ".backup"
        if os.path.exists(backup_path):
            os.remove(backup_path)
        shutil.copy2(current_exe_path, backup_path)
        
        # Replace current executable
        shutil.move(temp_path, current_exe_path)
        
        print("Update complete!")
        return True
        
    except Exception as e:
        print(f"Failed to download/install update: {e}")
        # Clean up temp file if it exists
        if 'temp_path' in locals() and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
        # Try to restore backup if replacement failed
        backup_path = current_exe_path + ".backup"
        if os.path.exists(backup_path) and not os.path.exists(current_exe_path):
            try:
                shutil.move(backup_path, current_exe_path)
                print("Restored backup executable.")
            except Exception:
                pass
        return False


def update_available() -> bool:
    """Return ``True`` if a newer commit/release is available on GitHub."""
    if _is_binary_release():
        # For binary releases, check if a newer release exists
        latest_release = _get_latest_release()
        if not latest_release:
            return False
        
        # Extract commit SHA from tag name (format: build-{commit_sha})
        tag_name = latest_release.get("tag_name", "")
        if not tag_name.startswith("build-"):
            return False
            
        latest_commit = tag_name[6:]  # Remove "build-" prefix
        current_commit = _get_current_version()
        
        # If we can't get current version, assume update is available
        # if the release has assets (executable)
        if not current_commit:
            assets = latest_release.get("assets", [])
            return any(asset.get("name") == "aimbot_gui.exe" for asset in assets)
            
        return current_commit != latest_commit
    else:
        # For source installations, use the existing logic
        local = _local_commit()
        remote = _remote_commit()
        return bool(local and remote and local != remote)


def ensure_up_to_date() -> None:
    """Update to the latest version if outdated and exit."""
    if not update_available():
        return
        
    if _is_binary_release():
        print("Your DeadUnlock binary is out of date. Downloading update...")
        
        # Get latest release info
        latest_release = _get_latest_release()
        if not latest_release:
            print("Failed to fetch latest release information.")
            input("Press Enter to continue...")
            return
            
        # Find the executable asset
        assets = latest_release.get("assets", [])
        exe_asset = None
        for asset in assets:
            if asset.get("name") == "aimbot_gui.exe":
                exe_asset = asset
                break
                
        if not exe_asset:
            print("No executable found in latest release.")
            input("Press Enter to continue...")
            return
            
        download_url = exe_asset.get("browser_download_url")
        if not download_url:
            print("Failed to get download URL.")
            input("Press Enter to continue...")
            return
            
        # Get current executable path
        current_exe_path = sys.executable
        
        # Download and replace
        if _download_and_replace_executable(download_url, current_exe_path):
            print("Update complete. Restarting...")
            # Restart the application
            try:
                subprocess.Popen([current_exe_path])
                sys.exit(0)
            except Exception as e:
                print(f"Failed to restart application: {e}")
                input("Please restart the application manually. Press Enter to exit...")
                sys.exit(0)
        else:
            print("Update failed. Continuing with current version.")
            input("Press Enter to continue...")
    else:
        # For source installations, use git pull
        print("Your DeadUnlock copy is out of date. Pulling updates...")
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        try:
            subprocess.check_call(["git", "pull"], cwd=root)
        except Exception as exc:
            print(f"Failed to update automatically: {exc}")
            print("Please run 'git pull' manually.")
            input("Press Enter to exit...")
            sys.exit(1)
        print("Update complete. Please restart the program.")
        input("Press Enter to exit...")
        sys.exit(0)
