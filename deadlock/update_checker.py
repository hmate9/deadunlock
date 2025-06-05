import os
import subprocess
import sys
from typing import Optional, Callable

import requests
from .binary_updater import download_and_replace_executable, cleanup_old_update_files

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
    except requests.exceptions.RequestException as e:
        print(f"Network error while fetching release info: {e}")
    except Exception as e:
        print(f"Error fetching release info: {e}")
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


def _pause(msg: str = "Press Enter to continue...") -> None:
    """Pause for user acknowledgement when running with a console."""
    if not _is_binary_release():
        try:
            input(msg)
        except Exception:
            pass


def ensure_up_to_date(progress_callback: Optional[Callable[[str], None]] = None, force: bool = False, cancel_check: Optional[Callable[[], bool]] = None) -> None:
    """Update to the latest version if outdated and exit."""
    if progress_callback:
        if force:
            progress_callback("Force update requested - downloading latest version...")
        else:
            progress_callback("Checking if update is needed...")
    
    # Check for cancellation early
    if cancel_check and cancel_check():
        if progress_callback:
            progress_callback("Update cancelled")
        return
        
    if not force and not update_available():
        if progress_callback:
            progress_callback("No update needed - you're running the latest version")
        return

    if _is_binary_release():
        if progress_callback:
            progress_callback("Binary release detected - preparing automatic update")
        print("Your DeadUnlock binary is out of date. Downloading update...")
        
        # Check for cancellation before connecting
        if cancel_check and cancel_check():
            if progress_callback:
                progress_callback("Update cancelled")
            return
        
        if progress_callback:
            progress_callback("Connecting to GitHub API...")
        
        # Get latest release info
        try:
            latest_release = _get_latest_release()
        except Exception as e:
            error_msg = f"Failed to connect to GitHub API: {str(e)}"
            if progress_callback:
                progress_callback(error_msg)
            print(error_msg)
            _pause()
            return
            
        if not latest_release:
            error_msg = "Failed to fetch latest release information from GitHub"
            if progress_callback:
                progress_callback(error_msg)
            print(error_msg)
            _pause()
            return
        
        # Check for cancellation after getting release info
        if cancel_check and cancel_check():
            if progress_callback:
                progress_callback("Update cancelled")
            return
            
        if progress_callback:
            release_name = latest_release.get("name", "Unknown")
            progress_callback(f"Found release: {release_name}")
            if force:
                progress_callback("Force update mode: will download and install regardless of current version")
            progress_callback("Analyzing release assets...")
        
        # Find the executable asset
        assets = latest_release.get("assets", [])
        if progress_callback:
            progress_callback(f"Found {len(assets)} asset(s) in release")
            
        exe_asset = None
        for asset in assets:
            if asset.get("name") == "aimbot_gui.exe":
                exe_asset = asset
                break
                
        if not exe_asset:
            error_msg = "No executable found in latest release."
            if progress_callback:
                asset_names = [asset.get("name", "unknown") for asset in assets]
                progress_callback(f"Available assets: {', '.join(asset_names) if asset_names else 'none'}")
                progress_callback(error_msg)
            print(error_msg)
            _pause()
            return
            
        if progress_callback:
            file_size = exe_asset.get("size", 0)
            if file_size > 0:
                progress_callback(f"Found executable: {exe_asset.get('name')} ({file_size // 1024 // 1024:.1f} MB)")
            else:
                progress_callback(f"Found executable: {exe_asset.get('name')}")
            
        download_url = exe_asset.get("browser_download_url")
        if not download_url:
            error_msg = "Failed to get download URL from release asset"
            if progress_callback:
                progress_callback(error_msg)
            print(error_msg)
            _pause()
            return
            
        if progress_callback:
            progress_callback("Download URL obtained successfully")
            progress_callback("Validating current executable path...")
        
        # Get current executable path
        current_exe_path = sys.executable
        if progress_callback:
            progress_callback(f"Current executable: {current_exe_path}")
            
            # Show version comparison for force updates
            if force:
                current_version = _get_current_version()
                tag_name = latest_release.get("tag_name", "")
                if tag_name.startswith("build-"):
                    latest_commit = tag_name[6:]  # Remove "build-" prefix
                    if current_version and current_version == latest_commit:
                        progress_callback("Note: You already have the latest version, but proceeding with forced update")
                    elif current_version:
                        progress_callback(f"Force updating from {current_version[:7]} to {latest_commit[:7]}")
                    else:
                        progress_callback("Force updating to latest version (current version unknown)")
                        
        # Download and replace
        cleanup_old_update_files(current_exe_path, progress_callback)
        
        if download_and_replace_executable(download_url, current_exe_path, progress_callback, cancel_check):
            if progress_callback:
                progress_callback("Update prepared successfully!")
                progress_callback("Close the application to complete the update automatically.")
            print("Update prepared successfully! Close the application to complete the update.")
            return
        else:
            error_msg = "Update preparation failed - continuing with current version"
            if progress_callback:
                progress_callback(error_msg)
            print(error_msg)
            _pause()
    else:
        # For source installations, use git pull
        if progress_callback:
            progress_callback("Source installation detected - using git pull")
        print("Your DeadUnlock copy is out of date. Pulling updates...")
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        if progress_callback:
            progress_callback(f"Repository path: {root}")
            progress_callback("Running git pull...")
            
        try:
            subprocess.check_call(["git", "pull"], cwd=root)
        except Exception as exc:
            error_msg = f"Git pull failed: {exc}"
            if progress_callback:
                progress_callback(error_msg)
            print(error_msg)
            print("Please run 'git pull' manually.")
            _pause("Press Enter to exit...")
            sys.exit(1)
            
        if progress_callback:
            progress_callback("Git pull completed successfully")
            progress_callback("Update complete. Please restart the program.")
        print("Update complete. Please restart the program.")
        _pause("Press Enter to continue...")
        return
