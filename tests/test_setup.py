import os
import json
from pathlib import Path
import shutil
import shlex
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        shutil.copy2(ROOT / "setup.sh", self.root / "setup.sh")
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.env = dict(os.environ, PATH=f"{self.bin}:/usr/bin:/bin")

    def executable(self, name, body):
        script = self.bin / name
        script.write_text(f"#!/bin/sh\nset -eu\n{body}\n", encoding="utf-8")
        script.chmod(0o755)

    def run_setup(self, *args):
        return subprocess.run(["/bin/sh", str(self.root / "setup.sh"), *args],
                              env=self.env, capture_output=True, text=True)

    def test_help_works_without_uv_or_environment_changes(self):
        result = self.run_setup("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("core|mlx", result.stdout)
        self.assertFalse((self.root / ".venv").exists())

    def test_mlx_rejects_old_macos_before_installing_packages(self):
        self.executable("uname", 'case "$1" in -s) echo Darwin;; -m) echo arm64;; esac')
        self.executable("sw_vers", "echo 13.7.6")
        self.executable("uv", 'touch sync-attempted; exit 77')
        result = self.run_setup("mlx")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("macOS 14", result.stderr)
        self.assertFalse((self.root / "sync-attempted").exists())

    def test_mlx_rejects_unsupported_hardware_before_install(self):
        self.executable("uname", 'case "$1" in -s) echo Linux;; -m) echo x86_64;; esac')
        self.executable("uv", 'touch sync-attempted; exit 77')
        result = self.run_setup("mlx")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("Apple Silicon", result.stderr)
        self.assertFalse((self.root / "sync-attempted").exists())

    def test_setup_owns_repository_environment_and_checks_installed_core(self):
        shutil.copytree(ROOT / "raradio", self.root / "raradio", ignore=shutil.ignore_patterns("__pycache__"))
        external = self.root / "another-environment"
        self.env["UV_PROJECT_ENVIRONMENT"] = str(external)
        # Replace only the package installer; run the real installed CLI/doctor.
        launcher = f"#!/bin/sh\nexec {shlex.quote(sys.executable)} -m raradio \"$@\"\n"
        self.executable("uv", 'mkdir -p "$UV_PROJECT_ENVIRONMENT/bin"\n'
                        f'cat > "$UV_PROJECT_ENVIRONMENT/bin/raradio" <<\'LAUNCHER\'\n{launcher}LAUNCHER\n'
                        'chmod +x "$UV_PROJECT_ENVIRONMENT/bin/raradio"')
        result = self.run_setup("core")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(external.exists())
        self.assertTrue((self.root / ".venv/bin/raradio").exists())
        report = json.loads(result.stdout)
        self.assertEqual(report["profile"], "core")
        self.assertTrue(report["ready"])


if __name__ == "__main__":
    unittest.main()
