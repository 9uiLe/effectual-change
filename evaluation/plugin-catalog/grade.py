#!/usr/bin/env python3
"""Black-box acceptance checks for the 9uiLe/plugins catalog-validator benchmark.

Requires only Python 3, Bash, and jq. Run against a *finished* isolated agent
checkout. This grader reads candidate scripts, but never changes the checkout.

WARNING: The candidate's Bash code will execute inside an ephemeral fixture.
Use an isolated, unprivileged environment without credentials or network access.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

REQUIRED = (
    "scripts/verify-plugin-catalog.sh",
    "scripts/lib/version.sh",
    "scripts/lib/common.sh",
)
TIMEOUT_SECONDS = 15


def catalog_row(plugin: str, title: str | None = None) -> str:
    return f"| [{title or plugin}](./plugins/{plugin}/README.md) | {plugin} |"


def fixture_readme(rows: list[str], prose_links: bool = False) -> str:
    body = "\n".join(("# Fixture", "", "| Plugin | Purpose |", "| --- | --- |", *rows, ""))
    if prose_links:
        body += "\nDetails: [alpha](./plugins/alpha/README.md), [alpha](./plugins/alpha/README.md).\n"
    return body


# Test names and assertions are kept outside the trial worktrees. Editing the
# candidate's own tests does not influence these cases.
CASES = (
    {
        "name": "valid_multiple_plugins",
        "rows": [catalog_row("alpha"), catalog_row("bravo")],
        "marketplace": ["alpha", "bravo"],
        "expected_success": True,
    },
    {
        "name": "duplicate_same_row",
        "rows": [catalog_row("alpha"), catalog_row("alpha"), catalog_row("bravo")],
        "marketplace": ["alpha", "bravo"],
        "expected_success": False,
        "expected_diagnostic": "alpha",
    },
    {
        "name": "duplicate_different_labels",
        "rows": [catalog_row("alpha", "Alpha"), catalog_row("alpha", "Alpha v2")],
        "marketplace": ["alpha"],
        "expected_success": False,
        "expected_diagnostic": "alpha",
    },
    {
        "name": "duplicate_second_plugin",
        "rows": [catalog_row("alpha"), catalog_row("bravo"), catalog_row("bravo", "B")],
        "marketplace": ["alpha", "bravo"],
        "expected_success": False,
        "expected_diagnostic": "bravo",
    },
    {
        "name": "regular_prose_links_are_not_table_rows",
        "rows": [catalog_row("alpha"), catalog_row("bravo")],
        "marketplace": ["alpha", "bravo"],
        "prose_links": True,
        "expected_success": True,
    },
    {
        "name": "missing_marketplace_plugin_still_fails",
        "rows": [catalog_row("alpha")],
        "marketplace": ["alpha", "bravo"],
        "expected_success": False,
        "expected_diagnostic": "bravo",
    },
    {
        "name": "unlisted_catalog_plugin_still_fails",
        "rows": [catalog_row("alpha"), catalog_row("bravo")],
        "marketplace": ["alpha"],
        "expected_success": False,
        "expected_diagnostic": "bravo",
    },
    {
        "name": "missing_linked_readme_still_fails",
        "rows": [catalog_row("alpha")],
        "marketplace": ["alpha"],
        "missing_readmes": ["alpha"],
        "expected_success": False,
        "expected_diagnostic": "alpha",
    },
)


def score_case(candidate: Path, case: dict, scratch: Path) -> dict:
    scratch.mkdir(parents=True)
    for relative in REQUIRED:
        destination = scratch / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(candidate / relative, destination)

    (scratch / ".claude-plugin").mkdir()
    marketplace = {
        "plugins": [
            {"name": plugin, "source": f"./plugins/{plugin}"}
            for plugin in case["marketplace"]
        ]
    }
    (scratch / ".claude-plugin/marketplace.json").write_text(
        json.dumps(marketplace, ensure_ascii=False), encoding="utf-8"
    )
    (scratch / "README.md").write_text(
        fixture_readme(case["rows"], case.get("prose_links", False)), encoding="utf-8"
    )
    for plugin in set(case["marketplace"]) | {"alpha", "bravo"}:
        readme = scratch / "plugins" / plugin / "README.md"
        readme.parent.mkdir(parents=True, exist_ok=True)
        if plugin not in case.get("missing_readmes", []):
            readme.write_text(f"# {plugin}\n", encoding="utf-8")

    # Do not forward secrets or tool-specific credentials to code under test.
    environment = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(scratch),
        "LC_ALL": "C",
        "LANG": "C",
    }
    try:
        completed = subprocess.run(
            ["bash", str(scratch / "scripts/verify-plugin-catalog.sh")],
            cwd=scratch,
            env=environment,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            check=False,
        )
        exit_code = completed.returncode
        diagnostic = (completed.stderr + "\n" + completed.stdout).strip()
        success = exit_code == 0
        passed = success == case["expected_success"]
        needle = case.get("expected_diagnostic")
        if needle and needle.lower() not in diagnostic.lower():
            passed = False
        return {
            "case": case["name"],
            "passed": passed,
            "exit_code": exit_code,
            "expected_success": case["expected_success"],
            "diagnostic": diagnostic[:1200],
        }
    except subprocess.TimeoutExpired:
        return {"case": case["name"], "passed": False, "error": "timeout"}


def grade(candidate: Path) -> dict:
    missing = [p for p in REQUIRED if not (candidate / p).is_file()]
    if missing:
        raise ValueError(f"Candidate checkout is missing files: {missing}")
    if shutil.which("bash") is None or shutil.which("jq") is None:
        raise RuntimeError("Bash and jq are required; do not count missing tools as model failure")

    with tempfile.TemporaryDirectory(prefix="effectual-grade-") as directory:
        base = Path(directory)
        cases = [
            score_case(candidate, case, base / f"case-{i:02d}")
            for i, case in enumerate(CASES)
        ]

    return {
        "candidate": str(candidate),
        "grading": "black-box, isolated fixtures; no mutation of candidate checkout",
        "passed": sum(bool(result["passed"]) for result in cases),
        "total": len(cases),
        "cases": cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True, help="Completed isolated checkout")
    parser.add_argument("--output", type=Path, help="Optional JSON result file outside the candidate")
    args = parser.parse_args()
    result = grade(args.candidate.resolve())
    encoded = json.dumps(result, ensure_ascii=False, indent=2)
    print(encoded)
    if args.output:
        args.output.write_text(encoded + "\n", encoding="utf-8")
    return 0 if result["passed"] == result["total"] else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, RuntimeError) as exc:
        print(f"PRECONDITION FAILED: {exc}", file=sys.stderr)
        sys.exit(2)
