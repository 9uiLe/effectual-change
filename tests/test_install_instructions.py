"""Regression tests for the symlink commands published in README.md.

Commands run only inside isolated temporary HOME directories; no Git clone,
network access, or user skill directories are touched.
"""

import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALL_SNIPPET = re.compile(
    r"~~~bash\n(# Safe Skill symlink installation\n.*?)\n~~~",
    re.DOTALL,
)
SKILL_RELATIVE_PATH = "skills/effectual-change"


def get_install_script() -> str:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    match = INSTALL_SNIPPET.search(readme)
    if match is None:
        raise AssertionError("README must contain the guarded symlink snippet")
    return match.group(1)


def run_install(home: Path) -> subprocess.CompletedProcess[str]:
    environment = {**os.environ, "HOME": str(home)}
    return subprocess.run(
        ["sh", "-c", get_install_script()],
        cwd=home,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def create_skill_source(home: Path) -> Path:
    source = home / ".local" / "share" / "effectual-change" / SKILL_RELATIVE_PATH
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text("name: effectual-change\n", encoding="utf-8")
    return source


def skill_targets(home: Path) -> tuple[Path, Path]:
    return (
        home / ".claude" / "skills" / "effectual-change",
        home / ".agents" / "skills" / "effectual-change",
    )


@unittest.skipUnless(os.name == "posix", "README commands target POSIX sh / symlinks")
class SafeSymlinkInstallTests(unittest.TestCase):
    def test_installs_both_symlinks_into_empty_destinations(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            source = create_skill_source(home)

            result = run_install(home)

            self.assertEqual(result.returncode, 0, result.stderr)
            for target in skill_targets(home):
                self.assertTrue(target.is_symlink())
                self.assertEqual(target.resolve(), source.resolve())

    def test_rejects_missing_source_without_creating_links(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)

            result = run_install(home)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Skill not found", result.stderr)
            for target in skill_targets(home):
                self.assertFalse(target.exists() or target.is_symlink())

    def test_existing_destinations_are_left_unchanged(self):
        for target_index in (0, 1):
            for collision in ("directory", "file", "symlink", "dangling symlink"):
                with self.subTest(target_index=target_index, collision=collision):
                    with tempfile.TemporaryDirectory() as directory:
                        home = Path(directory)
                        source = create_skill_source(home)
                        target = skill_targets(home)[target_index]
                        other = skill_targets(home)[1 - target_index]
                        target.parent.mkdir(parents=True, exist_ok=True)

                        if collision == "directory":
                            target.mkdir()
                            (target / "SKILL.md").write_text("existing\n", encoding="utf-8")
                        elif collision == "file":
                            target.write_text("existing\n", encoding="utf-8")
                        elif collision == "symlink":
                            target.symlink_to(source, target_is_directory=True)
                        else:
                            target.symlink_to(home / "missing-target", target_is_directory=True)

                        result = run_install(home)

                        self.assertNotEqual(result.returncode, 0)
                        self.assertIn("Skill already exists", result.stderr)
                        self.assertFalse(other.exists() or other.is_symlink())
                        self.assertFalse(
                            other.parent.exists(),
                            "A collision must not create the other agent's skill directory",
                        )
                        self.assertFalse((source / "effectual-change").exists())
                        if collision == "directory":
                            self.assertEqual(
                                (target / "SKILL.md").read_text(encoding="utf-8"),
                                "existing\n",
                            )
                            self.assertFalse((target / "effectual-change").exists())
                        elif collision == "file":
                            self.assertEqual(target.read_text(encoding="utf-8"), "existing\n")
                        else:
                            self.assertTrue(target.is_symlink())


if __name__ == "__main__":
    unittest.main()
