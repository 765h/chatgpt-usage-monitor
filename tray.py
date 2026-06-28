import threading
import time
import tkinter as tk
from datetime import datetime, timezone
from typing import Optional

from PIL import Image, ImageDraw, ImageFont
import pystray
from pystray import MenuItem as item

import server

POLL_INTERVAL = 30

BG       = "#1e1e1e"
BG_CARD  = "#2a2a2a"
TEXT     = "#e8e8e8"
TEXT_DIM = "#888888"
ORANGE   = "#e07a30"
BAR_BG   = "#3a3a3a"


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


def make_icon(ratio_5h: Optional[float]) -> Image.Image:
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    if ratio_5h is None:
        draw.text((size // 2, size // 2), "—", fill=(100, 100, 100),
                  font=_fit_font("—", size - 2), anchor="mm")
        return img

    pct = min(int(ratio_5h * 100), 100)
    if pct < 50:
        color = (80, 210, 100)
    elif pct < 80:
        color = (255, 185, 50)
    else:
        color = (240, 70, 60)

    text = "×" if pct >= 100 else str(pct)
    draw.text((size // 2, size // 2 + 2), text, fill=color,
              font=_fit_font(text, size - 2), anchor="mm")
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


def _usage_bar(parent, ratio: float) -> None:
    frame = tk.Frame(parent, bg=BG)
    frame.pack(fill="x", padx=16, pady=(2, 0))
    canvas = tk.Canvas(frame, height=6, bg=BG, highlightthickness=0)
    canvas.pack(fill="x")

    def _draw(event=None):
        w = canvas.winfo_width()
        if w < 2:
            return
        canvas.delete("all")
        canvas.create_rectangle(0, 0, w, 6, fill=BAR_BG, outline="")
        fw = int(w * min(ratio, 1.0))
        if fw > 0:
            canvas.create_rectangle(0, 0, fw, 6, fill=ORANGE, outline="")

    canvas.bind("<Configure>", _draw)
    canvas.after(50, _draw)


def show_popup(stats: dict):
    try:
        if _popup_ref[0] and _popup_ref[0].winfo_exists():
            _popup_ref[0].lift()
            return
    except Exception:
        _popup_ref[0] = None

    win = tk.Tk()
    win.title("")
    win.configure(bg=BG)
    win.resizable(False, False)
    win.attributes("-topmost", True)
    win.overrideredirect(True)

    content = tk.Frame(win, bg=BG)
    content.pack()

    header = tk.Frame(content, bg=BG)
    header.pack(fill="x", padx=16, pady=(14, 10))
    tk.Label(header, text="Usage summary", bg=BG, fg=TEXT,
             font=("Segoe UI", 10, "bold")).pack(side="left")
    tk.Label(header, text=_fmt_updated(stats.get("fetched_at")), bg=BG, fg=TEXT_DIM,
             font=("Segoe UI", 8)).pack(side="right")
    tk.Frame(content, bg=BAR_BG, height=1).pack(fill="x", padx=16, pady=(0, 10))

    for label, key_pct, key_reset, fmt_reset, bottom_pad in [
        ("Session",      "utilization_5h",     "resets_at_5h",     _fmt_resets_in, 10),
        ("Weekly (All)", "utilization_weekly",  "resets_at_weekly", _fmt_resets_day, 14),
    ]:
        ratio = stats.get(key_pct, 0.0)
        row = tk.Frame(content, bg=BG)
        row.pack(fill="x", padx=16, pady=(0, 2))
        tk.Label(row, text=label, bg=BG, fg=TEXT,
                 font=("Segoe UI", 9, "bold")).pack(side="left")
        tk.Label(row, text=fmt_reset(stats.get(key_reset)), bg=BG, fg=TEXT_DIM,
                 font=("Segoe UI", 8)).pack(side="right")
        _usage_bar(content, ratio)
        tk.Label(content, text=f"{int(ratio * 100)}%", bg=BG, fg=TEXT_DIM,
                 font=("Segoe UI", 8)).pack(anchor="w", padx=16, pady=(2, bottom_pad))

    tk.Frame(content, bg=BAR_BG, height=1).pack(fill="x", padx=16, pady=(0, 8))
    tk.Button(content, text="✕  閉じる", command=win.destroy,
              bg=BG, fg=TEXT_DIM, relief="flat", font=("Segoe UI", 8),
              activebackground=BG_CARD, cursor="hand2", bd=0).pack(pady=(0, 10))

    win.update_idletasks()
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    w, h = win.winfo_reqwidth(), win.winfo_reqheight()
    win.geometry(f"{w}x{h}+{sw - w - 16}+{sh - h - 56}")

    win.bind("<Escape>", lambda e: win.destroy())
    win.bind("<FocusOut>", lambda e: win.after(100, lambda: win.destroy() if not win.focus_get() else None))

    _popup_ref[0] = win
    win.mainloop()
    _popup_ref[0] = None


def run_tray(on_quit=None):
    stats: dict = {}
    lock = threading.Lock()
    tray_icon = None

    def poll_loop():
        while True:
            new_stats = server.get_last_data()
            if new_stats:
                with lock:
                    stats.update(new_stats)
                _refresh_icon()
            time.sleep(POLL_INTERVAL)

    def _refresh_icon():
        if not tray_icon:
            return
        with lock:
            r5 = stats.get("utilization_5h")
            rw = stats.get("utilization_weekly", 0.0)
            reset_5h = stats.get("resets_at_5h")
        tooltip = (
            "Claude Usage — データ待機中" if r5 is None else
            f"Session: {int(r5*100)}%  {_fmt_resets_in(reset_5h)}\n"
            f"Weekly: {int(rw*100)}%"
        )
        tray_icon.icon = make_icon(r5)
        tray_icon.title = tooltip

    def on_click(icon, button):
        try:
            if _popup_ref[0] and _popup_ref[0].winfo_exists():
                _popup_ref[0].destroy()
                return
        except Exception:
            _popup_ref[0] = None
        with lock:
            s = dict(stats)
        threading.Thread(target=show_popup, args=(s,), daemon=True).start()

    def _quit_handler(icon, _):
        if on_quit:
            on_quit()
        icon.stop()

    tray_icon = pystray.Icon(
        "claude_usage",
        make_icon(None),
        title="Claude Usage",
        menu=pystray.Menu(
            item("詳細を表示", on_click, default=True),
            item("終了", _quit_handler),
        ),
    )

    threading.Thread(target=poll_loop, daemon=True).start()
    tray_icon.run()
