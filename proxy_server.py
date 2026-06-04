from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import sys
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent
ORDERS_PATH = ROOT / "api" / "orders.json"


class PracticeERPHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/proxy/orders":
            self._send_json(json.loads(ORDERS_PATH.read_text(encoding="utf-8")))
            return
        super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        if path != "/api/deliveries":
            self.send_error(404, "Not Found")
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            payload = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self._send_json({"ok": False, "error": "invalid_json"}, status=400)
            return

        qty = payload.get("납품수량")
        if not isinstance(qty, (int, float)) or qty <= 0:
            self._send_json({"ok": False, "error": "invalid_qty"}, status=400)
            return

        self._send_json({
            "ok": True,
            "message": "practice_delivery_received",
            "persisted": False,
            "received": payload,
        })

    def _send_json(self, payload, status=200):
        raw = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def make_server(host="127.0.0.1", port=8000):
    return ThreadingHTTPServer((host, port), PracticeERPHandler)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    server = make_server("127.0.0.1", port)
    print(f"연습 ERP 프록시 서버 실행: http://localhost:{port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n서버를 종료합니다.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
