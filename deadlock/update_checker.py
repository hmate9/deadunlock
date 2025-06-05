"""Utility functions for update notifications."""

from __future__ import annotations

import os
import subprocess
import sys
import webbrowser
from typing import Optional

import requests

REPO_API_COMMIT = "https://api.github.com/repos/hmate9/deadunlock/commits/main"
REPO_API_RELEASES = "https://api.github.com/repos/hmate9/deadunlock/releases/latest"
RELEASE_PAGE = "https://github.com/hmate9/deadunlock/releases/latest"


def _is_binary_release() -> bool:
    """Return ``True`` if running as a PyInstaller binary."""
    return getattr(sys, "frozen", False)


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
    """Return the current version string or ``None`` if unavailable."""
    if _is_binary_release():
        try:
            if hasattr(sys, "_MEIPASS"):
                version_file = os.path.join(sys._MEIPASS, "version.txt")
            else:
                version_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "version.txt")
            if os.path.exists(version_file):
                with open(version_file, "r", encoding="utf-8") as fh:
                    return fh.read().strip()
        except Exception:
            return None
    return _local_commit()


def update_available() -> bool:
    """Return ``True`` if a newer commit or release exists."""
    if _is_binary_release():
        release = _get_latest_release()
        if not release:
            return False
        tag = release.get("tag_name", "")
        if not tag.startswith("build-"):
            return False
        latest = tag[6:]
        current = _get_current_version()
        return not current or current != latest
    local = _local_commit()
    remote = _remote_commit()
    return bool(local and remote and local != remote)


def open_release_page() -> None:
    """Open the project's latest release page in the default browser."""
    webbrowser.open(RELEASE_PAGE)


def ensure_up_to_date() -> None:
    """Check for updates and open the release page if a newer version exists."""
    if update_available():
        print("A newer DeadUnlock version is available. Opening download page...")
        open_release_page()
        sys.exit(0)

