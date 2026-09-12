"""Agent instructions are discoverable without models or project side effects."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from raradio import __version__


class AgentGuideTests(unittest.TestCase):
    def test_agent_guide_exports_an_installable_skill_offline(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = subprocess.run(
                [sys.executable, "-m", "raradio", "agent-guide"],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            skill = Path(temporary) / "raradio-audiobook" / "SKILL.md"
            skill.parent.mkdir()
            skill.write_text(result.stdout, encoding="utf-8")
            self.assertTrue(skill.read_text().startswith("---\nname: raradio-audiobook\n"))
            self.assertIn("raradio resolve", result.stdout)
            self.assertEqual(result.stderr, "")

    def test_json_discovery_carries_the_same_skill_and_current_version(self):
        command = [sys.executable, "-m", "raradio", "agent-guide"]
        structured = subprocess.run([*command, "--format", "json"], capture_output=True, text=True)
        self.assertEqual(structured.returncode, 0, structured.stderr)
        data = json.loads(structured.stdout)
        plain = subprocess.run(command, capture_output=True, text=True, check=True)
        self.assertEqual(data["raradio_version"], __version__)
        self.assertEqual(data["skill_name"], "raradio-audiobook")
        self.assertEqual(data["skill_markdown"], plain.stdout)


if __name__ == "__main__":
    unittest.main()
