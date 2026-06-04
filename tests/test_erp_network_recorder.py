import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RECORDER = ROOT / "tools" / "erp_network_recorder.py"
PROJECT_SKILL = ROOT / ".codex" / "skills" / "erp-network-recorder"


class ErpNetworkRecorderToolTests(unittest.TestCase):
    def test_help_command_is_available(self):
        result = subprocess.run(
            [sys.executable, str(RECORDER), "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Open a headed Playwright browser", result.stdout)
        self.assertIn("--include-document-body", result.stdout)

    def test_recorder_masks_sensitive_values_and_omits_document_bodies_by_default(self):
        source = RECORDER.read_text(encoding="utf-8")

        self.assertIn("SENSITIVE_RE", source)
        self.assertIn("mask_url", source)
        self.assertIn("bodyOmitted", source)
        self.assertIn("document body omitted", source)
        self.assertIn("REC Playwright Network", source)

    def test_recorder_installs_browser_fetch_and_xhr_capture(self):
        source = RECORDER.read_text(encoding="utf-8")

        self.assertIn("pwNetworkRecorderNetwork", source)
        self.assertIn("browser_request", source)
        self.assertIn("browser_response", source)
        self.assertIn("window.fetch", source)
        self.assertIn("XMLHttpRequest", source)

    def test_playwright_response_handler_does_not_read_body_in_event_callback(self):
        source = RECORDER.read_text(encoding="utf-8")

        self.assertNotIn("res.text()", source)
        self.assertIn("response body omitted to keep browser fetch non-blocking", source)

    def test_browser_fetch_response_logging_does_not_block_page_fetch(self):
        source = RECORDER.read_text(encoding="utf-8")

        self.assertNotIn("browser_response_body", source)
        self.assertNotIn("body: await responseText(response)", source)
        self.assertIn("sendNetwork(responsePayload);", source)

    def test_browser_network_binding_does_not_read_playwright_page_state(self):
        source = RECORDER.read_text(encoding="utf-8")
        network_handler = source.split("def on_browser_network", 1)[1].split("context.expose_binding", 1)[0]

        self.assertNotIn('source.get("page")', network_handler)
        self.assertIn("payload.pageUrl = location.href", source)

    def test_recorder_idle_loop_pumps_playwright_events(self):
        source = RECORDER.read_text(encoding="utf-8")

        self.assertIn("page.wait_for_timeout(1000)", source)
        self.assertNotIn("time.sleep(1)", source)

    def test_project_skill_bundles_the_recorder(self):
        skill_md = PROJECT_SKILL / "SKILL.md"
        skill_script = PROJECT_SKILL / "scripts" / "erp_network_recorder.py"
        skill_metadata = PROJECT_SKILL / "agents" / "openai.yaml"

        self.assertTrue(skill_md.exists())
        self.assertTrue(skill_script.exists())
        self.assertTrue(skill_metadata.exists())
        self.assertIn("name: erp-network-recorder", skill_md.read_text(encoding="utf-8"))
        self.assertEqual(RECORDER.read_text(encoding="utf-8"), skill_script.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
