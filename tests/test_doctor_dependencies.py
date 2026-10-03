"""Exercise doctor against source declarations and installed package metadata."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DoctorDependencyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.root = self.base / "distribution"
        self.cwd = self.base / "elsewhere"
        self.cwd.mkdir()
        shutil.copytree(Path(__file__).resolve().parents[1] / "raradio", self.root / "raradio",
                        ignore=shutil.ignore_patterns("__pycache__"))
        # The working directory must never decide which dependency pin is used.
        (self.cwd / "pyproject.toml").write_text(
            '[project]\nname = "unrelated"\n[project.optional-dependencies]\nmlx = ["mlx-audio==1.0.0"]\n',
            encoding="utf-8")

    def source_requirement(self, requirement):
        (self.root / "pyproject.toml").write_text(
            '[project]\nname = "raradio"\n[project.optional-dependencies]\n'
            f'mlx = [{json.dumps(requirement)}]\n', encoding="utf-8")

    def installed_requirement(self, requirement):
        metadata = self.root / "raradio-0.1.0.dist-info"
        metadata.mkdir()
        (metadata / "METADATA").write_text(
            'Metadata-Version: 2.4\nName: raradio\nVersion: 0.1.0\nProvides-Extra: mlx\n'
            f'Requires-Dist: {requirement}\n', encoding="utf-8")

    def doctor(self, installed, profile="mlx"):
        script = f'''
from unittest.mock import patch
from raradio.cli import main
with patch("raradio.cli.platform.system", return_value="Darwin"), \\
     patch("raradio.cli.platform.machine", return_value="arm64"), \\
     patch("raradio.cli.platform.mac_ver", return_value=("14.0", ("", "", ""), "")), \\
     patch("raradio.cli.importlib.metadata.version", return_value={installed!r}):
    raise SystemExit(main(["doctor", "--profile", {profile!r}]))
'''
        result = subprocess.run([sys.executable, "-S", "-c", script], cwd=self.cwd,
                                env={**os.environ, "PYTHONPATH": str(self.root)},
                                capture_output=True, text=True)
        self.assertEqual(result.stderr, "")
        return result.returncode, json.loads(result.stdout)

    def test_source_upgrade_updates_acceptance_rejection_and_hint(self):
        # Editable-install metadata can lag behind a freshly updated checkout.
        self.installed_requirement('mlx-audio[tts]==1.0.0; extra == "mlx"')
        for version in ("9.8.7", "10.0.0rc1"):
            with self.subTest(version=version):
                self.source_requirement(f'mlx-audio[tts]=={version}; sys_platform == "darwin"')
                code, report = self.doctor(version)
                self.assertEqual(code, 0)
                self.assertTrue(report["ready"])
                code, report = self.doctor("1.0.0")
                self.assertEqual(code, 1)
                failures = [check for check in report["checks"] if not check["ok"]]
                self.assertEqual([check["name"] for check in failures], ["mlx_audio"])
                self.assertIn(version, failures[0]["hint"])
                self.assertIn("setup.sh mlx", failures[0]["hint"])

    def test_installed_package_uses_generated_dependency_metadata(self):
        self.installed_requirement('mlx-audio[tts]==9.8.7; sys_platform == "darwin" and extra == "mlx"')
        code, report = self.doctor("9.8.7")
        self.assertEqual(code, 0)
        self.assertTrue(report["ready"])
        code, report = self.doctor("1.0.0")
        self.assertEqual(code, 1)
        self.assertIn("9.8.7", report["checks"][-1]["hint"])

    def test_unrelated_parent_pyproject_does_not_override_package_metadata(self):
        self.installed_requirement('mlx-audio[tts]==9.8.7; extra == "mlx"')
        shutil.copy(self.cwd / "pyproject.toml", self.root / "pyproject.toml")
        code, report = self.doctor("9.8.7")
        self.assertEqual(code, 0)
        self.assertTrue(report["ready"])

    def test_invalid_source_pin_fails_with_json_instead_of_accepting_installed_version(self):
        self.installed_requirement('mlx-audio[tts]==9.8.7; extra == "mlx"')
        for requirement in ("other==9.8.7", "mlx-audio>=9", "mlx-audio==9.*"):
            with self.subTest(requirement=requirement):
                self.source_requirement(requirement)
                code, report = self.doctor("9.8.7")
                self.assertEqual(code, 1)
                self.assertFalse(report["ready"])
                self.assertIn("pin", report["checks"][-1]["hint"])

    def test_malformed_source_metadata_preserves_diagnostic_json(self):
        for metadata in (
            "[invalid",
            'project = "broken"',
            '[project]\nname = "raradio"\noptional-dependencies = 123',
            '[project]\nname = "raradio"\n[project.optional-dependencies]\nmlx = [123]',
        ):
            with self.subTest(metadata=metadata):
                (self.root / "pyproject.toml").write_text(metadata, encoding="utf-8")
                code, report = self.doctor("9.8.7")
                self.assertEqual(code, 1)
                self.assertFalse(report["ready"])
                self.assertIn("pin", report["checks"][-1]["hint"])

    def test_missing_declaration_does_not_pass_when_dependency_is_also_missing(self):
        code, report = self.doctor(None)
        self.assertEqual(code, 1)
        self.assertFalse(report["ready"])
        self.assertIn("pin", report["checks"][-1]["hint"])

    def test_core_doctor_does_not_require_optional_dependency_metadata(self):
        code, report = self.doctor(None, profile="core")
        self.assertEqual(code, 0)
        self.assertTrue(report["ready"])


if __name__ == "__main__":
    unittest.main()
