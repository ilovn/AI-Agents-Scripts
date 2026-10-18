"""Run the public shell entrypoint against an actual local Git repository."""
import json
import os
import re
from pathlib import Path
import shutil
import shlex
import subprocess
import sys
import tempfile
import unittest

from harnesskit import __version__
from harnesskit.cli import restore
from harnesskit.install import install, status
from harnesskit.storage import HarnessError, read_json


@unittest.skipUnless(os.name == "posix" and shutil.which("sh") and shutil.which("git"), "POSIX shell and Git required")
class BootstrapTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shared = tempfile.TemporaryDirectory(prefix="harness upstream ")
        cls.addClassCleanup(cls.shared.cleanup)
        cls.repo = Path(cls.shared.name).resolve() / "upstream"
        cls.repo.mkdir()
        cls.checkout = Path(__file__).resolve().parents[1]
        cls.script = cls.checkout / "install.sh"
        cls.env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
                   "HARNESS_PYTHON": sys.executable}
        shutil.copy(cls.checkout / "harness.py", cls.repo)
        shutil.copytree(cls.checkout / "harnesskit", cls.repo / "harnesskit", ignore=shutil.ignore_patterns("__pycache__"))

        def git(*args):
            return subprocess.run(["git", "-C", str(cls.repo), *args], env=cls.env,
                                  check=True, capture_output=True, text=True).stdout.strip()

        cls.git = staticmethod(git)
        git("init", "-q", "-b", "main")
        git("config", "user.name", "Harness Tests")
        git("config", "user.email", "tests@example.invalid")
        git("add", ".")
        git("-c", "commit.gpgsign=false", "commit", "-qm", "fixture release")
        cls.initial_commit = git("rev-parse", "HEAD")
        git("tag", "v" + __version__)
        # Second commit with the same SemVer exercises exact commit provenance.
        (cls.repo / "release-note.txt").write_text("second source revision")
        git("add", ".")
        git("-c", "commit.gpgsign=false", "commit", "-qm", "branch revision")
        cls.branch_commit = git("rev-parse", "HEAD")
        git("tag", "v99.9.9")  # Intentionally mismatched tag for validation.

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="harness client ")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.project = self.base / "business project"
        self.downloads = self.base / "downloads"
        self.downloads.mkdir()

    def run_installer(self, *args, expected=0, piped=False, cwd=None):
        options = ["--repo", str(self.repo), "--project", str(self.project), *args]
        command = ["sh", "-s", "--", *options] if piped else ["sh", str(self.script), *options]
        result = subprocess.run(command, input=self.script.read_text() if piped else None,
                                cwd=cwd or self.base, env={**self.env, "TMPDIR": str(self.downloads)},
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        self.assertEqual(list(self.downloads.iterdir()), [], "temporary clone must be removed")
        return json.loads(result.stdout) if expected == 0 else result

    def test_piped_install_tracks_tag_commit_and_installs_selected_commands(self):
        result = self.run_installer("--tools", "codex,opencode", piped=True)
        self.assertEqual(result["kit_version"], __version__)
        report = status(self.project)
        self.assertEqual(report["source"], {"repository": str(self.repo), "ref": "v" + __version__,
                                            "commit": self.initial_commit})
        self.assertTrue((self.project / ".agents/skills/harness-quick/SKILL.md").exists())
        self.assertTrue((self.project / ".opencode/commands/harness-quick.md").exists())
        self.assertFalse((self.project / ".claude").exists())
        self.assertEqual(report["drift"], [])
        self.assertEqual(self.run_installer()["changed"], [])
        self.assertEqual(status(self.project)["tools"], ["codex", "opencode"])

    def test_dry_run_creates_no_project_and_cleans_clone(self):
        result = self.run_installer("--dry-run")
        self.assertTrue(result["dry_run"])
        self.assertTrue(result["changed"])
        self.assertFalse(self.project.exists())

    def test_ref_upgrade_changes_provenance_and_restore_recovers_previous_source(self):
        self.run_installer("--tools", "codex")
        config = self.project / ".harness/config.json"
        config.write_text('{"schema_version": 1, "gates": [], "custom": "preserved"}')
        result = self.run_installer("--ref", "main")
        self.assertEqual(status(self.project)["source"]["commit"], self.branch_commit)
        self.assertEqual(read_json(self.project, ".harness/config.json")["custom"], "preserved")
        restore(self.project, result["backup_id"])
        self.assertEqual(status(self.project)["source"]["commit"], self.initial_commit)
        self.assertEqual(self.run_installer("--ref", self.branch_commit)["source"]["commit"], self.branch_commit)

    def test_remote_upgrade_preserves_conflict_protection(self):
        self.run_installer("--tools", "codex")
        path = self.project / ".agents/skills/harness-bugfix/SKILL.md"
        path.write_text("team customization")
        before = (self.project / ".harness/manifest.json").read_bytes()
        result = self.run_installer("--ref", "main", expected=2)
        self.assertIn("冲突", result.stderr)
        self.assertEqual(path.read_text(), "team customization")
        self.assertEqual((self.project / ".harness/manifest.json").read_bytes(), before)

    def test_version_mismatch_and_missing_ref_fail_before_project_write(self):
        result = self.run_installer("--version", "99.9.9", expected=2)
        self.assertIn("mismatch", result.stderr)
        self.assertFalse(self.project.exists())
        self.run_installer("--ref", "no-such-ref", expected=128)
        self.assertFalse(self.project.exists())

    def test_invalid_arguments_fail_before_fetch(self):
        cases = [("--tools", "codex,unknown"), ("--tools", ",codex"), ("--mode", "bad"),
                 ("--ref", "main", "--version", __version__), ("--version", "latest"),
                 ("--python", str(self.base / "missing-python"))]
        for args in cases:
            with self.subTest(args=args):
                result = self.run_installer(*args, expected=2 if args != ("--version", "latest") else 1)
                self.assertNotIn("Fetching", result.stderr)
                self.assertFalse(self.project.exists())

    def test_publisher_default_repository_enables_no_argument_install(self):
        configured = re.sub(r"(?m)^DEFAULT_REPO=.*$", lambda _: "DEFAULT_REPO=" + shlex.quote(str(self.repo)), self.script.read_text(), count=1)
        result = subprocess.run(["sh"], input=configured, cwd=self.base,
                                env={**self.env, "HARNESS_REPO": "", "TMPDIR": str(self.downloads)},
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(status(self.base)["source"]["commit"], self.initial_commit)
        self.assertTrue((self.base / ".claude/commands/harness-quick.md").exists())
        self.assertTrue((self.base / ".agents/skills/harness-quick/SKILL.md").exists())
        self.assertEqual(list(self.downloads.iterdir()), [])

    def test_default_target_is_callers_directory(self):
        result = subprocess.run(["sh", str(self.script), "--repo", str(self.repo), "--tools", "claude"],
                                cwd=self.base, env=self.env, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.base / ".claude/commands/harness-quick.md").exists())
        self.assertEqual(status(self.base)["source"]["commit"], self.initial_commit)


class SourceMetadataTest(unittest.TestCase):
    def test_invalid_source_is_rejected_and_local_upgrade_clears_old_provenance(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with self.assertRaises(HarnessError):
                install(root, ["codex"], source={"commit": "bad"})
            self.assertFalse((root / ".harness").exists())
            source = {"repository": "https://example.invalid/team/kit.git", "ref": "v" + __version__, "commit": "a" * 40}
            install(root, ["codex"], source=source)
            self.assertEqual(status(root)["source"], source)
            result = install(root, None, upgrade=True)
            self.assertIsNone(status(root)["source"])
            restore(root, result["backup_id"])
            self.assertEqual(status(root)["source"], source)

    def test_bootstrap_version_matches_package(self):
        text = (Path(__file__).resolve().parents[1] / "install.sh").read_text()
        self.assertIn("INSTALLER_VERSION=" + __version__, text)
