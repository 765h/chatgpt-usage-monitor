import logging
import threading
import time
import tkinter as tk
from datetime import datetime, timezone
from typing import Optional

from PIL import Image, ImageDraw, ImageFont
import pystray
from pystray import MenuItem as item

import codex_usage

POLL_INTERVAL = 30

BG       = "#1e1e1e"
BG_CARD  = "#2a2a2a"
TEXT     = "#e8e8e8"
TEXT_DIM = "#888888"
BAR_BG   = "#3a3a3a"
WAITING_TITLE = "ChatGPT 残量 — データ待機中"
LUNA_BADGE_BG = (155, 95, 230)
LUNA_BADGE_FG = (255, 255, 255)
LUNA_ACTIVE_BG = "#d8b2ff"
LUNA_ACTIVE_FG = "#000000"
LOGGER = logging.getLogger(__name__)


def _remaining_ratio(used_ratio: float) -> float:
    return round(1.0 - used_ratio, 10)


def _remaining_color(remaining: float) -> tuple[int, int, int]:
    if remaining < 0.2:
        return (240, 70, 60)
    if remaining < 0.5:
        return (255, 185, 50)
    return (80, 210, 100)


def _format_remaining(used_ratio: Optional[float]) -> str:
    return "—" if used_ratio is None else f"{int(_remaining_ratio(used_ratio) * 100)}%"


def _make_tooltip(
    ratio_5h: Optional[float],
    ratio_weekly: Optional[float],
    reset_5h,
    ratio_luna: Optional[float] = None,
    reset_luna=None,
    luna_active: bool = False,
) -> str:
    current_label = "Luna reserve" if luna_active else "Session"
    current_ratio = ratio_luna if luna_active else ratio_5h
    current_reset = reset_luna if luna_active else reset_5h
    if current_ratio is None:
        lines = [
            WAITING_TITLE
            if not luna_active and ratio_5h is None
            else f"現在利用中: {current_label} 残量: —"
        ]
    else:
        lines = [
            f"現在利用中: {current_label} 残量: {_format_remaining(current_ratio)}  {_fmt_resets_in(current_reset)}"
        ]
    if not luna_active and ratio_5h is not None:
        lines.append(f"Session 残量: {_format_remaining(ratio_5h)}  {_fmt_resets_in(reset_5h)}")
    if ratio_weekly is not None:
        lines.append(f"Weekly 残量: {_format_remaining(ratio_weekly)}")
    if ratio_luna is not None and not luna_active:
        lines.append(f"Luna reserve 残量: {_format_remaining(ratio_luna)}  {_fmt_resets_in(reset_luna)}")
    elif luna_active and ratio_5h is not None:
        lines.append(f"Session 残量: {_format_remaining(ratio_5h)}  {_fmt_resets_in(reset_5h)}")
    if luna_active:
        lines.append("Luna reserve 使用中")
    return "\n".join(lines)


def _get_font(size: int) -> ImageFont.FreeTypeFont:
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/bahnschrift.ttf", size)
        font.set_variation_by_name("Bold Condensed")
        return font
    except Exception:
        pass
    for name in ["ariblk.ttf", "segoeuib.ttf", "arialbd.ttf"]:
        try:
            return ImageFont.truetype(f"C:/Windows/Fonts/{name}", size)
        except OSError:
            continue
    return ImageFont.load_default()


def _fit_font(text: str, max_px: int) -> ImageFont.FreeTypeFont:
    lo, hi = 8, max_px
    best = _get_font(lo)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        font = _get_font(mid)
        bb = font.getbbox(text)
        if bb[2] - bb[0] <= max_px and bb[3] - bb[1] <= max_px:
            lo, best = mid, font
        else:
            hi = mid - 1
    return best


