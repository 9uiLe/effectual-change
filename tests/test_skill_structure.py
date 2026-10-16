"""Validate that the Agent Skill is self-contained and discoverable.

Only Python's standard library is used. The metadata checker deliberately accepts
a narrow, unquoted YAML subset (name and description as one-line plain scalars);
it is NOT a general YAML parser. Also run the official skills-ref validator
before a public release.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "effectual-change"
SKILL_FILE = SKILL_DIR / "SKILL.md"
LOCAL_LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
FRONTMATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)
# Restrict plain scalars to characters with unambiguous YAML string semantics.
# In particular, reject flow collections ([...], {...}), anchors, tags, quotes,
# colon-mappings, YAML comments, and folded/literal block scalars.
PLAIN_DESCRIPTION = re.compile(r"[\w .,;!?()/\-、（）]+", re.UNICODE)


def validate_frontmatter(markdown: str) -> dict[str, str]:
    """Accept only the exact frontmatter subset used by this repository.

    Requiring two plain scalar fields eliminates the false-positive case where
    a line-based key/value split accepted syntactically invalid YAML.
    """
    match = FRONTMATTER.match(markdown)
    if match is None:
        raise ValueError("SKILL.md requires a YAML frontmatter block")

    lines = match.group(1).splitlines()
    if len(lines) != 2:
        raise ValueError("Only 'name' and 'description' one-line fields are supported")
    if not lines[0].startswith("name: ") or not lines[1].startswith("description: "):
        raise ValueError("Expected 'name' followed by 'description' plain scalars")

    name = lines[0][len("name: "):]
    description = lines[1][len("description: "):]
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name) or len(name) > 64:
        raise ValueError("Invalid skill name")
    if (
        not description
        or len(description) > 1024
        or not description[0].isalnum()
        or PLAIN_DESCRIPTION.fullmatch(description) is None
        or description.lower() in {"true", "false", "null", "yes", "no", "on", "off"}
    ):
        raise ValueError("Description must be a nonempty, unquoted, single-line plain scalar")
    if len(markdown.splitlines()) > 500:
        raise ValueError("SKILL.md exceeds 500 lines")
    return {"name": name, "description": description}


class AgentSkillStructureTests(unittest.TestCase):
    def test_skill_frontmatter(self):
        metadata = validate_frontmatter(SKILL_FILE.read_text(encoding="utf-8"))
        self.assertEqual(metadata["name"], SKILL_DIR.name)

    def test_invalid_frontmatter_is_rejected(self):
        original = SKILL_FILE.read_text(encoding="utf-8")
        match = FRONTMATTER.match(original)
        self.assertIsNotNone(match)
        body = original[match.end():]
        invalid_headers = {
            "invalid YAML flow sequence": "name: effectual-change\ndescription: [invalid, YAML",
            "invalid YAML mapping": "name: effectual-change\ndescription: {invalid: YAML",
            "embedded mapping": "name: effectual-change\ndescription: Invalid: YAML",
            "unterminated quote": 'name: effectual-change\ndescription: "unterminated',
            "block scalar": "name: effectual-change\ndescription: |",
            "anchor": "name: effectual-change\ndescription: &ref text",
            "comment": "name: effectual-change\ndescription: Text #comment",
            "duplicate key": "name: effectual-change\ndescription: Valid text\ndescription: Duplicate",
            "extra key": "name: effectual-change\ndescription: Valid text\nallowed-tools: Bash",
            "missing key": "name: effectual-change",
            "empty description": "name: effectual-change\ndescription: ",
            "wrong key order": "description: Valid text\nname: effectual-change",
            "invalid name": "name: Effectual Change\ndescription: Valid text",
            "leading YAML indicator": "name: effectual-change\ndescription: - unsafe",
            "tab character": "name: effectual-change\ndescription: Text\tbad",
        }
        for reason, header in invalid_headers.items():
            with self.subTest(reason=reason):
                with self.assertRaises(ValueError):
                    validate_frontmatter(f"---\n{header}\n---\n{body}")

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
