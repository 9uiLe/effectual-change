"""Validate that the Agent Skill is self-contained and discoverable.

This uses only Python's standard library; it does not install dependencies.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "effectual-change"
SKILL_FILE = SKILL_DIR / "SKILL.md"
LOCAL_LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")


class AgentSkillStructureTests(unittest.TestCase):
    def test_skill_frontmatter(self):
        text = SKILL_FILE.read_text(encoding="utf-8")
        match = re.match(r"\A---\r?\n(.*?)\r?\n---\r?\n", text, re.DOTALL)
        self.assertIsNotNone(match, "SKILL.md requires YAML frontmatter")
        fields = {}
        for line in match.group(1).splitlines():
            if not line.strip():
                continue
            key, separator, value = line.partition(":")
            self.assertTrue(separator, f"Invalid frontmatter line: {line}")
            fields[key.strip()] = value.strip().strip('"').strip("'")
        self.assertEqual(fields.get("name"), SKILL_DIR.name)
        self.assertRegex(fields["name"], r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
        self.assertLessEqual(len(fields["name"]), 64)
        self.assertTrue(fields.get("description"), "description is required")
        self.assertLessEqual(len(fields["description"]), 1024)
        self.assertLessEqual(len(text.splitlines()), 500)

    def test_skill_has_no_executable_payload(self):
        self.assertFalse((SKILL_DIR / "scripts").exists())
        for path in SKILL_DIR.rglob("*"):
            if path.is_file():
                self.assertEqual(path.suffix, ".md", f"Unexpected bundled file: {path}")

    def test_relative_markdown_links_and_self_containment(self):
        paths = [ROOT / "README.md", ROOT / "docs" / "evaluation.md"]
        paths += sorted(SKILL_DIR.rglob("*.md"))
        for path in paths:
            for target in LOCAL_LINK.findall(path.read_text(encoding="utf-8")):
                link = target.split("#", 1)[0].strip()
                if not link or "://" in link or link.startswith("mailto:"):
                    continue
                with self.subTest(source=str(path.relative_to(ROOT)), target=link):
                    self.assertFalse(Path(link).is_absolute(), "Absolute local link")
                    resolved = (path.parent / link).resolve()
                    self.assertTrue(resolved.is_relative_to(ROOT.resolve()), "Link escapes repo")
                    self.assertTrue(resolved.is_file(), "Broken Markdown link")
                    if path.is_relative_to(SKILL_DIR):
                        self.assertTrue(
                            resolved.is_relative_to(SKILL_DIR.resolve()),
                            "Installed skill references a file outside the skill package",
                        )


if __name__ == "__main__":
    unittest.main()
