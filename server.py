import json
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional

PORT = 9876
_last_data: dict = {}
_lock = threading.Lock()


def get_last_data() -> dict:
    with _lock:
        return dict(_last_data)


def _parse_ts(ts_str) -> Optional[datetime]:
    if not ts_str:
        return None
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except ValueError:
        return None


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/usage":
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            raw = json.loads(body)
            parsed = {
                "utilization_5h":     raw["five_hour"]["utilization"] / 100,
                "resets_at_5h":       _parse_ts(raw["five_hour"]["resets_at"]),
                "utilization_weekly": raw["seven_day"]["utilization"] / 100,
                "resets_at_weekly":   _parse_ts(raw["seven_day"]["resets_at"]),
                "fetched_at":         datetime.now(timezone.utc),
            }
            with _lock:
                _last_data.update(parsed)
        except Exception:
            pass
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        # Claude Codeのフック（usage-guard.js）が使用率を照会するためのエンドポイント
        if self.path != "/usage":
            self.send_response(404)
            self.end_headers()
            return
        data = get_last_data()
        body = json.dumps(
            data,
            default=lambda o: o.isoformat() if isinstance(o, datetime) else str(o),
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def start() -> HTTPServer:
    httpd = HTTPServer(("localhost", PORT), _Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd
