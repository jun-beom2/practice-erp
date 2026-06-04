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
            self._send_json(self._orders_with_deliveries())
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

        po = payload.get("발주번호")
        orders = {o["발주번호"]: o for o in self._base_orders()["orders"]}
        if po not in orders:
            self._send_json({"ok": False, "error": "unknown_order"}, status=404)
            return

        current = self.server.deliveries.get(po, 0)
        ordered_qty = orders[po]["발주수량"]
        self.server.deliveries[po] = min(current + qty, ordered_qty)

        self._send_json({
            "ok": True,
            "message": "practice_delivery_received",
            "persisted": True,
            "received": payload,
            "납품누계": self.server.deliveries[po],
        })

    def _base_orders(self):
        return json.loads(ORDERS_PATH.read_text(encoding="utf-8"))

    def _orders_with_deliveries(self):
        payload = self._base_orders()
        for order in payload["orders"]:
            delivered = self.server.deliveries.get(order["발주번호"], 0)
            ordered = order["발주수량"]
            order["납품수량"] = delivered
            order["잔량"] = max(ordered - delivered, 0)
            if delivered >= ordered:
                order["상태"] = "납품완료"
            elif delivered > 0:
                order["상태"] = "부분납품"
        return payload

    def _send_json(self, payload, status=200):
        raw = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def make_server(host="127.0.0.1", port=8000):
    server = ThreadingHTTPServer((host, port), PracticeERPHandler)
    server.deliveries = {}
    return server


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
