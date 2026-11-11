# The Pirate Cove Campus Marketplace
# Created by Ethan Williams 11/9/26

"""
scripts/run_local.py

Started by "Launch Pirate Cove.command" (macOS) and "Launch Pirate Cove.bat" (Windows).
Starts the app on this computer, waits until it answers, then opens it in the browser.
Closing the window (or pressing Ctrl+C) stops the app.

Port: uses PORT from the environment if set, otherwise the first free port from 5000.
(On macOS, AirPlay Receiver often takes port 5000, so 5001+ is used then.)
"""

import os
import socket
import sys
import threading
import time
import urllib.request
import webbrowser

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.chdir(ROOT)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "backend"))


def port_is_free(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def pick_port():
    if os.environ.get("PORT"):
        return int(os.environ["PORT"])
    for port in range(5000, 5021):
        if port_is_free(port):
            return port
    raise SystemExit("No free port between 5000 and 5020. Close other apps and try again.")


def open_browser_when_ready(url):
    # Wait for /health to answer, so the browser doesn't open on an error page
    for _ in range(120):
        try:
            with urllib.request.urlopen(url + "/health", timeout=1):
                break
        except Exception:
            time.sleep(0.5)
    print(f"\nThe Pirate Cove is running at {url}")
    print("Leave this window open while you use the site. Close it (or press Ctrl+C) to stop.\n", flush=True)
    webbrowser.open(url)


def main():
    if not os.path.exists(os.path.join(ROOT, ".env")):
        print("No .env file found. Run the installer first (install.command or install.bat).")
        return 1

    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT, ".env"))

    port = pick_port()
    url = f"http://127.0.0.1:{port}"
    print("Starting The Pirate Cove...", flush=True)

    from app import app  # also runs the table migrations

    threading.Thread(target=open_browser_when_ready, args=(url,), daemon=True).start()
    # debug=False: the Werkzeug debugger must never run in a release build
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nStopped.")
