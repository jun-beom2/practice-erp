import importlib.util
import json
import socket
import threading
import urllib.error
import urllib.request
from pathlib import Path
import unittest

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]


def load_proxy_server():
    spec = importlib.util.spec_from_file_location("proxy_server", ROOT / "proxy_server.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class PracticeErpTrainingTests(unittest.TestCase):
    def test_proxy_orders_and_delivery_post_are_available(self):
        module = load_proxy_server()
        port = free_port()
        server = module.make_server("127.0.0.1", port)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/proxy/orders", timeout=3) as response:
                self.assertEqual(response.status, 200)
                orders_payload = json.loads(response.read().decode("utf-8"))

            self.assertEqual(orders_payload["건수"], len(orders_payload["orders"]))
            self.assertGreater(len(orders_payload["orders"]), 0)

            delivery = {
                "발주번호": orders_payload["orders"][0]["발주번호"],
                "거래처": orders_payload["orders"][0]["거래처"],
                "납품수량": 3,
                "연습용": True,
            }
            request = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/deliveries",
                data=json.dumps(delivery).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            with urllib.request.urlopen(request, timeout=3) as response:
                self.assertEqual(response.status, 200)
                save_payload = json.loads(response.read().decode("utf-8"))

            self.assertTrue(save_payload["ok"])
            self.assertEqual(save_payload["received"]["납품수량"], 3)
            self.assertFalse((ROOT / "api" / "deliveries.json").exists())
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_delivery_post_is_reflected_in_subsequent_order_lookup(self):
        module = load_proxy_server()
        port = free_port()
        server = module.make_server("127.0.0.1", port)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/proxy/orders", timeout=3) as response:
                before_payload = json.loads(response.read().decode("utf-8"))

            order = before_payload["orders"][0]
            delivery = {
                "발주번호": order["발주번호"],
                "거래처": order["거래처"],
                "납품수량": 3,
                "연습용": True,
            }
            request = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/deliveries",
                data=json.dumps(delivery).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=3) as response:
                save_payload = json.loads(response.read().decode("utf-8"))

            with urllib.request.urlopen(f"http://127.0.0.1:{port}/proxy/orders", timeout=3) as response:
                after_payload = json.loads(response.read().decode("utf-8"))

            updated = next(x for x in after_payload["orders"] if x["발주번호"] == order["발주번호"])
            self.assertTrue(save_payload["persisted"])
            self.assertEqual(updated["납품수량"], 3)
            self.assertEqual(updated["잔량"], order["발주수량"] - 3)
            self.assertEqual(updated["상태"], "부분납품")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_html_teaches_proxy_and_has_stable_rpa_targets(self):
        index_html = (ROOT / "index.html").read_text(encoding="utf-8")
        input_html = (ROOT / "input.html").read_text(encoding="utf-8")

        self.assertIn("fetch('./proxy/orders'", index_html)
        self.assertIn('data-testid="search-button"', index_html)
        self.assertIn('data-testid="vendor-filter"', index_html)
        self.assertIn("applyFilters(data.orders)", index_html)
        self.assertIn("sessionStorage.setItem('ordersSearched', '1')", index_html)
        self.assertIn("sessionStorage.getItem('ordersSearched') === '1'", index_html)
        self.assertIn("o.납품수량", index_html)
        self.assertIn("o.잔량", index_html)

        self.assertIn("fetch('./proxy/orders'", input_html)
        self.assertIn('data-testid="delivery-qty"', input_html)
        self.assertIn('data-testid="save-button"', input_html)
        self.assertIn("fetch('./api/deliveries'", input_html)
        self.assertNotIn("confirm(", input_html)
        self.assertIn("sessionStorage.setItem('ordersSearched', '1')", input_html)

    def test_delivery_input_save_shows_success_message_without_native_confirm(self):
        module = load_proxy_server()
        port = free_port()
        server = module.make_server("127.0.0.1", port)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                try:
                    page = browser.new_page()
                    dialogs = []
                    page.on("dialog", lambda dialog: (dialogs.append(dialog.message), dialog.dismiss()))
                    page.goto(f"http://127.0.0.1:{port}/input.html?po=PO-2026-0522", wait_until="domcontentloaded")
                    page.locator('[data-testid="delivery-qty"]').fill("7")
                    page.locator('[data-testid="save-button"]').click()
                    page.wait_for_function(
                        "document.querySelector('#saved').textContent.includes('연습용 저장 요청')",
                        timeout=3000,
                    )

                    self.assertEqual(dialogs, [])
                finally:
                    browser.close()

            with urllib.request.urlopen(f"http://127.0.0.1:{port}/proxy/orders", timeout=3) as response:
                after_payload = json.loads(response.read().decode("utf-8"))

            updated = next(x for x in after_payload["orders"] if x["발주번호"] == "PO-2026-0522")
            self.assertEqual(updated["납품수량"], 7)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
