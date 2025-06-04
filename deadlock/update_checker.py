import os
import subprocess
import sys
from typing import Optional

import requests

REPO_API_COMMIT = "https://api.github.com/repos/hmate9/deadunlock/commits/main"


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


def ensure_up_to_date() -> None:
    """Pull the latest changes if the local repo is outdated and exit."""
    local = _local_commit()
    remote = _remote_commit()
    if local and remote and local != remote:
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
