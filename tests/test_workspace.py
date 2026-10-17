"""Work-unit placement, isolation and local privacy at the storage boundary."""

import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


SCRIPTS = Path(__file__).resolve().parents[1] / "skills/moletta/scripts"
sys.path.insert(0, str(SCRIPTS))
import store
import workspace
from model import DataError


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.project = self.base / "project"
        self.project.mkdir()
        self.brief = self.project / "request.md"
        self.brief.write_text("A synthetic task request", encoding="utf-8")

    def initialize(self, **kwargs):
        return workspace.initialize(self.brief, "Complete the task", cwd=self.project, **kwargs)

    def git(self, directory, *args):
        environment = os.environ.copy()
        for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_CEILING_DIRECTORIES"):
            environment.pop(key, None)
        result = subprocess.run(["git", "-C", str(directory), *args], capture_output=True,
                                text=True, check=False, env=environment)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def test_nongit_defaults_to_calling_directory_and_each_start_is_distinct(self):
        first = self.initialize()
        second = self.initialize()
        self.assertEqual(Path(first["project"]), self.project)
        self.assertEqual(Path(first["workspace"]), self.project / ".moletta-runs")
        self.assertNotEqual(first["run"], second["run"])
        for result in (first, second):
            root = Path(result["run"])
            self.assertEqual(root.parent, self.project / ".moletta-runs")
            self.assertEqual((root / "brief.md").read_bytes(), self.brief.read_bytes())
            self.assertEqual(json.loads((root / "journal.json").read_text())["events"], [])
        self.assertNotEqual(store.load(Path(first["run"])).run.run_id,
                            store.load(Path(second["run"])).run.run_id)

    def test_missing_git_uses_selected_nongit_directory(self):
        with mock.patch.object(workspace.subprocess, "run", side_effect=FileNotFoundError):
            self.assertEqual(workspace.project_root(cwd=self.project), self.project)

    def test_project_selection_and_brief_are_relative_to_the_caller(self):
        selected = self.project / "selected"
        selected.mkdir()
        result = workspace.initialize(Path("request.md"), "Task", cwd=self.project,
                                      project=Path("selected"))
        self.assertEqual(Path(result["project"]), selected)
        self.assertEqual(Path(result["run"]).parent, selected / ".moletta-runs")
        self.assertEqual((Path(result["run"]) / "brief.md").read_bytes(), self.brief.read_bytes())

    @unittest.skipUnless(shutil.which("git"), "Git is required for worktree discovery")
    def test_git_subdirectory_uses_worktree_root_and_ignores_git_environment_overrides(self):
        self.git(self.project, "init", "--quiet")
        nested = self.project / "src" / "nested"
        nested.mkdir(parents=True)
        unrelated = self.base / "other"
        unrelated.mkdir()
        self.git(unrelated, "init", "--quiet")
        environment = {"GIT_DIR": str(unrelated / ".git"), "GIT_WORK_TREE": str(unrelated),
                       "GIT_COMMON_DIR": str(unrelated / ".git"),
                       "GIT_CEILING_DIRECTORIES": str(nested.parent)}
        with mock.patch.dict(os.environ, environment):
            result = workspace.initialize(self.brief, "Task", cwd=nested)
        self.assertEqual(Path(result["project"]), self.project)
        self.assertEqual(Path(result["run"]).parent, self.project / ".moletta-runs")
        self.assertFalse((unrelated / ".moletta-runs").exists())
        self.assertFalse((nested / ".moletta-runs").exists())

    @unittest.skipUnless(shutil.which("git"), "Git is required for worktree discovery")
    def test_linked_worktrees_keep_separate_records_outside_shared_git_directory(self):
        self.git(self.project, "init", "--quiet")
        self.git(self.project, "-c", "user.name=Moletta Test", "-c", "user.email=test@example.invalid",
                 "-c", "commit.gpgSign=false", "commit", "--allow-empty", "-m", "Synthetic fixture")
        linked = self.base / "linked"
        self.git(self.project, "worktree", "add", "--detach", str(linked), "HEAD")
        nested = linked / "src"
        nested.mkdir()
        linked_result = workspace.initialize(self.brief, "Task", cwd=nested)
        self.assertEqual(Path(linked_result["project"]), linked)
        self.assertEqual(Path(linked_result["run"]).parent, linked / ".moletta-runs")
        self.assertFalse((self.project / ".moletta-runs").exists())
        common = Path(self.git(linked, "rev-parse", "--git-common-dir")).resolve()
        self.assertFalse((common / ".moletta-runs").exists())
        main_result = self.initialize()
        self.assertEqual(Path(main_result["run"]).parent, self.project / ".moletta-runs")

    def test_explicit_run_bypasses_default_workspace_and_remains_exclusive(self):
        result = self.initialize(root=Path("custom") / "run")
        self.assertEqual(Path(result["run"]), self.project / "custom" / "run")
        self.assertIsNone(result["workspace"])
        self.assertFalse((self.project / ".moletta-runs").exists())
        brief = (Path(result["run"]) / "brief.md").read_bytes()
        with self.assertRaises(FileExistsError):
            self.initialize(root=Path(result["run"]))
        self.assertEqual((Path(result["run"]) / "brief.md").read_bytes(), brief)

    def test_explicit_run_rejects_a_name_that_would_be_ignored(self):
        with self.assertRaisesRegex(DataError, "--name"):
            self.initialize(root=Path("run"), name="ignored")
        self.assertFalse((self.project / "run").exists())

    def test_known_secret_cannot_become_a_task_directory_name(self):
        token = "ghp_" + "A" * 40
        with self.assertRaises(DataError) as caught:
            self.initialize(name=token)
        self.assertNotIn(token, str(caught.exception))
        self.assertFalse((self.project / ".moletta-runs").exists())

    def test_multibyte_task_names_fit_a_single_filesystem_entry(self):
        result = self.initialize(name="𠀀" * 60)
        self.assertLess(len(Path(result["run"]).name.encode("utf-8")), 255)

    def test_readme_explains_contents_and_preserves_existing_custom_file(self):
        self.initialize()
        readme = self.project / ".moletta-runs" / "README.md"
        for content in ("brief.md", "intent.json", "journal.json", "artifacts/", "checkpoints/", "/.moletta-runs/"):
            self.assertIn(content, readme.read_text())
        readme.write_text("Project-specific guidance\n", encoding="utf-8")
        self.initialize()
        self.assertEqual(readme.read_text(), "Project-specific guidance\n")

    def test_gitignore_is_reported_without_creating_or_editing_it(self):
        absent = self.initialize()
        ignore = self.project / ".gitignore"
        self.assertEqual(absent["gitignore"]["status"], "missing")
        self.assertEqual(absent["gitignore"]["pattern"], "/.moletta-runs/")
        self.assertFalse(ignore.exists())
        original = b"# Project rules\n*.tmp\n"
        ignore.write_bytes(original)
        self.assertEqual(self.initialize()["gitignore"]["status"], "missing")
        self.assertEqual(ignore.read_bytes(), original)
        included = original + b"/.moletta-runs/\n"
        ignore.write_bytes(included)
        self.assertEqual(self.initialize()["gitignore"]["status"], "present")
        self.assertEqual(ignore.read_bytes(), included)

    def test_symlinked_ignore_file_is_not_followed(self):
        outside = self.base / "outside-ignore"
        outside.write_text("/.moletta-runs/\n", encoding="utf-8")
        (self.project / ".gitignore").symlink_to(outside)
        result = self.initialize()
        self.assertEqual(result["gitignore"]["status"], "unreadable")
        self.assertEqual(outside.read_text(), "/.moletta-runs/\n")

    def test_workspace_and_readme_cannot_traverse_a_symlink(self):
        outside = self.base / "outside"
        outside.mkdir()
        path = self.project / ".moletta-runs"
        path.symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(DataError, "symlink"):
            self.initialize()
        self.assertEqual(list(outside.iterdir()), [])
        path.unlink()
        path.mkdir()
        target = outside / "README.md"
        target.write_text("Keep this\n", encoding="utf-8")
        (path / "README.md").symlink_to(target)
        with self.assertRaisesRegex(DataError, "symlink"):
            self.initialize()
        self.assertEqual(target.read_text(), "Keep this\n")
        self.assertEqual(list(path.iterdir()), [path / "README.md"])

    def test_existing_files_cannot_be_used_as_workspace_or_readme(self):
        path = self.project / ".moletta-runs"
        path.write_text("Keep this\n", encoding="utf-8")
        with self.assertRaises(DataError):
            self.initialize()
        self.assertEqual(path.read_text(), "Keep this\n")
        path.unlink()
        path.mkdir()
        (path / "README.md").mkdir()
        with self.assertRaises(DataError):
            self.initialize()
        self.assertTrue((path / "README.md").is_dir())

    def test_task_name_cannot_escape_storage_and_remains_useful_in_unicode(self):
        result = self.initialize(name="../../ 検証 / Screen Save !")
        root = Path(result["run"])
        self.assertEqual(root.parent, self.project / ".moletta-runs")
        self.assertIn("検証-screen-save", root.name)
        self.assertNotIn("..", root.name)
        self.assertRegex(root.name, r"^\d{8}T\d{6}\.\d{6}Z-.*-[0-9a-f]{8}$")

    def test_allocation_collision_does_not_overwrite_or_resume_existing_work(self):
        directory = self.project / ".moletta-runs"
        directory.mkdir()
        occupied = directory / "20261017T000000.000000Z-task-aaaaaaaa"
        occupied.mkdir()
        keep = occupied / "keep.txt"
        keep.write_text("Previous work\n", encoding="utf-8")
        with mock.patch.object(workspace, "datetime") as clock, \
                mock.patch.object(workspace.secrets, "token_hex", side_effect=["aaaaaaaa", "bbbbbbbb"]):
            clock.now.return_value.strftime.return_value = "20261017T000000.000000Z"
            result = self.initialize(name="Task")
        self.assertEqual(Path(result["run"]).name, "20261017T000000.000000Z-task-bbbbbbbb")
        self.assertEqual(keep.read_text(), "Previous work\n")
        self.assertFalse((occupied / "journal.json").exists())

    def test_new_storage_is_private_even_with_permissive_process_umask(self):
        previous = os.umask(0)
        try:
            result = self.initialize()
            root = Path(result["run"])
            store.write_json(root / "plan.json", store.read_json(root / "plan.json"))
            with store.mutation(root):
                pass
        finally:
            os.umask(previous)
        for directory in (root.parent, root, root / "artifacts", root / "checkpoints"):
            self.assertEqual(stat.S_IMODE(directory.stat().st_mode), 0o700, directory)
        for path in (*root.glob("*.json"), root / "brief.md", root / ".write.lock", root.parent / "README.md"):
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600, path)

    def test_existing_symlink_run_and_lock_cannot_redirect_writes(self):
        outside = self.base / "outside"
        outside.mkdir()
        (self.project / "run").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(FileExistsError):
            self.initialize(root=Path("run"))
        self.assertEqual(list(outside.iterdir()), [])
        root = Path(self.initialize()["run"])
        target = outside / "lock"
        target.write_text("Keep this\n", encoding="utf-8")
        (root / ".write.lock").symlink_to(target)
        with self.assertRaises(OSError), store.mutation(root):
            self.fail("A symlink lock must not be acquired")
        self.assertEqual(target.read_text(), "Keep this\n")


if __name__ == "__main__":
    unittest.main()
