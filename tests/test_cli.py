import json
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from contextlib import redirect_stdout, redirect_stderr
from http.client import BadStatusLine, IncompleteRead
from unittest.mock import patch
from urllib.error import URLError


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.work = self.base / "book"
        self.source = self.base / "story.txt"
        self.source.write_text("窗外下着雨。", encoding="utf-8")
        self.cast = self.base / "cast.json"
        self.cast.write_text(json.dumps({"characters": {"narrator": {"name": "旁白", "confirmed": True, "voice": "n"}},
                                         "voices": {"n": {"backend": "tone"}}}), encoding="utf-8")

    def cli(self, *arguments):
        return subprocess.run([sys.executable, "-m", "raradio", *map(str, arguments)], capture_output=True, text=True)

    def invoke_main(self, *arguments):
        from raradio.cli import main

        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            try:
                code = main(list(arguments))
            except SystemExit as exc:
                code = exc.code
        self.assertTrue(stdout.getvalue(), stderr.getvalue())
        return code, json.loads(stdout.getvalue()), stderr.getvalue()

    def invoke_text(self, *arguments):
        from raradio.cli import main

        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            try:
                code = main(list(arguments))
            except SystemExit as exc:
                code = exc.code
        self.assertTrue(stdout.getvalue(), stderr.getvalue())
        return code, stdout.getvalue(), stderr.getvalue()

    def test_version_can_be_read_without_a_command(self):
        from raradio import __version__

        result = self.cli("--version")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), f"raradio {__version__}")

    def test_core_doctor_checks_offline_requirements_without_contacting_ollama(self):
        with patch("raradio.cli.urlopen", side_effect=AssertionError("Offline doctor contacted a service")):
            code, result, stderr = self.invoke_main("doctor")
        self.assertEqual(code, 0, stderr)
        self.assertEqual(result["profile"], "core")
        self.assertTrue(result["ready"])
        self.assertNotIn("ollama_models", result)

    def test_mlx_doctor_rejects_unsupported_hardware_even_if_package_is_installed(self):
        with patch("raradio.cli.platform.system", return_value="Linux"), \
             patch("raradio.cli.importlib.metadata.version", return_value="0.5.3"):
            code, result, _ = self.invoke_main("doctor", "--profile", "mlx")
        self.assertEqual(code, 1)
        self.assertFalse(result["ready"])
        failures = [check for check in result["checks"] if not check["ok"]]
        self.assertIn("Apple Silicon", failures[0]["hint"])

    def test_mlx_doctor_missing_dependency_explains_install_and_scope(self):
        import importlib.metadata

        with patch("raradio.cli.platform.system", return_value="Darwin"), \
             patch("raradio.cli.platform.machine", return_value="arm64"), \
             patch("raradio.cli.platform.mac_ver", return_value=("14.0", ("", "", ""), "")), \
             patch("raradio.cli.importlib.metadata.version", side_effect=importlib.metadata.PackageNotFoundError):
            code, result, _ = self.invoke_main("doctor", "--profile", "mlx")
        self.assertEqual(code, 1)
        failures = [check for check in result["checks"] if not check["ok"]]
        self.assertIn("setup.sh mlx", failures[0]["hint"])
        self.assertIn("model", result["scope"])

    def test_ollama_doctor_uses_selected_service_and_normalizes_latest_tag(self):
        requested = []

        def response(url, timeout):
            requested.append(url)
            return io.BytesIO(b'{"models": [{"name": "tiny:latest"}]}')

        with patch("raradio.cli.urlopen", side_effect=response):
            code, result, stderr = self.invoke_main("doctor", "--profile", "ollama", "--model", "tiny",
                                                    "--ollama-url", "http://example.test:1234/")
        self.assertEqual(code, 0, stderr)
        self.assertTrue(result["ready"])
        self.assertEqual(requested, ["http://example.test:1234/api/tags"])
        self.assertEqual(result["ollama_models"], ["tiny:latest"])

    def test_ollama_doctor_failures_keep_json_output_and_give_next_step(self):
        responses = [URLError("Connection refused"), IncompleteRead(b'{"models":', 30), BadStatusLine("bad status"),
                     b'{"models": null}', b'{"models": []}']
        for response in responses:
            with self.subTest(response=response):
                options = {"side_effect": response} if isinstance(response, Exception) else {"return_value": io.BytesIO(response)}
                with patch("raradio.cli.urlopen", **options):
                    code, result, stderr = self.invoke_main("doctor", "--profile", "ollama")
                self.assertEqual(code, 1, stderr)
                self.assertFalse(result["ready"])
                self.assertTrue(all(check.get("hint") for check in result["checks"] if not check["ok"]))

    def test_setup_defaults_to_single_voice_and_does_not_require_ollama(self):
        mlx_report = {"profile": "mlx", "ready": True, "checks": []}
        with patch("raradio.cli._doctor", return_value=mlx_report) as doctor:
            code, output, stderr = self.invoke_text("setup")
        self.assertEqual(code, 0, stderr)
        doctor.assert_called_once_with("mlx", "http://localhost:11434", "qwen3:14b")
        self.assertIn("Single voice", output)
        self.assertIn("Ollama: not required", output)
        self.assertIn("does not install", output)
        self.assertIn("first speech generation", output)

    def test_setup_missing_speech_dependencies_gives_source_setup_path(self):
        mlx_report = {"profile": "mlx", "ready": False, "checks": [
            {"name": "mlx_audio", "ok": False, "detail": None, "hint": "Install speech support."}
        ]}
        with patch("raradio.cli._doctor", return_value=mlx_report):
            code, output, stderr = self.invoke_text("setup")
        self.assertEqual(code, 1, stderr)
        self.assertIn("sh setup.sh mlx", output)
        self.assertNotIn("PyPI", output)
        self.assertNotIn("uv tool install", output)

    def test_setup_unsupported_platform_does_not_recommend_installing_mlx(self):
        import importlib.metadata

        with patch("raradio.cli.platform.system", return_value="Linux"), \
             patch("raradio.cli.platform.machine", return_value="x86_64"), \
             patch("raradio.cli.importlib.metadata.version", side_effect=importlib.metadata.PackageNotFoundError):
            code, output, stderr = self.invoke_text("setup")
        self.assertEqual(code, 1, stderr)
        self.assertIn("Apple Silicon Mac", output)
        self.assertNotIn("uv tool install", output)
        self.assertNotIn("setup.sh mlx", output)

    def test_setup_multi_voice_checks_ollama_and_can_emit_json(self):
        reports = {
            "mlx": {"profile": "mlx", "ready": True, "checks": []},
            "ollama": {"profile": "ollama", "ready": True, "checks": [], "model": "small:latest"},
        }
        with patch("raradio.cli._doctor", side_effect=lambda profile, *_: reports[profile]) as doctor:
            code, result, stderr = self.invoke_main(
                "setup", "--mode", "multi-voice", "--format", "json",
                "--ollama-url", "http://example.test:1234", "--model", "small:latest",
            )
        self.assertEqual(code, 0, stderr)
        self.assertTrue(result["ready"])
        self.assertTrue(result["requires_ollama"])
        self.assertEqual(set(result["profiles"]), {"mlx", "ollama"})
        self.assertEqual(doctor.call_count, 2)
        doctor.assert_any_call("ollama", "http://example.test:1234", "small:latest")

    def test_interrupted_ollama_response_is_saved_for_review(self):
        from raradio.project import BookProject

        project = BookProject.create(self.source, self.work)
        with patch("raradio.analysis.urlopen", side_effect=IncompleteRead(b'{"done":', 92)):
            code, result, stderr = self.invoke_main("analyze", str(self.work))
        self.assertEqual(code, 0, stderr)
        self.assertEqual(result["counts"], {"NEEDS_REVIEW": 1})
        self.assertIn("analysis: Ollama request failed", project.review()[0]["issue"])
        self.assertIn("could not unload Ollama model", stderr)
        self.assertNotIn("Traceback", stderr)

    def test_ollama_doctor_invalid_port_reports_json_without_traceback(self):
        result = self.cli("doctor", "--profile", "ollama", "--ollama-url", "http://localhost:bogus")
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("Traceback", result.stderr)
        report = json.loads(result.stdout)
        self.assertFalse(report["ready"])
        self.assertIn("Ollama base_url", report["ollama_error"])

    def test_invalid_numeric_build_options_fail_before_creating_a_project(self):
        for index, (option, value) in enumerate([("--max-chars", "0"), ("--limit", "0"), ("--max-attempts", "-1"),
                                                ("--timeout", "nan"), ("--timeout", "inf"), ("--batch-size", "0")]):
            with self.subTest(option=option, value=value):
                work = self.base / f"invalid-{index}"
                result = self.cli("build", self.source, "--work", work, "--analyzer", "rules", option, value)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertFalse(work.exists())
                self.assertIn(option, result.stderr)
                self.assertNotIn("Traceback", result.stderr)

    def test_negative_export_pause_is_an_argument_error_before_opening_the_project(self):
        result = self.cli("export", self.work, "--output", self.base / "export", "--pause-ms", "-1")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("--pause-ms", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertFalse((self.base / "export").exists())

    def test_corrupt_project_metadata_and_database_errors_are_concise(self):
        self.assertEqual(self.cli("init", self.source, "--work", self.work).returncode, 0)
        metadata_path = self.work / "project.json"
        original = metadata_path.read_bytes()
        for metadata in [[], {"schema_version": 1}, {"schema_version": 2}]:
            with self.subTest(metadata=metadata):
                metadata_path.write_text(json.dumps(metadata))
                result = self.cli("status", self.work)
                self.assertEqual(result.returncode, 1)
                self.assertNotIn("Traceback", result.stderr)
                self.assertIn("project", result.stderr.lower())
        metadata_path.write_bytes(original)
        (self.work / "state.sqlite3").write_bytes(b"not a database")
        result = self.cli("status", self.work)
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn("database", result.stderr)

    def test_unsupported_file_locking_keeps_help_usable_and_reports_a_clear_error(self):
        # Simulate the missing POSIX module before importing the application.
        script = "import sys, runpy; sys.modules['fcntl'] = None; runpy.run_module('raradio', run_name='__main__')"
        for arguments, expected in [(["--help"], 0), (["--version"], 0), (["doctor"], 1),
                                    (["init", str(self.source), "--work", str(self.work)], 1)]:
            with self.subTest(arguments=arguments):
                result = subprocess.run([sys.executable, "-c", script, *arguments], capture_output=True, text=True)
                self.assertEqual(result.returncode, expected, result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                if arguments[0] in {"doctor", "init"}:
                    self.assertIn("POSIX", result.stdout + result.stderr)
        self.assertFalse(self.work.exists())

    def test_build_is_one_command_and_second_run_reuses_audio(self):
        args = ("build", self.source, "--work", self.work, "--cast", self.cast, "--analyzer", "rules", "--output", self.base / "export")
        first = self.cli(*args)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(json.loads(first.stdout)["counts"], {"DONE": 1})
        files = list((self.work / "audio").glob("*.wav"))
        modified = files[0].stat().st_mtime_ns
        self.assertEqual(self.cli(*args).returncode, 0)
        self.assertEqual(files[0].stat().st_mtime_ns, modified)
        self.assertTrue((self.base / "export" / "manifest.json").is_file())

    def test_single_voice_build_reads_quoted_dialogue_and_exports_without_review(self):
        self.source.write_text("窗外下着雨。“你好。”", encoding="utf-8")
        result = self.cli("build", self.source, "--work", self.work, "--cast", self.cast,
                          "--analyzer", "single-voice", "--output", self.base / "export")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["counts"], {"DONE": 2})
        segments = json.loads(self.cli("segments", self.work).stdout)
        self.assertEqual([(s["text"], s["kind"], s["speaker_id"]) for s in segments],
                         [("窗外下着雨。", "narration", "narrator"), ("“你好。”", "dialogue", "narrator")])
        self.assertEqual(json.loads(self.cli("review", self.work).stdout), [])
        self.assertTrue((self.base / "export" / "manifest.json").is_file())
        self.assertTrue(list((self.base / "export").glob("*.wav")))
        self.assertTrue(list((self.base / "export").glob("*.srt")))

    def test_single_voice_analyze_and_build_do_not_contact_ollama(self):
        from raradio.cli import main
        from raradio.project import BookProject

        self.source.write_text("窗外下着雨。“你好。”", encoding="utf-8")
        for command, expected_status in [("analyze", "READY"), ("build", "DONE")]:
            with self.subTest(command=command):
                work = self.base / command
                project = BookProject.create(self.source, work)
                project.configure(json.loads(self.cast.read_text()))
                args = [command, str(work), "--analyzer", "single-voice"]
                if command == "build":
                    args = [command, str(self.source), "--work", str(work), "--analyzer", "single-voice"]
                stdout, stderr = io.StringIO(), io.StringIO()
                with patch("raradio.analysis.urlopen", side_effect=AssertionError("Ollama HTTP is forbidden")), \
                     patch("raradio.cli.urlopen", side_effect=AssertionError("Ollama HTTP is forbidden")), \
                     redirect_stdout(stdout), redirect_stderr(stderr):
                    code = main(args)
                self.assertEqual(code, 0, stderr.getvalue())
                self.assertEqual(json.loads(stdout.getvalue())["counts"], {expected_status: 2})

    def test_rules_build_keeps_quoted_dialogue_for_review(self):
        self.source.write_text("窗外下着雨。“你好。”", encoding="utf-8")
        result = self.cli("build", self.source, "--work", self.work, "--cast", self.cast,
                          "--analyzer", "rules", "--output", self.base / "export")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(json.loads(result.stdout)["counts"], {"DONE": 1, "NEEDS_REVIEW": 1})
        review = json.loads(self.cli("review", self.work).stdout)
        self.assertEqual([(s["text"], s["speaker_id"]) for s in review], [("“你好。”", None)])
        self.assertFalse((self.base / "export").exists())

    def test_unresolved_cast_is_reported_with_exit_two_and_no_export(self):
        result = self.cli("build", self.source, "--work", self.work, "--analyzer", "rules", "--output", self.base / "export")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(json.loads(result.stdout)["remaining"], 1)
        self.assertFalse((self.base / "export").exists())
        review = self.cli("review", self.work)
        self.assertEqual(review.returncode, 0, review.stderr)
        self.assertEqual(len(json.loads(review.stdout)), 1)

    def test_reusing_work_directory_for_different_source_is_refused(self):
        self.assertEqual(self.cli("init", self.source, "--work", self.work).returncode, 0)
        self.source.write_text("另一本完全不同的书。", encoding="utf-8")
        result = self.cli("build", self.source, "--work", self.work, "--analyzer", "rules")
        self.assertEqual(result.returncode, 1)
        self.assertIn("source", result.stderr.lower())

    def test_user_input_errors_are_concise_without_traceback(self):
        result = self.cli("status", self.work)
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("Traceback", result.stderr)

    def test_backend_loading_messages_do_not_corrupt_json_stdout(self):
        from raradio.cli import main
        from raradio.project import BookProject
        from raradio.analysis import RulesAnalyzer
        from tests.test_project import WaveBackend

        class NoisyBackend(WaveBackend):
            def synthesize(self, text, voice, emotion, output):
                print("Loading speech tokenizer")
                super().synthesize(text, voice, emotion, output)

        project = BookProject.create(self.source, self.work)
        project.analyze(RulesAnalyzer())
        project.configure(json.loads(self.cast.read_text()))
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch("raradio.backends.get_backend", return_value=NoisyBackend()), redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(["run", str(self.work)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout.getvalue())["remaining"], 0)
        self.assertIn("Loading speech tokenizer", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
