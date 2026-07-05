import os
import threading
import time
import urllib.request
import webbrowser

import uvicorn

from app.config import GRADIO_PORT
from app.main import app


HOST = "127.0.0.1"
URL = f"http://{HOST}:{GRADIO_PORT}"


def wait_until_ready(timeout: int = 90) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(URL, timeout=2) as response:
                return response.status == 200
        except Exception:
            time.sleep(1)
    return False


def main() -> int:
    config = uvicorn.Config(app, host=HOST, port=GRADIO_PORT, log_level="info")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    print("Starting TalkAgent UI...", flush=True)
    print(f"Address: {URL}", flush=True)
    print("Waiting for service to become ready...", flush=True)

    if not wait_until_ready():
        print("TalkAgent did not become ready within 90 seconds.", flush=True)
        server.should_exit = True
        thread.join(timeout=10)
        return 1

    print("TalkAgent is ready.", flush=True)
    if os.getenv("TALKAGENT_NO_BROWSER", "").lower() not in {"1", "true", "yes"}:
        webbrowser.open(URL)
    print("Keep this window open while using TalkAgent. Press Ctrl+C to stop.", flush=True)

    try:
        while thread.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping TalkAgent...", flush=True)
        server.should_exit = True
        thread.join(timeout=10)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
