import os
import shutil
import subprocess
import sys
import tempfile
from typing import Optional, Callable

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


def _download_and_replace_executable(download_url: str, current_exe_path: str, progress_callback: Optional[Callable[[str], None]] = None, cancel_check: Optional[Callable[[], bool]] = None) -> bool:
    """Download a new executable and schedule replacement after exit."""
    try:
        if progress_callback:
            progress_callback("Initializing download...")
        print("Downloading update...")

        # Check for cancellation
        if cancel_check and cancel_check():
            if progress_callback:
                progress_callback("Download cancelled")
            return False

        # Download to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".exe") as temp_file:
            temp_path = temp_file.name

        if progress_callback:
            progress_callback("Connecting to download server...")
        
        # Check for cancellation
        if cancel_check and cancel_check():
            if progress_callback:
                progress_callback("Download cancelled")
            return False
        
        try:
            resp = requests.get(download_url, stream=True, timeout=30)
            resp.raise_for_status()
        except requests.exceptions.Timeout:
            raise Exception("Download request timed out")
        except requests.exceptions.ConnectionError:
            raise Exception("Failed to connect to download server")
        except requests.exceptions.HTTPError as e:
            raise Exception(f"HTTP error {resp.status_code}: {e}")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Network error: {e}")
        
        total_size = int(resp.headers.get('content-length', 0))
        downloaded = 0

        if progress_callback:
            if total_size > 0:
                progress_callback(f"Starting download ({total_size // 1024 // 1024:.1f} MB)...")
            else:
                progress_callback("Starting download (size unknown)...")

        with open(temp_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                # Check for cancellation during download
                if cancel_check and cancel_check():
                    if progress_callback:
                        progress_callback("Download cancelled")
                    # Clean up partial download
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                    return False
                    
                f.write(chunk)
                downloaded += len(chunk)
                if progress_callback and total_size > 0:
                    percent = (downloaded / total_size) * 100
                    progress_callback(f"Downloading update... {percent:.1f}% ({downloaded // 1024 // 1024:.1f}/{total_size // 1024 // 1024:.1f} MB)")
                elif progress_callback:
                    progress_callback(f"Downloading update... {downloaded // 1024 // 1024:.1f} MB downloaded")

        if progress_callback:
            progress_callback("Download complete. Verifying file...")
        print("Download complete. Preparing update helper...")

        # Verify downloaded file size
        actual_size = os.path.getsize(temp_path)
        if total_size > 0:
            if actual_size != total_size:
                raise Exception(f"Downloaded file size mismatch: expected {total_size}, got {actual_size}")
            if progress_callback:
                progress_callback(f"File verification successful ({actual_size // 1024 // 1024:.1f} MB)")
        else:
            if progress_callback:
                progress_callback(f"Download completed ({actual_size // 1024 // 1024:.1f} MB)")
        
        # Basic file validation - check if it's a valid executable
        if actual_size < 1024 * 1024:  # Less than 1MB is suspicious for an executable
            raise Exception("Downloaded file appears to be too small to be a valid executable")
            
        if progress_callback:
            progress_callback("File validation passed")

        if progress_callback:
            progress_callback("Creating backup of current version...")
        
        # Create backup of current executable
        backup_path = current_exe_path + ".backup"
        if os.path.exists(backup_path):
            if progress_callback:
                progress_callback("Removing old backup...")
            os.remove(backup_path)
        
        if progress_callback:
            progress_callback("Creating backup of current executable...")
        shutil.copy2(current_exe_path, backup_path)
        
        if progress_callback:
            backup_size = os.path.getsize(backup_path)
            progress_callback(f"Backup created successfully ({backup_size // 1024 // 1024:.1f} MB)")

        if progress_callback:
            progress_callback("Preparing update helper script...")

        # Write helper script that waits for the current process to exit,
        # replaces the executable and launches the new one
        helper_code = f"""
import os
import shutil
import subprocess
import sys
import time

OLD = r"{current_exe_path}"
NEW = r"{temp_path}"

# Wait for current process to exit (up to 30 seconds)
for i in range(30):
    try:
        os.remove(OLD)
        break
    except PermissionError:
        time.sleep(1)
    except FileNotFoundError:
        break
else:
    # Timeout - exit with error
    sys.exit(1)

# Move new executable to replace old one
try:
    shutil.move(NEW, OLD)
except Exception as e:
    sys.exit(1)

# Launch the new executable
try:
    subprocess.Popen([OLD])
except Exception as e:
    sys.exit(1)
"""

        with tempfile.NamedTemporaryFile(delete=False, suffix=".py", mode="w", encoding="utf-8") as helper:
            helper.write(helper_code)
            helper_path = helper.name

        if progress_callback:
            progress_callback("Update helper script created successfully")
            progress_callback("Launching update helper...")

        try:
            subprocess.Popen([sys.executable, helper_path])
        except Exception as e:
            raise Exception(f"Failed to launch update helper: {e}")

        if progress_callback:
            progress_callback("Update helper launched successfully")
            progress_callback("Application will restart in a few seconds...")
        print("Updater launched. Exiting current instance...")
        return True

    except Exception as e:
        error_msg = f"Update failed: {str(e)}"
        if progress_callback:
            progress_callback(error_msg)
        print(error_msg)
        
        # Clean up temp file if it exists
        if "temp_path" in locals() and os.path.exists(temp_path):
            try:
                if progress_callback:
                    progress_callback("Cleaning up temporary files...")
                os.remove(temp_path)
                if progress_callback:
                    progress_callback("Temporary files cleaned up")
            except Exception as cleanup_error:
                if progress_callback:
                    progress_callback(f"Warning: Failed to clean up temporary file: {cleanup_error}")
                pass
                
        # Try to restore backup if replacement failed
        backup_path = current_exe_path + ".backup"
        if os.path.exists(backup_path) and not os.path.exists(current_exe_path):
            try:
                if progress_callback:
                    progress_callback("Attempting to restore backup...")
                shutil.move(backup_path, current_exe_path)
                success_msg = "Backup restored successfully"
                if progress_callback:
                    progress_callback(success_msg)
                print(success_msg)
            except Exception as restore_error:
                restore_msg = f"Failed to restore backup: {restore_error}"
                if progress_callback:
                    progress_callback(restore_msg)
                print(restore_msg)
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
        if _download_and_replace_executable(download_url, current_exe_path, progress_callback, cancel_check):
            if progress_callback:
                progress_callback("Update process completed successfully!")
                progress_callback("Application will restart automatically...")
            print("Update helper launched. Exiting for update...")
            sys.exit(0)
        else:
            error_msg = "Update process failed - continuing with current version"
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
        _pause("Press Enter to exit...")
        sys.exit(0)
