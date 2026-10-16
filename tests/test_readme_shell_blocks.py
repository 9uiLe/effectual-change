"""Keep documented shell snippets safe to paste into interactive zsh."""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHELL_LANGUAGES = {"bash", "sh", "shell", "zsh"}
FENCED_BLOCK = re.compile(
    r"^[ \t]*(?P<fence>`{3,}|~{3,})(?P<info>[^`~\n]*)\n"
    r"(?P<body>.*?)^[ \t]*(?P=fence)[ \t]*$",
    re.MULTILINE | re.DOTALL,
)


class ReadmeShellBlockTests(unittest.TestCase):
    def test_shell_blocks_have_no_comment_only_lines(self):
        markdown_files = (
            path
            for path in ROOT.rglob("*.md")
            if ".git" not in path.relative_to(ROOT).parts
        )
        for path in markdown_files:
            text = path.read_text(encoding="utf-8")
            for block in FENCED_BLOCK.finditer(text):
                if block.group("info").strip() not in SHELL_LANGUAGES:
                    continue
                first_line = text.count("\n", 0, block.start("body")) + 1
                for offset, line in enumerate(block.group("body").splitlines()):
                    if line.lstrip().startswith("#"):
                        self.fail(
                            f"{path.relative_to(ROOT)}:{first_line + offset}: "
                            "interactive zsh may execute comment lines as commands."
                        )


if __name__ == "__main__":
    unittest.main()
