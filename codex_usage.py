import json
import math
import queue
import shutil
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

CODEX_SESSIONS = Path.home() / ".codex" / "sessions"
APP_SERVER_POLL_INTERVAL = 60
APP_SERVER_TIMEOUT = 8

_luna_lock = threading.Lock()
_luna_data: dict = {}
_started = False


def _parse_rate_limits(obj: dict) -> dict | None:
    if not isinstance(obj, dict):
        return None
    payload = obj.get("payload")
    if not isinstance(payload, dict):
        return None
    limits = payload.get("rate_limits")
    if not isinstance(limits, dict) or not limits.get("primary") or not limits.get("secondary"):
        return None

    try:
        fetched_at = datetime.fromisoformat(obj["timestamp"].replace("Z", "+00:00"))
        if fetched_at.tzinfo is None:
            return None
        fetched_at = fetched_at.astimezone(timezone.utc)
    except (AttributeError, KeyError, TypeError, ValueError):
        return None

    def window(name: str) -> tuple[float, datetime]:
        value = limits[name]
        used_percent = float(value["used_percent"])
        if not math.isfinite(used_percent) or not 0 <= used_percent <= 100:
            raise ValueError
        return (
            used_percent / 100,
            datetime.fromtimestamp(value["resets_at"], timezone.utc),
        )

    try:
        primary, secondary = window("primary"), window("secondary")
    except (KeyError, TypeError, ValueError, OverflowError, OSError):
        return None
    return {
        "utilization_5h": primary[0],
        "resets_at_5h": primary[1],
        "utilization_weekly": secondary[0],
        "resets_at_weekly": secondary[1],
        "fetched_at": fetched_at,
    }


def _latest_from_file(path: Path) -> dict | None:
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except (OSError, PermissionError):
        return None
    for line in reversed(lines):
        try:
            parsed = _parse_rate_limits(json.loads(line))
        except json.JSONDecodeError:
            continue
        if parsed:
            return parsed
    return None


def _codex_executable() -> str | None:
    return shutil.which("codex.exe") or shutil.which("codex")


def _wait_for_response(messages: queue.Queue, request_id: int, timeout: float) -> dict | None:
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None
        try:
            line = messages.get(timeout=remaining)
        except queue.Empty:
            return None
        if line is None:
            return None
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(message, dict) and message.get("id") == request_id:
            return message


def _read_app_server_rate_limits() -> dict | None:
    executable = _codex_executable()
    if executable is None:
        return None
    try:
        process = subprocess.Popen(
            [executable, "app-server", "--stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000),
        )
    except (OSError, ValueError):
        return None

    messages: queue.Queue = queue.Queue()

    def read_lines() -> None:
        try:
            for line in process.stdout or ():
                messages.put(line)
        finally:
            messages.put(None)

    threading.Thread(target=read_lines, daemon=True).start()
    try:
        if process.stdin is None:
            return None
        process.stdin.write(json.dumps({
            "id": 1,
            "method": "initialize",
            "params": {"clientInfo": {"name": "chatgpt-usage-monitor", "version": "1.0"}},
        }) + "\n")
        process.stdin.flush()
        if _wait_for_response(messages, 1, APP_SERVER_TIMEOUT) is None:
            return None
        process.stdin.write(json.dumps({"method": "initialized"}) + "\n")
        process.stdin.write(json.dumps({
            "id": 2,
            "method": "account/rateLimits/read",
            "params": None,
        }) + "\n")
        process.stdin.flush()
        response = _wait_for_response(messages, 2, APP_SERVER_TIMEOUT)
        result = response.get("result") if response else None
        return result if isinstance(result, dict) else None
    except (OSError, TypeError, ValueError):
        return None
    finally:
        try:
            if process.stdin is not None:
                process.stdin.close()
        except OSError:
            pass
        try:
            process.terminate()
            process.wait(timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            try:
                process.kill()
            except OSError:
                pass


def _parse_luna_reserve(result: dict | None) -> dict | None:
    if not isinstance(result, dict):
        return None
    buckets = result.get("rateLimitsByLimitId")
    if not isinstance(buckets, dict):
        return None
    main_limits = result.get("rateLimits")
    main_blocked = False
    if isinstance(main_limits, dict):
        reached_type = main_limits.get("rateLimitReachedType")
        main_blocked = isinstance(reached_type, str) and bool(reached_type)
        for name in ("primary", "secondary"):
            window = main_limits.get(name)
            used = window.get("usedPercent") if isinstance(window, dict) else None
            if not isinstance(used, bool):
                try:
                    main_blocked = main_blocked or float(used) >= 100
                except (TypeError, ValueError):
                    pass
    for bucket in buckets.values():
        if not isinstance(bucket, dict) or bucket.get("limitName") != "gpt-reserve":
            continue
        primary = bucket.get("primary")
        if not isinstance(primary, dict):
            continue
        used_percent = primary.get("usedPercent")
        if isinstance(used_percent, bool):
            continue
        try:
            used_percent = float(used_percent)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(used_percent) or not 0 <= used_percent <= 100:
            continue
        reserve_reached_type = bucket.get("rateLimitReachedType")
        reserve_available = not (isinstance(reserve_reached_type, str) and reserve_reached_type) and used_percent < 100
        reset_at = None
        raw_reset_at = primary.get("resetsAt")
        if raw_reset_at is not None and not isinstance(raw_reset_at, bool):
            try:
                reset_at = datetime.fromtimestamp(float(raw_reset_at), timezone.utc)
            except (TypeError, ValueError, OverflowError, OSError):
                pass
        return {
            "utilization_luna_reserve": used_percent / 100,
            "resets_at_luna_reserve": reset_at,
            "luna_reserve_active": main_blocked and reserve_available,
        }
    return None


def _update_luna_reserve() -> None:
    parsed = _parse_luna_reserve(_read_app_server_rate_limits())
    with _luna_lock:
        was_active = _luna_data.get("luna_reserve_active") is True
        _luna_data.clear()
        if parsed:
            _luna_data.update(parsed)
        elif was_active:
            _luna_data.update({
                "utilization_luna_reserve": None,
                "resets_at_luna_reserve": None,
                "luna_reserve_active": True,
            })


def _luna_poll_loop() -> None:
    while True:
        _update_luna_reserve()
        time.sleep(APP_SERVER_POLL_INTERVAL)


def get_last_data() -> dict:
    result = {}
    try:
        files = sorted(CODEX_SESSIONS.rglob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    except (OSError, PermissionError):
        files = []
    for path in files:
        data = _latest_from_file(path)
        if data:
            result = data
            break
    with _luna_lock:
        if _started:
            result.update({
                "utilization_luna_reserve": _luna_data.get("utilization_luna_reserve"),
                "resets_at_luna_reserve": _luna_data.get("resets_at_luna_reserve"),
                "luna_reserve_active": _luna_data.get("luna_reserve_active"),
            })
        else:
            result.update(_luna_data)
    return result


def start() -> None:
    global _started
    with _luna_lock:
        if _started:
            return
        _started = True
    threading.Thread(target=_luna_poll_loop, daemon=True, name="luna-reserve-poll").start()