def make_icon(
    ratio_5h: Optional[float],
    luna_active: bool = False,
    ratio_luna: Optional[float] = None,
) -> Image.Image:
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    ratio = ratio_luna if luna_active else ratio_5h
    luna_value_known = luna_active and ratio_luna is not None
    if luna_value_known:
        draw.rounded_rectangle((2, 2, 62, 62), radius=10, fill=LUNA_ACTIVE_BG)
    if ratio is None:
        draw.text((size // 2, size // 2), "—", fill=(100, 100, 100),
                  font=_fit_font("—", size - 2), anchor="mm")
    else:
        remaining = _remaining_ratio(ratio)
        pct = int(remaining * 100)
        color = LUNA_ACTIVE_FG if luna_value_known else _remaining_color(remaining)

        text = "×" if pct == 0 else str(pct)
        draw.text((size // 2, size // 2 + 2), text, fill=color,
                  font=_fit_font(text, size - 2), anchor="mm")
    if luna_active:
        draw.ellipse((45, 45, 62, 62), fill=LUNA_BADGE_BG, outline=LUNA_BADGE_FG, width=1)
        draw.text((53, 53), "L", fill=LUNA_BADGE_FG, font=_get_font(10), anchor="mm")
    return img


def _fmt_resets_in(reset_at) -> str:
    if not reset_at:
        return "—"
    total_mins = int((reset_at - datetime.now(timezone.utc)).total_seconds() / 60)
    if total_mins <= 0:
        return "まもなくリセット"
    h, m = divmod(total_mins, 60)
    return f"Resets in {h}h {m}m" if h else f"Resets in {m}m"


def _fmt_resets_day(reset_at) -> str:
    if not reset_at:
        return "—"
    local = reset_at.astimezone()
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    return f"Resets {days[local.weekday()]} {local.strftime('%I:%M %p').lstrip('0')}"


def _fmt_updated(fetched_at) -> str:
    if not fetched_at:
        return ""
    mins = int((datetime.now(timezone.utc) - fetched_at).total_seconds() / 60)
    return f"Updated {mins}m ago"


_popup_ref = [None]
_close_popup = [False]


def _usage_bar(parent, ratio: float) -> None:
    frame = tk.Frame(parent, bg=BG)
    frame.pack(fill="x", padx=16, pady=(2, 0))
    canvas = tk.Canvas(frame, height=6, bg=BG, highlightthickness=0)
    canvas.pack(fill="x")

    def _draw(event=None):
        try:
            if not canvas.winfo_exists():
                return
            w = canvas.winfo_width()
        except tk.TclError:
            return
        if w < 2:
            return
        canvas.delete("all")
        canvas.create_rectangle(0, 0, w, 6, fill=BAR_BG, outline="")
        fw = int(w * min(ratio, 1.0))
        if fw > 0:
            color = "#%02x%02x%02x" % _remaining_color(ratio)
            canvas.create_rectangle(0, 0, fw, 6, fill=color, outline="")

    canvas.bind("<Configure>", _draw)
    canvas.after(50, _draw)


def _render_popup(content, stats: dict, close_command) -> None:
    for child in content.winfo_children():
        child.destroy()

    header = tk.Frame(content, bg=BG)
    header.pack(fill="x", padx=16, pady=(14, 10))
    tk.Label(header, text="Remaining", bg=BG, fg=TEXT,
             font=("Segoe UI", 10, "bold")).pack(side="left")
    tk.Label(header, text=_fmt_updated(stats.get("fetched_at")), bg=BG, fg=TEXT_DIM,
             font=("Segoe UI", 8)).pack(side="right")
    tk.Frame(content, bg=BAR_BG, height=1).pack(fill="x", padx=16, pady=(0, 10))

    rows = [
        ("Session",      "utilization_5h",     "resets_at_5h",     _fmt_resets_in, 10),
        ("Weekly (All)", "utilization_weekly",  "resets_at_weekly", _fmt_resets_day, 14),
    ]
    if stats.get("utilization_luna_reserve") is not None or stats.get("luna_reserve_active"):
        rows.append(("Luna reserve", "utilization_luna_reserve", "resets_at_luna_reserve", _fmt_resets_in, 14))

    for label, key_pct, key_reset, fmt_reset, bottom_pad in rows:
        used_ratio = stats.get(key_pct)
        row = tk.Frame(content, bg=BG)
        row.pack(fill="x", padx=16, pady=(0, 2))
        tk.Label(row, text=label, bg=BG, fg=TEXT,
                 font=("Segoe UI", 9, "bold")).pack(side="left")
        tk.Label(row, text=fmt_reset(stats.get(key_reset)), bg=BG, fg=TEXT_DIM,
                 font=("Segoe UI", 8)).pack(side="right")
        if used_ratio is not None:
            _usage_bar(content, _remaining_ratio(used_ratio))
        tk.Label(content, text=_format_remaining(used_ratio), bg=BG, fg=TEXT_DIM,
                 font=("Segoe UI", 8)).pack(anchor="w", padx=16, pady=(2, bottom_pad))

    tk.Frame(content, bg=BAR_BG, height=1).pack(fill="x", padx=16, pady=(0, 8))
    tk.Button(content, text="✕  閉じる", command=close_command,
              bg=BG, fg=TEXT_DIM, relief="flat", font=("Segoe UI", 8),
              activebackground=BG_CARD, cursor="hand2", bd=0).pack(pady=(0, 10))


def show_popup(stats: dict):
    if _popup_ref[0] is not None:
        return

    _close_popup[0] = False
    win = tk.Tk()
    win.title("")
    win.configure(bg=BG)
    win.resizable(False, False)
    win.attributes("-topmost", True)
    win.overrideredirect(True)

    content = tk.Frame(win, bg=BG)
    content.pack()

    def _render(current_stats: dict) -> None:
        _render_popup(content, current_stats, win.destroy)
        win.update_idletasks()

    def _refresh():
        if _close_popup[0]:
            return
        try:
            latest = codex_usage.get_last_data()
            if latest:
                _render(latest)
                sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
                w, h = win.winfo_reqwidth(), win.winfo_reqheight()
                x = max(0, sw - w - 16)
                y = max(0, sh - h - 56)
                win.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            LOGGER.exception("Popup refresh failed")
        if not _close_popup[0]:
            win.after(POLL_INTERVAL * 1000, _refresh)

    _render(stats)

    win.update_idletasks()
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    w, h = win.winfo_reqwidth(), win.winfo_reqheight()
    win.geometry(f"{w}x{h}+{sw - w - 16}+{sh - h - 56}")

    def _check_close():
        if _close_popup[0]:
            win.destroy()
            return
        win.after(100, _check_close)

    win.bind("<Escape>", lambda e: win.destroy())
    win.after(100, _check_close)
    win.after(POLL_INTERVAL * 1000, _refresh)
    _popup_ref[0] = win
    win.mainloop()
    _popup_ref[0] = None


def run_tray(on_quit=None):
    stats: dict = {}
    lock = threading.Lock()
    tray_icon = None

    def _poll_once():
        new_stats = codex_usage.get_last_data()
        if new_stats:
            with lock:
                stats.update(new_stats)
        _refresh_icon()

    def poll_loop():
        while True:
            time.sleep(POLL_INTERVAL)
            try:
                _poll_once()
            except Exception:
                LOGGER.exception("Tray usage update failed")

    def _refresh_icon():
        if not tray_icon:
            return
        with lock:
            r5 = stats.get("utilization_5h")
            rw = stats.get("utilization_weekly")
            reset_5h = stats.get("resets_at_5h")
            rl = stats.get("utilization_luna_reserve")
            reset_luna = stats.get("resets_at_luna_reserve")
            luna_active = bool(stats.get("luna_reserve_active"))
        tooltip = _make_tooltip(r5, rw, reset_5h, rl, reset_luna, luna_active)
        tray_icon.icon = make_icon(r5, luna_active, rl)
        tray_icon.title = tooltip

    def on_click(icon, button):
        if _popup_ref[0] is not None:
            _close_popup[0] = True
            return
        with lock:
            s = dict(stats)
        threading.Thread(target=show_popup, args=(s,), daemon=True).start()

    def _quit_handler(icon, _):
        if on_quit:
            on_quit()
        icon.stop()

    tray_icon = pystray.Icon(
        "chatgpt_usage",
        make_icon(None),
        title=WAITING_TITLE,
        menu=pystray.Menu(
            item("残量詳細を表示", on_click, default=True),
            item("終了", _quit_handler),
        ),
    )

    try:
        _poll_once()
    except Exception:
        LOGGER.exception("Initial tray usage update failed")
    threading.Thread(target=poll_loop, daemon=True).start()
    tray_icon.run()
