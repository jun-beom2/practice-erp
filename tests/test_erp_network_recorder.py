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
