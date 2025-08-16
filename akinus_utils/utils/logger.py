import os
import sys
import platform
import asyncio
from pathlib import Path
from datetime import datetime
import inspect
from functools import wraps

from akinus_utils.utils.app_details import PROJECT_ROOT, APP_NAME

# Local file logging setup
LOGS_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOGS_DIR / f"{APP_NAME}.log"
MAX_LOG_SIZE = 2 * 1024 * 1024  # 2MB in bytes

LOGS_DIR.mkdir(parents=True, exist_ok=True)

LOG_LEVELS = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "ERROR": 40,
    "CRITICAL": 50,
}

log_lock = asyncio.Lock()


def rotate_log_file():
    """Check log size and rotate if necessary."""
    if LOG_FILE.exists() and LOG_FILE.stat().st_size > MAX_LOG_SIZE:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        rotated_file = LOGS_DIR / f"{timestamp}.log"
        LOG_FILE.rename(rotated_file)
        LOG_FILE.touch()  # Create a new empty log file


def _write_log_line(line: str):
    """Blocking I/O to write the log line."""
    rotate_log_file()
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line)


async def _local(message_type: str, script: str, message: str):
    """Async log to local file (logger.log)."""
    frame = inspect.stack()[2]  # go up 2 levels to skip wrapper
    caller_file = frame.filename.split("/")[-1]
    caller_line = frame.lineno
    caller_func = frame.function

    priority = LOG_LEVELS.get(message_type.upper(), 20)  # Default INFO
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    line = (
        f"{priority} {timestamp}: {message_type.upper()}: "
        f"{caller_file}:{caller_line} ({caller_func}): {message}\n"
    )

    async with log_lock:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _write_log_line, line)


# --------------------------
# System logger implementation
# --------------------------

import logging

system_logger = logging.getLogger("system_logger")
system_logger.setLevel(logging.DEBUG)
if not system_logger.hasHandlers():
    ch = logging.StreamHandler()
    formatter = logging.Formatter("%(levelname)s %(asctime)s %(name)s: %(message)s")
    ch.setFormatter(formatter)
    system_logger.addHandler(ch)


async def _system(message_type: str, script: str, message: str):
    """Async log to platform-specific system logging facility."""
    system_platform = platform.system()
    full_message = f"{script}: {message}"
    level = LOG_LEVELS.get(message_type.upper(), logging.INFO)

    try:
        if system_platform == "Linux":
            try:
                from systemd import journal
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, journal.send, full_message)
                return
            except ImportError:
                import syslog
                priority_map = {
                    10: syslog.LOG_DEBUG,
                    20: syslog.LOG_INFO,
                    30: syslog.LOG_WARNING,
                    40: syslog.LOG_ERR,
                    50: syslog.LOG_CRIT,
                }
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(
                    None,
                    lambda: (
                        syslog.openlog(script),
                        syslog.syslog(priority_map.get(level, syslog.LOG_INFO), message),
                        syslog.closelog(),
                    ),
                )
                return

        elif system_platform == "Windows":
            try:
                import win32evtlogutil  # pyright: ignore
                import win32evtlog  # pyright: ignore
                import win32con  # pyright: ignore

                level_map = {
                    10: win32evtlog.EVENTLOG_INFORMATION_TYPE,
                    20: win32evtlog.EVENTLOG_INFORMATION_TYPE,
                    30: win32evtlog.EVENTLOG_WARNING_TYPE,
                    40: win32evtlog.EVENTLOG_ERROR_TYPE,
                    50: win32evtlog.EVENTLOG_ERROR_TYPE,
                }
                event_type = level_map.get(level, win32evtlog.EVENTLOG_INFORMATION_TYPE)

                loop = asyncio.get_running_loop()
                await loop.run_in_executor(
                    None,
                    lambda: win32evtlogutil.ReportEvent(
                        script,
                        eventID=1,
                        eventCategory=0,
                        eventType=event_type,
                        strings=[message],
                    ),
                )
                return
            except ImportError:
                system_logger.log(level, full_message)
                return

        elif system_platform == "Darwin":
            try:
                from Foundation import NSLog  # pyright: ignore
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, NSLog, f"{script}: {message}")
                return
            except ImportError:
                system_logger.log(level, full_message)
                return
        else:
            system_logger.log(level, full_message)
    except Exception as e:
        system_logger.error(f"System log failed: {e}")
        system_logger.log(level, full_message)


# --------------------------
# Auto async wrapper
# --------------------------

def log(message_type: str, script: str, message: str, target: str = "local"):
    """
    Unified logging entrypoint.

    Example:
        await log("INFO", "myscript", "something happened")          # local async
        await log("ERROR", "myscript", "bad system error", target="system")
        log("INFO", "myscript", "from sync code")                    # local sync
    """
    func = _local if target == "local" else _system

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # sync context
        return asyncio.run(func(message_type, script, message))
    else:
        # async context
        return func(message_type, script, message)
