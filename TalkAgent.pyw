"""Double-click launcher for the local TalkAgent web application."""

from __future__ import annotations

import subprocess
import sys
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
ENTRY_SCRIPT = APP_DIR / "run_talkagent_ui.py"
APP_URL = "http://127.0.0.1:7860"


def _service_is_ready() -> bool:
    try:
        with urllib.request.urlopen(APP_URL, timeout=1) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError):
        return False


def main() -> None:
    if _service_is_ready():
        webbrowser.open(APP_URL)
        return

    subprocess.Popen(
        [sys.executable, "-B", str(ENTRY_SCRIPT)],
        cwd=str(APP_DIR),
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


if __name__ == "__main__":
    main()
