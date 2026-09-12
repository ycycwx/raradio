"""The source runner obeys the installed CLI's path and exit-code contract."""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class RunnerTests(unittest.TestCase):
    def test_runner_builds_relative_to_caller_even_with_spaces_in_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            checkout = base / "source checkout"
            caller = base / "my books"
            checkout.mkdir()
            caller.mkdir()
            root = Path(__file__).resolve().parents[1]
            shutil.copyfile(root / "run.sh", checkout / "run.sh")
            shutil.copytree(root / "raradio", checkout / "raradio", ignore=shutil.ignore_patterns("__pycache__"))
            # An isolated entry point avoids requiring uv or touching the user's .venv.
            entry = checkout / ".venv" / "bin" / "raradio"
            entry.parent.mkdir(parents=True)
            entry.write_text(
                f"#!{sys.executable}\nimport sys\nsys.path.insert(0, {str(checkout)!r})\n"
                "from raradio.cli import main\nraise SystemExit(main())\n",
                encoding="utf-8",
            )
            entry.chmod(0o755)
            (caller / "story.txt").write_text("A small test. “A second line.”\n", encoding="utf-8")
            (caller / "cast.json").write_text(json.dumps({
                "characters": {"narrator": {"name": "Narrator", "voice": "reader", "confirmed": True}},
                "voices": {"reader": {"backend": "tone"}},
            }), encoding="utf-8")
            command = ["sh", str(checkout / "run.sh"), "build", "story.txt", "--work", "book",
                       "--cast", "cast.json", "--analyzer", "single-voice", "--output", "export"]
            first = subprocess.run([*command, "--limit", "1"], cwd=caller, capture_output=True, text=True)
            self.assertEqual(first.returncode, 2, first.stderr)
            self.assertEqual(json.loads(first.stdout)["remaining"], 1)
            complete = subprocess.run(command, cwd=caller, capture_output=True, text=True)
            self.assertEqual(complete.returncode, 0, complete.stderr)
            self.assertEqual(json.loads(complete.stdout)["remaining"], 0)
            self.assertTrue((caller / "export" / "manifest.json").is_file())
            self.assertFalse((checkout / "book").exists())


if __name__ == "__main__":
    unittest.main()
