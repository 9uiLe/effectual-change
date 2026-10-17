"""The local skill distribution contract shared by installation and validation."""

from __future__ import annotations

import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit


SKILL_NAMES = (
    "moletta",
    "moletta-explore",
    "moletta-compare",
    "moletta-verify",
    "moletta-learn",
)


class DistributionError(ValueError):
    """A checkout is not a complete, internally consistent skill distribution."""


def scalar(value: str, path: Path, key: str) -> str:
    """Accept plain text and quoted string values, excluding YAML collections/types."""
    if value.startswith('"'):
        try:
            decoded = json.loads(value)
        except ValueError as error:
            raise DistributionError(f"{path}: {key} must be a single-line string") from error
    elif value.startswith("'") and value.endswith("'"):
        decoded = value[1:-1].replace("''", "'")
    elif (not value or value[0] in "[]{}|>&*!@`'" or re.search(r":(?:\s|$)", value)
          or value in {"null", "Null", "NULL", "~", "true", "false", "True", "False"}
          or re.fullmatch(r"[-+]?\d+(?:\.\d+)?", value)):
        raise DistributionError(f"{path}: {key} must be a nonempty single-line string")
    else:
        decoded = value
    if not isinstance(decoded, str) or not decoded.strip():
        raise DistributionError(f"{path}: {key} must be a nonempty single-line string")
    return decoded


def metadata(path: Path) -> dict[str, str]:
    """Read the package's deliberately small, single-line frontmatter format."""
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---" or "---" not in lines[1:]:
        raise DistributionError(f"{path}: expected frontmatter delimited by ---")
    fields = {}
    for line in lines[1:lines.index("---", 1)]:
        key, separator, value = line.partition(":")
        if not separator or key not in {"name", "description"} or key in fields:
            raise DistributionError(f"{path}: use one name and one single-line description")
        fields[key] = scalar(value.strip(), path, key)
    if set(fields) != {"name", "description"}:
        raise DistributionError(f"{path}: both name and description are required")
    return fields


def local_links(path: Path, boundary: Path) -> list[str]:
    """Check local Markdown destinations; external links require no network access."""
    errors = []
    text = path.read_text(encoding="utf-8")
    # Examples inside fenced blocks are literals, not document navigation.
    text = re.sub(r"(?ms)^(`{3,}|~{3,})[^\n]*\n.*?^\1\s*$", "", text)
    for match in re.finditer(r"!?\[[^\]\n]*\]\((<[^>\n]+>|[^\s)]+)(?:\s+\"[^\"]*\")?\)", text):
        destination = match.group(1).strip("<>")
        parts = urlsplit(destination)
        if parts.scheme or parts.netloc or not parts.path:
            continue
        relative = Path(unquote(parts.path))
        target = (path.parent / relative).resolve()
        if relative.is_absolute() or not target.is_relative_to(boundary.resolve()):
            errors.append(f"{path}: local link escapes the distribution: {destination}")
        elif not target.exists():
            errors.append(f"{path}: missing local link target: {destination}")
    return errors


def skill_sources(repository: Path) -> list[Path]:
    """Validate the complete installed family before exposing any source paths."""
    directory = repository / "skills"
    found = {path.name for path in directory.iterdir() if path.is_dir() or path.is_symlink()}
    if found != set(SKILL_NAMES):
        missing = sorted(set(SKILL_NAMES) - found)
        unexpected = sorted(found - set(SKILL_NAMES))
        raise DistributionError(f"Incomplete skill package; missing={missing}, unexpected={unexpected}")
    sources = [directory / name for name in SKILL_NAMES]
    for source in sources:
        if source.is_symlink() or not source.is_dir():
            raise DistributionError(f"Skill source must be a regular directory: {source}")
        for entry in source.rglob("*"):
            if entry.is_symlink():
                raise DistributionError(f"Skill source must not contain symlinks: {entry}")
        values = metadata(source / "SKILL.md")
        if values["name"] != source.name:
            raise DistributionError(f"{source}: frontmatter name must equal its folder name")
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", values["name"]):
            raise DistributionError(f"{source}: invalid skill name")
        for document in source.rglob("*.md"):
            errors = local_links(document, directory)
            if errors:
                raise DistributionError("\n".join(errors))
    helper = directory / "moletta" / "scripts" / "moletta.py"
    if not helper.is_file() or helper.is_symlink():
        raise DistributionError(f"Missing runtime entrypoint: {helper}")
    return sources


def validate_manifest(repository: Path) -> None:
    path = repository / ".claude-plugin" / "plugin.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("name") != "moletta":
        raise DistributionError(f"{path}: plugin name must be moletta")
    if not re.fullmatch(r"\d+\.\d+\.\d+", str(manifest.get("version", ""))):
        raise DistributionError(f"{path}: version must be major.minor.patch")
    if not isinstance(manifest.get("description"), str) or not manifest["description"].strip():
        raise DistributionError(f"{path}: description must be nonempty")
    author = manifest.get("author")
    if not isinstance(author, dict) or not isinstance(author.get("name"), str) or not author["name"].strip():
        raise DistributionError(f"{path}: author.name must be nonempty")


def validate_package(repository: Path) -> list[Path]:
    sources = skill_sources(repository)
    validate_manifest(repository)
    return sources


def validate_documentation(repository: Path) -> None:
    errors = []
    for document in repository.rglob("*.md"):
        if any(part.startswith(".") or part == "__pycache__" for part in document.relative_to(repository).parts):
            continue
        errors.extend(local_links(document, repository))
    if errors:
        raise DistributionError("\n".join(errors))
