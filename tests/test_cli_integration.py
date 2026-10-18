"""Exercise the portable installed CLI through a realistic fix/verify/deliver cycle."""
import base64
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from harnesskit.cli import restore
from harnesskit.install import install
from harnesskit.storage import HarnessError, apply, atomic, encoded, read_json
from harnesskit.tasks import check, new_task


class IntegrationTest(unittest.TestCase):
    def test_installed_cli_end_to_end_with_spaces(self):
        checkout = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix="harness project ") as folder:
            project = Path(folder)

            def command(*args, expected=0, installed=True):
                script = project / ".harness/run.py" if installed else checkout / "harness.py"
                prefix = [] if installed else ["--project", str(project)]
                result = subprocess.run([sys.executable, str(script), *prefix, *args],
                                        cwd=tempfile.gettempdir(), capture_output=True, text=True)
                self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
                return json.loads(result.stdout)

            command("init", "--tools", "codex", installed=False)
            (project / "calc.py").write_text("def add(a, b):\n    return a - b\n")
            (project / "repair.py").write_text(
                "from pathlib import Path\nimport sys\n"
                "assert 'addition' in Path(sys.argv[1]).read_text(encoding='utf-8')\n"
                "Path('calc.py').write_text('def add(a, b):\\n    return a + b\\n')\n")
            config = {"schema_version": 1, "gates": [{"name": "regression", "argv": [
                sys.executable, "-B", "-c", "from calc import add; assert add(1, 2) == 3"]}]}
            atomic(project, ".harness/config.json", encoded(config))
            command("task", "new", "bugfix", "修复加法", "--id", "addition", "--accept", "1 + 2 = 3")
            baseline = command("check", "addition", expected=1)
            self.assertFalse(baseline["passed"])
            result = command("loop", "addition", "--worker", json.dumps([sys.executable, "repair.py", "{prompt}"]))
            self.assertEqual(result["reason"], "checks_passed")
            completed = command("task", "finish", "addition", "--summary", "复现失败并验证修复，符合验收")
            self.assertEqual(completed["status"], "done")
            command("upgrade", installed=False)
            self.assertEqual(command("status")["drift"], [])
            self.assertTrue((project / ".harness/tasks/addition/delivery.md").exists())

    def test_in_process_install_failure_rolls_back(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            atomic(root, "one.txt", b"old one")
            atomic(root, "two.txt", b"old two")
            original_atomic = atomic
            failed = False

            def fail_once(target, name, data):
                nonlocal failed
                if name == "two.txt" and not failed:
                    failed = True
                    raise OSError("simulated write failure")
                return original_atomic(target, name, data)

            with patch("harnesskit.storage.atomic", side_effect=fail_once):
                with self.assertRaises(OSError):
                    apply(root, {"one.txt": b"new one", "two.txt": b"new two"})
            self.assertEqual((root / "one.txt").read_bytes(), b"old one")
            self.assertEqual((root / "two.txt").read_bytes(), b"old two")

    def test_restore_can_handle_partially_applied_upgrade(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            install(root, ["codex"])
            (root / ".harness/roles/qa.md").write_text("local customization")
            result = install(root, ["claude"], upgrade=True, replace_modified=True)
            backup = read_json(root, f".harness/backups/{result['backup_id']}.json")
            name = ".harness/roles/qa.md"
            # Simulate a file that was still old when a multi-file write stopped.
            atomic(root, name, base64.b64decode(backup["files"][name]["before"]))
            restore(root, result["backup_id"])
            self.assertEqual((root / name).read_text(), "local customization")
            self.assertFalse((root / "CLAUDE.md").exists())

    def test_gate_timeout_is_recorded_as_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            install(root, ["codex"])
            new_task(root, "quick", "timeout test", "timeout")
            atomic(root, ".harness/config.json", encoded({"schema_version": 1, "gates": [
                {"name": "timeout", "argv": [sys.executable, "-c", "import time; time.sleep(10)"],
                 "timeout_seconds": 1}]}))
            result = check(root, "timeout")
            self.assertFalse(result["passed"])
            self.assertTrue(result["gates"][0]["timed_out"])

    def test_malformed_manifest_has_actionable_error(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            atomic(root, ".harness/manifest.json", b"[]")
            with self.assertRaises(HarnessError):
                install(root, None, upgrade=True)
