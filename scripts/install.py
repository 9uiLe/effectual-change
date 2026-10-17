#!/usr/bin/env python3
"""Install the complete local Moletta skill set into one project."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import sys

from distribution import DistributionError, validate_package

HOST_DIRS = {"codex": ".agents", "claude": ".claude"}


class InstallError(Exception):
    """An installation cannot proceed without changing an existing entry."""


@dataclass(frozen=True)
class Target:
    source: Path
    destination: Path
    unchanged: bool


def preflight(project: Path, sources: list[Path], hosts: list[str], mode: str) -> list[Target]:
    """Inspect every parent and destination before creating any project entries."""
    if not project.is_dir():
        raise InstallError(f"Project must be an existing directory: {project}")
    if project in {Path.home().resolve(), Path(project.anchor)}:
        raise InstallError("Choose a project directory; global installation is not supported")

    targets = []
    conflicts = []
    for host in hosts:
        host_dir = project / HOST_DIRS[host]
        skill_dir = host_dir / "skills"
        for parent in (host_dir, skill_dir):
            if parent.is_symlink() or (os.path.lexists(parent) and not parent.is_dir()):
                conflicts.append(f"Skill parent must be a regular directory: {parent}")
        for source in sources:
            destination = skill_dir / source.name
            unchanged = False
            if os.path.lexists(destination):
                # Resolve relative and absolute links alike. Dangling or foreign
                # links are conflicts, even though Path.exists() returns false.
                try:
                    unchanged = (mode == "symlink" and destination.is_symlink()
                                 and destination.resolve(strict=True) == source.resolve())
                except (OSError, RuntimeError):
                    unchanged = False
                if not unchanged:
                    conflicts.append(f"Refusing to replace existing skill: {destination}")
            targets.append(Target(source, destination, unchanged))
    if conflicts:
        raise InstallError("\n".join(conflicts))
    return targets


def install(targets: list[Target], mode: str) -> None:
    for target in targets:
        if target.unchanged:
            print(f"Already linked: {target.destination}")
            continue
        target.destination.parent.mkdir(parents=True, exist_ok=True)
        if mode == "symlink":
            target.destination.symlink_to(target.source, target_is_directory=True)
        else:
            shutil.copytree(target.source, target.destination, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        print(f"Installed ({mode}): {target.destination}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Install the complete Moletta skill family into one existing project. "
            "Uses only local files; no downloads or configuration edits."
        ),
        epilog=(
            "Existing unrelated entries, including dangling links, stop the entire install "
            "before any project changes. Links to this checkout are idempotent. Copy mode "
            "refuses existing copied directories; review and remove them explicitly before updating. "
            "Uninstall by removing only the installed skill links (or reviewed copies)."
        ),
    )
    parser.add_argument("project", type=Path, help="existing project directory (global install is unsupported)")
    parser.add_argument(
        "--host", choices=("both", "codex", "claude"), default="both",
        help="Codex uses .agents/skills; Claude Code uses .claude/skills (default: both)",
    )
    parser.add_argument(
        "--mode", choices=("symlink", "copy"), default="symlink",
        help="symlink keeps this checkout as the maintained source; copy is portable (default: symlink)",
    )
    args = parser.parse_args(argv)
    if sys.version_info < (3, 11):
        parser.exit(1, "Python 3.11 or newer is required\n")
    hosts = list(HOST_DIRS) if args.host == "both" else [args.host]
    repository = Path(__file__).resolve().parents[1]
    try:
        sources = validate_package(repository)
        targets = preflight(args.project.expanduser().resolve(), sources, hosts, args.mode)
        install(targets, args.mode)
    except (InstallError, DistributionError, OSError, RuntimeError) as error:
        parser.exit(1, f"Installation failed: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
