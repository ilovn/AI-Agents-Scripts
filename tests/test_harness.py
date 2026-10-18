import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from harnesskit import SCHEMA_VERSION, __version__
from harnesskit.cli import main, restore
from harnesskit.install import doctor, install, status
from harnesskit.storage import HarnessError, atomic, encoded, locked, read_json
from harnesskit.tasks import accept, check, collect, delegate, finish, load_task, loop, new_task, task_path


class ProjectTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def setup_project(self, tools=None):
        return install(self.root, tools or ["codex"])

    def configure(self, code="pass", **settings):
        cfg = {"schema_version": SCHEMA_VERSION,
               "gates": [{"name": "test", "argv": [sys.executable, "-c", code], "timeout_seconds": 5}],
               "loop": {"max_rounds": 4, "timeout_seconds": 5, "stagnation_rounds": 1, **settings}}
        atomic(self.root, ".harness/config.json", encoded(cfg))

    def task(self, kind="quick", task_id="demo"):
        return new_task(self.root, kind, "可验证目标", task_id, ["观察预期结果"])

    def test_dry_run_does_not_create_target(self):
        target = self.root / "missing"
        result = install(target, ["codex"], dry_run=True)
        self.assertTrue(result["changed"])
        self.assertFalse(target.exists())

    def test_install_merges_existing_rules_and_portable_runtime(self):
        original = "# 团队规则\n\n使用现有测试约定。\n"
        (self.root / "AGENTS.md").write_text(original)
        self.setup_project(["codex", "claude", "opencode", "trae"])
        self.assertTrue((self.root / "AGENTS.md").read_text().startswith(original))
        self.assertTrue((self.root / ".claude/agents/harness-qa.md").exists())
        self.assertTrue((self.root / ".opencode/agents/harness-qa.md").exists())
        self.assertTrue((self.root / ".harness/adapters/trae.md").exists())
        result = subprocess.run([sys.executable, str(self.root / ".harness/run.py"), "status"],
                                cwd=tempfile.gettempdir(), capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["project_version"], __version__)

    def test_upgrade_is_idempotent_and_preserves_custom_files(self):
        self.setup_project()
        project = self.root / ".harness/project.md"
        project.write_text("团队维护的上下文")
        agents = self.root / "AGENTS.md"
        agents.write_text(agents.read_text() + "\n团队新增规则\n")
        result = install(self.root, None, upgrade=True)
        self.assertEqual(result["changed"], [])
        self.assertEqual(project.read_text(), "团队维护的上下文")
        self.assertIn("团队新增规则", agents.read_text())
        self.assertEqual(status(self.root)["drift"], [])

    def test_crlf_owned_blocks_are_canonical_and_real_edits_still_drift(self):
        self.setup_project()
        agents = self.root / "AGENTS.md"
        data = agents.read_bytes().replace(b"\n", b"\r\n")
        agents.write_bytes(data + b"\r\n\xe5\x9b\xa2\xe9\x98\x9f\xe8\xa7\x84\xe5\x88\x99\r\n")
        self.assertEqual(status(self.root)["drift"], [])
        self.assertEqual(install(self.root, None, upgrade=True)["changed"], [])
        agents.write_bytes(agents.read_bytes().replace(b"AI Harness 0.3.1", b"AI Harness customized", 1))
        self.assertEqual(len(status(self.root)["drift"]), 1)
        with self.assertRaises(HarnessError):
            install(self.root, None, upgrade=True)

    def test_drift_blocks_upgrade_without_partial_writes(self):
        self.setup_project()
        role = self.root / ".harness/roles/qa.md"
        role.write_text("定制角色")
        before = (self.root / ".harness/manifest.json").read_bytes()
        with self.assertRaises(HarnessError):
            install(self.root, ["claude"], upgrade=True)
        self.assertEqual((self.root / ".harness/manifest.json").read_bytes(), before)
        self.assertFalse((self.root / "CLAUDE.md").exists())
        self.assertEqual(len(status(self.root)["drift"]), 1)

    def test_replace_modified_backup_and_restore_are_reversible(self):
        self.setup_project()
        role = self.root / ".harness/roles/qa.md"
        role.write_text("定制角色")
        result = install(self.root, ["claude"], upgrade=True, replace_modified=True)
        restored = restore(self.root, result["backup_id"])
        self.assertEqual(role.read_text(), "定制角色")
        self.assertFalse((self.root / "CLAUDE.md").exists())
        restore(self.root, restored["undo_backup_id"])
        self.assertIn("测试工程师", role.read_text())
        self.assertTrue((self.root / "CLAUDE.md").exists())

    def test_restore_refuses_to_overwrite_later_user_edits(self):
        result = self.setup_project()
        (self.root / "AGENTS.md").write_text("后续修改")
        with self.assertRaises(HarnessError):
            restore(self.root, result["backup_id"])
        self.assertTrue((self.root / ".harness/manifest.json").exists())

    def test_downgrade_and_unknown_schema_rejected(self):
        self.setup_project()
        value = read_json(self.root, ".harness/manifest.json")
        value["kit_version"] = "99.0.0"
        atomic(self.root, ".harness/manifest.json", encoded(value))
        with self.assertRaises(HarnessError):
            install(self.root, None, upgrade=True)
        value["schema_version"] = 99
        atomic(self.root, ".harness/manifest.json", encoded(value))
        with self.assertRaises(HarnessError):
            status(self.root)

    def test_upgrade_version_change_replaces_only_owned_block(self):
        self.setup_project()
        agents = self.root / "AGENTS.md"
        agents.write_text("前置自定义\n" + agents.read_text() + "\n后置自定义")
        with patch("harnesskit.install.__version__", "0.4.0"), patch("harnesskit.templates.__version__", "0.4.0"):
            result = install(self.root, None, upgrade=True)
        self.assertEqual(result["kit_version"], "0.4.0")
        text = agents.read_text()
        self.assertIn("前置自定义", text)
        self.assertIn("后置自定义", text)
        self.assertIn("AI Harness 0.4.0", text)

    def test_broken_markers_refuse_install(self):
        (self.root / "AGENTS.md").write_text("<!-- ai-harness:begin -->")
        with self.assertRaises(HarnessError):
            self.setup_project()

    @unittest.skipUnless(os.name == "posix", "symlink privileges differ on Windows")
    def test_symlink_and_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as outside:
            (self.root / ".harness").symlink_to(outside, target_is_directory=True)
            with self.assertRaises(HarnessError):
                self.setup_project()
            self.assertEqual(list(Path(outside).iterdir()), [])
        with self.assertRaises(HarnessError):
            task_path("../../bad")

    def test_exclusive_lock(self):
        with locked(self.root):
            with self.assertRaises(HarnessError):
                with locked(self.root):
                    pass
        self.assertFalse((self.root / ".harness/.lock").exists())

    def test_all_workflows_can_create_and_resume(self):
        self.setup_project()
        for kind in ("quick", "complex", "bugfix", "research"):
            self.task(kind, kind)
            self.assertEqual(load_task(self.root, kind)["kind"], kind)
            self.assertTrue((self.root / task_path(kind, "context.md")).exists())
        with self.assertRaises(HarnessError):
            self.task("quick", "quick")

    def test_no_gates_cannot_pass_or_loop(self):
        self.setup_project()
        self.task()
        with self.assertRaises(HarnessError):
            check(self.root, "demo")
        with self.assertRaises(HarnessError):
            loop(self.root, "demo", [sys.executable, "-c", "pass"])
        self.assertTrue(doctor(self.root)["warnings"])

    def test_success_and_stale_source_evidence(self):
        self.setup_project()
        self.configure()
        self.task()
        self.assertTrue(check(self.root, "demo")["passed"])
        (self.root / "app.py").write_text("changed = True")
        with self.assertRaises(HarnessError):
            finish(self.root, "demo", "已核验")
        check(self.root, "demo")
        self.assertEqual(finish(self.root, "demo", "已核验验收及交付物")["status"], "done")

    def test_gate_that_mutates_source_is_not_success(self):
        self.setup_project()
        self.configure("from pathlib import Path; Path('source.txt').write_text('change')")
        self.task()
        self.assertFalse(check(self.root, "demo")["passed"])

    def test_authored_research_artifact_changes_invalidate_evidence(self):
        self.setup_project()
        self.configure()
        self.task("research")
        report = self.root / task_path("demo", "research.md")
        report.write_text("事实和来源")
        check(self.root, "demo")
        report.write_text("修改后的结论")
        with self.assertRaises(HarnessError):
            finish(self.root, "demo", "调研完成")

    def test_changed_acceptance_requires_new_check(self):
        self.setup_project()
        self.configure()
        self.task()
        check(self.root, "demo")
        accept(self.root, "demo", ["新的验收"])
        with self.assertRaises(HarnessError):
            finish(self.root, "demo", "验证")

    def test_subtask_dependencies_and_result_drift(self):
        self.setup_project()
        self.configure()
        self.task("complex")
        first = delegate(self.root, "demo", "architect", "接口设计", "只读设计", [])
        second = delegate(self.root, "demo", "backend", "实现", "src/api.py", [first["id"]])
        second_result = task_path("demo", f"subtasks/{second['id']}/result.md")
        atomic(self.root, second_result, b"evidence")
        with self.assertRaises(HarnessError):
            collect(self.root, "demo", second["id"])
        atomic(self.root, task_path("demo", f"subtasks/{first['id']}/result.md"), b"design")
        collect(self.root, "demo", first["id"])
        collect(self.root, "demo", second["id"])
        check(self.root, "demo")
        atomic(self.root, second_result, b"changed evidence")
        with self.assertRaises(HarnessError):
            finish(self.root, "demo", "已验证")
        collect(self.root, "demo", second["id"])
        check(self.root, "demo")
        self.assertEqual(finish(self.root, "demo", "验证所有角色产出")["status"], "done")

    def test_loop_executes_repair_then_quality_gate(self):
        self.setup_project()
        self.configure("from pathlib import Path; assert Path('fixed.txt').read_text() == 'ok'")
        self.task("bugfix")
        worker = [sys.executable, "-c", "from pathlib import Path; import sys; assert '工程任务' in sys.stdin.read(); Path('fixed.txt').write_text('ok')"]
        result = loop(self.root, "demo", worker)
        self.assertEqual(result["reason"], "checks_passed")
        self.assertEqual(load_task(self.root, "demo")["status"], "checks_passed")
        self.assertEqual(finish(self.root, "demo", "已复现并验证修复")["status"], "done")

    def test_loop_stagnation_and_feedback_prompt(self):
        self.setup_project()
        self.configure("raise SystemExit('specific failure')")
        self.task()
        result = loop(self.root, "demo", [sys.executable, "-c", "pass"])
        self.assertEqual(result["reason"], "stagnation")
        self.assertEqual(load_task(self.root, "demo")["status"], "blocked")
        last_id = result["rounds"][-1]["run"]
        self.assertIn("specific failure", (self.root / task_path("demo", f"runs/{last_id}/prompt.md")).read_text())

    def test_loop_worker_failure_and_timeout_stop(self):
        self.setup_project()
        self.configure()
        self.task()
        failed = loop(self.root, "demo", [sys.executable, "-c", "raise SystemExit(7)"])
        self.assertEqual(failed["reason"], "worker_failed")
        timed = loop(self.root, "demo", [sys.executable, "-c", "import time; time.sleep(10)"], timeout=1)
        self.assertEqual(timed["reason"], "worker_timeout")
        self.assertIsNone(load_task(self.root, "demo")["last_check"])

    def test_round_budget_stops_and_nonzero_gate_is_preserved(self):
        self.setup_project()
        self.configure("raise SystemExit(3)")
        self.task()
        report = check(self.root, "demo")
        self.assertEqual(report["gates"][0]["exit_code"], 3)
        result = loop(self.root, "demo", [sys.executable, "-c", "pass"], rounds=1)
        self.assertEqual(result["reason"], "max_rounds")

    def test_invalid_config_and_worker_are_rejected(self):
        self.setup_project()
        self.task()
        atomic(self.root, ".harness/config.json", encoded({"schema_version": 1, "gates": [{"name": "bad", "argv": "echo ok"}]}))
        with self.assertRaises(HarnessError):
            check(self.root, "demo")
        self.configure()
        with self.assertRaises(HarnessError):
            loop(self.root, "demo", "echo ok")
        with self.assertRaises(HarnessError):
            loop(self.root, "demo", [sys.executable], rounds=0)

    def test_cli_exit_codes_and_scan(self):
        self.setup_project()
        self.configure("raise SystemExit(4)")
        self.task()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["--project", str(self.root), "status"]), 0)
            self.assertEqual(main(["--project", str(self.root), "check", "demo"]), 1)
            self.assertEqual(main(["--project", str(self.root), "task", "show", "missing"]), 2)
            self.assertEqual(main(["scan", str(self.root)]), 0)
            self.assertEqual(main(["scan", str(self.root / "missing")]), 1)

    def test_release_metadata_matches_runtime(self):
        project = Path(__file__).resolve().parents[1]
        self.assertIn(f'version = "{__version__}"', (project / "pyproject.toml").read_text())


if __name__ == "__main__":
    unittest.main()
