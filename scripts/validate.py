#!/usr/bin/env python3
"""Validate the shipped package, corpus and deterministic tests without external tools."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from distribution import DistributionError, validate_documentation, validate_package


def main() -> int:
    if sys.version_info < (3, 11):
        print("Python 3.11 or newer is required", file=sys.stderr)
        return 1
    repository = Path(__file__).resolve().parents[1]
    try:
        sources = validate_package(repository)
        validate_documentation(repository)
    except (DistributionError, OSError, ValueError) as error:
        print(f"Distribution validation failed: {error}", file=sys.stderr)
        return 1
    print(f"Validated {len(sources)} skills, plugin manifest and local documentation links.", flush=True)
    commands = (
        [sys.executable, str(repository / "evaluation" / "evaluate.py"), "validate"],
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
    )
    for command in commands:
        result = subprocess.run(command, cwd=repository, check=False)
        if result.returncode:
            return result.returncode
    print("Deterministic validation passed. Agent decision quality requires behavioral evaluation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
