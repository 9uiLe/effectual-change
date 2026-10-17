"""Validate the files users actually install, without host or global dependencies."""

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from scripts.distribution import (
    DistributionError,
    SKILL_NAMES,
    local_links,
    metadata,
    validate_documentation,
    validate_manifest,
    validate_package,
)


REPOSITORY = Path(__file__).resolve().parents[1]


class DistributionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()

    def test_shipped_skills_are_complete_and_have_resolvable_local_references(self):
        self.assertEqual([source.name for source in validate_package(REPOSITORY)], list(SKILL_NAMES))

    def test_installed_copy_initializes_a_run_after_source_checkout_is_removed(self):
        checkout = self.root / "checkout"
        for name in ("scripts", "skills", ".claude-plugin"):
            shutil.copytree(REPOSITORY / name, checkout / name,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        project = self.root / "project"
        project.mkdir()
        installed = subprocess.run(
            [sys.executable, str(checkout / "scripts/install.py"), str(project), "--mode", "copy"],
            capture_output=True, text=True,
        )
        self.assertEqual(installed.returncode, 0, installed.stderr)
        shutil.rmtree(checkout)
        brief = project / "brief.txt"
        brief.write_text("Update a setting and verify the saved result.\n", encoding="utf-8")
        for host in (".agents", ".claude"):
            run = project / (host.lstrip(".") + "-run")
            result = subprocess.run(
                [sys.executable, str(project / host / "skills/moletta/scripts/moletta.py"),
                 "init", str(run), "--brief", str(brief), "--goal", "Apply the requested setting"],
                cwd=project, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((run / "brief.md").read_bytes(), brief.read_bytes())
            self.assertEqual(json.loads((run / "intent.json").read_text())["outcomes"][0]["statement"],
                             "Apply the requested setting")
            self.assertTrue((run / "plan.json").is_file())
            self.assertTrue((run / "journal.json").is_file())

    def test_frontmatter_requires_unique_nonempty_scalar_fields(self):
        document = self.root / "SKILL.md"
        for content in (
            "name: moletta\ndescription: Missing delimiters\n",
            "---\nname: moletta\nname: moletta\ndescription: Repeated name\n---\n",
            "---\nname: moletta\ndescription: \n---\n",
            "---\nname: moletta\ndescription: \"\"\n---\n",
            "---\nname: moletta\ndescription: [not, a, string]\n---\n",
            "---\nname: moletta\ndescription: false\n---\n",
            "---\nname: moletta\ndescription: |\n  Multiline value\n---\n",
        ):
            with self.subTest(content=content):
                document.write_text(content, encoding="utf-8")
                with self.assertRaises(DistributionError):
                    metadata(document)

    def test_frontmatter_accepts_quoted_string_values(self):
        document = self.root / "SKILL.md"
        document.write_text("---\nname: \"moletta\"\ndescription: 'A useful: skill.'\n---\n", encoding="utf-8")
        self.assertEqual(metadata(document), {"name": "moletta", "description": "A useful: skill."})

    def test_markdown_links_resolve_encoded_paths_and_ignore_fenced_examples(self):
        (self.root / "File With Spaces.md").write_text("# Details\n", encoding="utf-8")
        document = self.root / "README.md"
        document.write_text(
            "[spaces](File%20With%20Spaces.md#details)\n"
            "[angle](<File With Spaces.md>)\n"
            "[website](https://example.com/missing)\n"
            "```md\n[example](not-created.md)\n```\n", encoding="utf-8"
        )
        self.assertEqual(local_links(document, self.root), [])

    def test_broken_links_and_links_outside_package_are_reported(self):
        document = self.root / "README.md"
        document.write_text("[missing](missing.md)\n[outside](../outside.md)\n", encoding="utf-8")
        errors = local_links(document, self.root)
        self.assertEqual(len(errors), 2)
        self.assertIn("missing local link target", errors[0])
        self.assertIn("escapes", errors[1])

    def test_repository_documentation_checks_nested_documents(self):
        nested = self.root / "docs" / "nested"
        nested.mkdir(parents=True)
        (nested / "guide.md").write_text("[missing](../unavailable.md)\n", encoding="utf-8")
        with self.assertRaises(DistributionError):
            validate_documentation(self.root)

    def test_plugin_manifest_requires_product_identity_and_version(self):
        directory = self.root / ".claude-plugin"
        directory.mkdir()
        manifest = {"name": "moletta", "version": "0.1.0", "description": "Moletta skills.",
                    "author": {"name": "9uiLe"}}
        path = directory / "plugin.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        validate_manifest(self.root)
        for field, invalid in (("name", "different-product"), ("version", "0.1"),
                               ("description", ""), ("author", {})):
            with self.subTest(field=field):
                path.write_text(json.dumps({**manifest, field: invalid}), encoding="utf-8")
                with self.assertRaises(DistributionError):
                    validate_manifest(self.root)


if __name__ == "__main__":
    unittest.main()
