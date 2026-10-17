"""Exercise local installation with real files in isolated temporary projects."""

from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from scripts.distribution import SKILL_NAMES

REPOSITORY = Path(__file__).resolve().parents[1]


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.package = self.root / "package"
        self.project = self.root / "project"
        self.project.mkdir()
        (self.package / "scripts").mkdir(parents=True)
        for name in ("install.py", "distribution.py"):
            shutil.copy2(REPOSITORY / "scripts" / name, self.package / "scripts" / name)
        (self.package / ".claude-plugin").mkdir()
        shutil.copy2(REPOSITORY / ".claude-plugin" / "plugin.json", self.package / ".claude-plugin" / "plugin.json")
        for name in SKILL_NAMES:
            skill = self.package / "skills" / name
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text(
                f"---\nname: {name}\ndescription: Fixture skill.\n---\n"
                "Read [shared process](../moletta/references/process.md)\n", encoding="utf-8"
            )
        core = self.package / "skills" / "moletta"
        (core / "references").mkdir()
        (core / "references" / "process.md").write_text("shared reference\n", encoding="utf-8")
        (core / "scripts").mkdir()
        (core / "scripts" / "moletta.py").write_text("print('local helper available')\n", encoding="utf-8")

    def run_installer(self, *arguments, project=None):
        return subprocess.run(
            [sys.executable, str(self.package / "scripts" / "install.py"),
             str(project or self.project), *arguments],
            capture_output=True, text=True,
        )

    def assert_hosts_usable(self, mode):
        for host in (".agents", ".claude"):
            directory = self.project / host / "skills"
            self.assertEqual({path.name for path in directory.iterdir()}, set(SKILL_NAMES))
            for name in SKILL_NAMES:
                self.assertEqual((directory / name).is_symlink(), mode == "symlink")
                self.assertTrue((directory / name / "SKILL.md").is_file())
                reference = directory / name / ".." / "moletta" / "references" / "process.md"
                self.assertEqual(reference.read_text(encoding="utf-8"), "shared reference\n")
            helper = subprocess.run(
                [sys.executable, str(directory / "moletta" / "scripts" / "moletta.py")],
                capture_output=True, text=True,
            )
            self.assertEqual(helper.returncode, 0, helper.stderr)
            self.assertEqual(helper.stdout.strip(), "local helper available")

    def test_default_installs_all_skills_with_both_hosts_and_shared_assets(self):
        (self.project / "AGENTS.md").write_text("keep Codex instructions\n", encoding="utf-8")
        (self.project / "CLAUDE.md").write_text("keep Claude instructions\n", encoding="utf-8")
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_hosts_usable("symlink")
        self.assertEqual((self.project / "AGENTS.md").read_text(), "keep Codex instructions\n")
        self.assertEqual((self.project / "CLAUDE.md").read_text(), "keep Claude instructions\n")

    def test_identical_links_are_idempotent_including_relative_links(self):
        self.assertEqual(self.run_installer().returncode, 0)
        link = self.project / ".agents" / "skills" / "moletta"
        link.unlink()
        link.symlink_to("../../../package/skills/moletta", target_is_directory=True)
        before = {path: path.lstat().st_ino for host in (".agents", ".claude")
                  for path in (self.project / host / "skills").iterdir()}
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.count("Already linked:"), 10)
        self.assertEqual(before, {path: path.lstat().st_ino for path in before})

    def test_any_late_host_conflict_blocks_all_installation(self):
        directory = self.project / ".claude" / "skills"
        directory.mkdir(parents=True)
        conflict = directory / "moletta-verify"
        conflict.mkdir()
        (conflict / "user-data.txt").write_text("preserve me", encoding="utf-8")
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Refusing to replace", result.stderr)
        self.assertFalse((self.project / ".agents").exists())
        self.assertEqual(list(directory.iterdir()), [conflict])
        self.assertEqual((conflict / "user-data.txt").read_text(), "preserve me")

    def test_dangling_symlink_is_a_conflict(self):
        directory = self.project / ".claude" / "skills"
        directory.mkdir(parents=True)
        conflict = directory / "moletta-learn"
        conflict.symlink_to(self.root / "missing")
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.project / ".agents").exists())
        self.assertTrue(conflict.is_symlink())

    def test_regular_file_skill_is_not_overwritten(self):
        directory = self.project / ".claude" / "skills"
        directory.mkdir(parents=True)
        conflict = directory / "moletta-compare"
        conflict.write_text("user-owned content", encoding="utf-8")
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.project / ".agents").exists())
        self.assertEqual(conflict.read_text(), "user-owned content")

    def test_foreign_symlink_is_a_conflict(self):
        directory = self.project / ".claude" / "skills"
        directory.mkdir(parents=True)
        foreign = self.root / "foreign-skill"
        foreign.mkdir()
        conflict = directory / "moletta"
        conflict.symlink_to(foreign, target_is_directory=True)
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.project / ".agents").exists())
        self.assertEqual(conflict.resolve(), foreign)

    def test_parent_symlink_cannot_redirect_installation(self):
        foreign = self.root / "foreign-config"
        foreign.mkdir()
        (self.project / ".claude").symlink_to(foreign, target_is_directory=True)
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("regular directory", result.stderr)
        self.assertFalse((self.project / ".agents").exists())
        self.assertEqual(list(foreign.iterdir()), [])

    def test_regular_file_parent_blocks_both_hosts(self):
        (self.project / ".claude").write_text("existing file", encoding="utf-8")
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.project / ".agents").exists())
        self.assertEqual((self.project / ".claude").read_text(), "existing file")

    def test_copy_mode_preserves_sibling_references_without_source_checkout(self):
        result = self.run_installer("--mode", "copy")
        self.assertEqual(result.returncode, 0, result.stderr)
        shutil.rmtree(self.package)
        self.assert_hosts_usable("copy")

    def test_existing_copy_is_not_overwritten(self):
        self.assertEqual(self.run_installer("--mode", "copy").returncode, 0)
        user_file = self.project / ".claude" / "skills" / "moletta-learn" / "notes.txt"
        user_file.write_text("local additions", encoding="utf-8")
        result = self.run_installer("--mode", "copy")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(user_file.read_text(), "local additions")

    def test_host_selection_still_installs_complete_skill_family(self):
        for host, selected, absent in (("codex", ".agents", ".claude"),
                                       ("claude", ".claude", ".agents")):
            with self.subTest(host=host):
                project = self.root / host
                project.mkdir()
                result = self.run_installer("--host", host, project=project)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual({path.name for path in (project / selected / "skills").iterdir()}, set(SKILL_NAMES))
                self.assertFalse((project / absent).exists())

    def test_unlisted_skill_is_rejected_before_project_mutation(self):
        extra = self.package / "skills" / "moletta-future"
        extra.mkdir()
        (extra / "SKILL.md").write_text("additional skill", encoding="utf-8")
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unexpected", result.stderr)
        self.assertEqual(list(self.project.iterdir()), [])

    def test_incomplete_package_fails_before_project_mutation(self):
        shutil.rmtree(self.package / "skills" / "moletta-learn")
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Incomplete skill package", result.stderr)
        self.assertEqual(list(self.project.iterdir()), [])

    def test_project_must_exist(self):
        missing = self.root / "missing-project"
        result = self.run_installer(project=missing)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(missing.exists())

    def test_global_home_installation_is_rejected(self):
        result = self.run_installer(project=Path.home())
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("global installation is not supported", result.stderr)

    def test_copy_cannot_silently_reuse_existing_checkout_links(self):
        self.assertEqual(self.run_installer().returncode, 0)
        result = self.run_installer("--mode", "copy")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Refusing to replace", result.stderr)
        self.assert_hosts_usable("symlink")

    def test_broken_sibling_reference_blocks_installation_before_mutation(self):
        reference = self.package / "skills" / "moletta" / "references" / "process.md"
        reference.unlink()
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing local link target", result.stderr)
        self.assertEqual(list(self.project.iterdir()), [])

    def test_invalid_metadata_blocks_installation_before_mutation(self):
        entry = self.package / "skills" / "moletta-explore" / "SKILL.md"
        entry.write_text("---\nname: wrong-name\ndescription: Fixture skill.\n---\n", encoding="utf-8")
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("frontmatter name", result.stderr)
        self.assertEqual(list(self.project.iterdir()), [])

    def test_unsupported_host_is_rejected_without_project_mutation(self):
        result = self.run_installer("--host", "unsupported")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(self.project.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
