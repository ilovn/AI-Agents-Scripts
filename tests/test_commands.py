"""Task entrypoints must share the installer ownership and recovery guarantees."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from harnesskit import __version__
from harnesskit.cli import restore
from harnesskit.install import doctor, install, status
from harnesskit.storage import HarnessError, read_json
from harnesskit.templates import WORKFLOWS, managed_files, task_entrypoints


class CommandsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_all_platform_entrypoints_have_valid_discovery_paths_and_ownership(self):
        install(self.root, ["claude", "codex", "opencode", "trae"])
        report = doctor(self.root)
        entries = report["task_entrypoints"]
        self.assertEqual(len(entries), 12)
        installed = read_json(self.root, ".harness/manifest.json")
        for entry in entries:
            self.assertTrue(entry["installed"])
            self.assertIn(entry["path"], installed["files"])
            path = self.root / entry["path"]
            text = path.read_text(encoding="utf-8")
            header, body = text.removeprefix("---\n").split("\n---\n", 1)
            self.assertIn("description:", header)
            self.assertIn(f".harness/workflows/{entry['kind']}.md", body)
            if entry["tool"] == "codex":
                self.assertEqual(path.name, "SKILL.md")
                self.assertEqual(path.parent.name, f"harness-{entry['kind']}")
                self.assertIn(f"name: {path.parent.name}", header)
                self.assertNotIn("$ARGUMENTS", text)
                self.assertTrue(entry["invoke"].startswith("$"))
            else:
                self.assertEqual(path.stem, f"harness-{entry['kind']}")
                self.assertIn("$ARGUMENTS", body)
                self.assertTrue(entry["invoke"].startswith("/"))
        self.assertFalse((self.root / ".codex/prompts").exists())
        self.assertFalse((self.root / ".trae/commands").exists())

    def test_selection_does_not_install_other_platform_commands(self):
        install(self.root, ["opencode"])
        self.assertEqual(len(doctor(self.root)["task_entrypoints"]), 4)
        self.assertFalse((self.root / ".claude").exists())
        self.assertFalse((self.root / ".agents").exists())

    def test_new_command_name_collision_blocks_all_install_writes(self):
        path = self.root / ".claude/commands/harness-quick.md"
        path.parent.mkdir(parents=True)
        path.write_text("existing team command")
        with self.assertRaises(HarnessError):
            install(self.root, ["claude", "codex"])
        self.assertFalse((self.root / ".harness/manifest.json").exists())
        self.assertFalse((self.root / ".agents").exists())
        self.assertEqual(path.read_text(), "existing team command")

    def test_modified_skill_is_detected_and_preserved_until_explicit_replace(self):
        install(self.root, ["codex"])
        path = self.root / ".agents/skills/harness-bugfix/SKILL.md"
        path.write_text("team customization")
        self.assertEqual(status(self.root)["drift"][0]["path"], path.relative_to(self.root).as_posix())
        with self.assertRaises(HarnessError):
            install(self.root, None, upgrade=True)
        result = install(self.root, None, upgrade=True, replace_modified=True)
        restore(self.root, result["backup_id"])
        self.assertEqual(path.read_text(), "team customization")

    def test_upgrade_from_pre_commands_version_adds_and_can_remove_commands(self):
        # Fixture for the old installer: same shared contracts, no command/skill files.
        def old_files(tools):
            files = managed_files(tools)
            for entry in task_entrypoints(tools):
                files.pop(entry["path"])
            return files

        with patch("harnesskit.install.managed_files", side_effect=old_files), \
             patch("harnesskit.install.__version__", "0.1.0"), \
             patch("harnesskit.templates.__version__", "0.1.0"):
            install(self.root, ["claude", "codex", "opencode"])
        self.assertTrue(all(not entry["installed"] for entry in doctor(self.root)["task_entrypoints"]))
        config_before = (self.root / ".harness/config.json").read_bytes()
        result = install(self.root, None, upgrade=True)
        self.assertEqual(result["kit_version"], __version__)
        self.assertTrue(all(entry["installed"] for entry in doctor(self.root)["task_entrypoints"]))
        self.assertEqual(status(self.root)["drift"], [])
        self.assertEqual(install(self.root, None, upgrade=True)["changed"], [])
        restore(self.root, result["backup_id"])
        self.assertEqual(status(self.root)["project_version"], "0.1.0")
        self.assertEqual((self.root / ".harness/config.json").read_bytes(), config_before)
        for entry in task_entrypoints(["claude", "codex", "opencode"]):
            self.assertFalse((self.root / entry["path"]).exists())
