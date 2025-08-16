import platform
import sys
import asyncio
import subprocess
from akinus_utils.utils.logger  import log
from akinus_utils.utils.app_details import APP_NAME

def notify(title: str, message: str):
    system = platform.system()
    try:
        if system == "Linux":
            subprocess.run(["notify-send", title, message, APP_NAME])
        elif system == "Windows":
            # Import Windows-only ToastNotifier here to avoid import errors on other OSes
            from win10toast import ToastNotifier  # pyright: ignore[reportMissingImports]
            toaster = ToastNotifier()
            toaster.show_toast(title, message, duration=5)
        elif system == "Darwin":
            script = f'display notification "{message}" with title "{title}"'
            subprocess.run(["osascript", "-e", script])
        else:
            print(f"{title}: {message}")
    except Exception as e:
        asyncio.run(log("WARNING", "notify.py", f"Notification failed: {e}"))
        print(f"{title}: {message}")

