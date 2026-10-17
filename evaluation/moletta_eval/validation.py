"""Shared JSON and file-boundary primitives for evaluator inputs."""

import hashlib
import json
import math
from pathlib import Path, PurePosixPath
from typing import Any

JsonObject = dict[str, Any]


class Invalid(ValueError):
    """An evaluator input does not meet the public contract."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise Invalid(message)


def object_value(value: Any, label: str) -> JsonObject:
    require(isinstance(value, dict), f"{label} must be an object")
    return value


def nonempty(value: Any, label: str) -> str:
    require(isinstance(value, str) and bool(value.strip()), f"{label} must be a nonempty string")
    return value


def number(value: Any, label: str, *, integer: bool = False, positive: bool = False) -> int | float:
    require(type(value) in ((int,) if integer else (int, float)), f"{label} must be numeric")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    require(finite and value >= 0, f"{label} must be finite and nonnegative")
    require(not positive or value > 0, f"{label} must be positive")
    return value


def sha(value: Any, label: str) -> str:
    require(isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value),
            f"{label} must be a lowercase SHA-256")
    return value


def objects_by_id(items: Any, label: str) -> dict[str, JsonObject]:
    require(isinstance(items, list) and bool(items), f"{label} must be a nonempty list")
    result: dict[str, JsonObject] = {}
    for item in items:
        item = object_value(item, f"{label} entry")
        key = nonempty(item.get("id"), f"{label}.id")
        require(key not in result, f"duplicate {label} id: {key}")
        result[key] = item
    return result


def strings(value: Any, label: str) -> list[str]:
    require(isinstance(value, list), f"{label} must be a list")
    for item in value:
        nonempty(item, f"{label} entry")
    require(len(value) == len(set(value)), f"{label} must contain unique strings")
    return value


def _unique_object(pairs: list[tuple[str, Any]]) -> JsonObject:
    result: JsonObject = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _invalid_constant(value: str) -> None:
    raise Invalid(f"nonstandard JSON number: {value}")


def read_json(path: Path) -> JsonObject:
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object,
                           parse_constant=_invalid_constant)
        return object_value(value, str(path))
    except (OSError, UnicodeError, ValueError) as error:
        raise Invalid(f"{path}: {error}") from error


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def write_new_json(path: Path, value: Any) -> None:
    """Exclusive creation keeps evidence and verdict files immutable by this tool."""
    with path.open("xb") as output:
        output.write(json_bytes(value))


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_digest(value: Any) -> str:
    return digest(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                             allow_nan=False).encode("utf-8"))


def relative_file(base: Path, relative: Any, label: str) -> Path:
    """Accept only canonical portable paths to real files inside one bundle."""
    name = nonempty(relative, label)
    portable = PurePosixPath(name)
    require(not portable.is_absolute() and name == portable.as_posix() and "\\" not in name
            and ":" not in name and not any(part in (".", "..") for part in portable.parts),
            f"{label} must be a canonical relative path without traversal")
    require(bool(portable.parts), f"{label} must name a file")
    require(not base.is_symlink(), f"{label} directory cannot be a symlink")
    current = base
    for part in portable.parts:
        current = current / part
        require(not current.is_symlink(), f"{label} cannot use symlinks: {name}")
    require(current.is_file(), f"missing {label}: {name}")
    return current
