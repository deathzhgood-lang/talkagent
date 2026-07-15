"""Double-click launcher for the local TalkAgent web application."""

from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
ENTRY_SCRIPT = APP_DIR / "run_talkagent_ui.py"
APP_URL = "http://127.0.0.1:7860"
HEALTH_URL = f"{APP_URL}/api/system-status"
ICON_PATH = APP_DIR / "assets" / "talkagent.ico"
LOG_PATH = APP_DIR / "data" / "launcher" / "server.log"


def _service_is_ready() -> bool:
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=1) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError):
        return False


def _create_splash():
    """Give a double-clicked launcher visible progress while the server starts."""
    try:
        import tkinter as tk

        root = tk.Tk()
        root.title("TalkAgent")
        root.resizable(False, False)
        root.geometry("360x148")
        root.configure(bg="#F7FAFC")
        if ICON_PATH.exists():
            root.iconbitmap(default=str(ICON_PATH))

        tk.Label(
            root,
            text="T",
            font=("Segoe UI", 34, "bold"),
            fg="#0F766E",
            bg="#F7FAFC",
        ).pack(pady=(24, 2))
        status = tk.Label(
            root,
            text="正在启动 TalkAgent...",
            font=("Segoe UI", 11),
            fg="#334155",
            bg="#F7FAFC",
        )
        status.pack()
        root.update_idletasks()
        return root, status
    except Exception:
        return None, None


def _show_startup_error(message: str) -> None:
    try:
        from tkinter import messagebox

        messagebox.showerror("TalkAgent 启动失败", message)
    except Exception:
        pass


def main() -> None:
    if _service_is_ready():
        webbrowser.open(APP_URL)
        return

    splash, status = _create_splash()
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    environment = dict(os.environ)
    environment["TALKAGENT_NO_BROWSER"] = "1"
    environment["PYTHONUNBUFFERED"] = "1"

    with LOG_PATH.open("ab") as log_file:
        process = subprocess.Popen(
            [sys.executable, "-B", str(ENTRY_SCRIPT)],
            cwd=str(APP_DIR),
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        if _service_is_ready():
            if splash:
                splash.destroy()
            webbrowser.open(APP_URL)
            return

        if process.poll() is not None:
            if splash:
                splash.destroy()
            _show_startup_error(
                "本地服务未能启动。请查看日志：\n"
                f"{LOG_PATH}\n\n"
                "也可以双击 start_talkagent_ui.bat 查看详细错误。"
            )
            return

        if splash and status:
            status.configure(text="正在加载本地知识库，请稍候...")
            splash.update()
        time.sleep(0.4)

    if splash:
        splash.destroy()
    _show_startup_error(
        "TalkAgent 在 90 秒内未就绪。请查看日志：\n"
        f"{LOG_PATH}\n\n"
        "也可以双击 start_talkagent_ui.bat 查看详细错误。"
    )


if __name__ == "__main__":
    main()
