"""Frozen case/rubric validation and allowlisted public packet construction."""

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .validation import (JsonObject, canonical_digest, digest, json_bytes, nonempty, number,
                         objects_by_id, read_json, relative_file, require, strings, write_new_json)

DEFAULT_SUITE = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class SuiteCase:
    case: JsonObject
    rubric: JsonObject
    rubric_sha256: str


Suite = dict[str, SuiteCase]


def load_suite(root: Path = DEFAULT_SUITE) -> Suite:
    root = root.resolve()
    for name in ("cases", "artifacts", "rubrics"):
        require((root / name).is_dir() and not (root / name).is_symlink(),
                f"suite requires a real {name}/ directory")
    cases: Suite = {}
    for path in sorted((root / "cases").glob("*.json")):
        require(not path.is_symlink(), f"case file cannot be a symlink: {path.name}")
        case = read_json(path)
        require(type(case.get("schema_version")) is int and case["schema_version"] == 1,
                f"invalid case schema: {path.name}")
        for field in ("id", "title", "brief"):
            nonempty(case.get(field), f"{path.name}.{field}")
        require(case["id"] == path.stem and case["id"] not in cases, "case id must match its unique filename")
        require(case.get("split") in ("regression", "transfer", "holdout"), f"invalid split: {case['id']}")
        for relative in strings(case.get("artifacts"), "case.artifacts"):
            relative_file(root / "artifacts", relative, "public artifact")
        rubric_path = relative_file(root / "rubrics", path.name, "rubric")
        rubric = read_json(rubric_path)
        require(type(rubric.get("schema_version")) is int and rubric["schema_version"] == 1
                and rubric.get("case_id") == case["id"],
                f"rubric/case mismatch: {case['id']}")
        criteria = objects_by_id(rubric.get("criteria"), "criteria")
        failures = objects_by_id(rubric.get("critical_failures"), "critical_failures")
        require(not criteria.keys() & failures.keys(), "criterion and failure ids must be distinct")
        for item in criteria.values():
            nonempty(item.get("description"), "criterion.description")
            number(item.get("weight"), "criterion.weight", positive=True)
        number(sum(item["weight"] for item in criteria.values()), "total criterion weight", positive=True)
        for item in failures.values():
            nonempty(item.get("description"), "critical_failure.description")
        nonempty(rubric.get("judging_guidance"), "judging_guidance")
        cases[case["id"]] = SuiteCase(case, rubric, digest(rubric_path.read_bytes()))
    require(bool(cases), "suite has no cases")
    return cases


def public_packet(entry: SuiteCase, root: Path = DEFAULT_SUITE) -> tuple[dict[str, bytes], JsonObject]:
    case = entry.case
    public = {field: case[field] for field in ("schema_version", "id", "title", "brief", "artifacts")}
    files = {"case.json": json_bytes(public)}
    for relative in case["artifacts"]:
        files["artifacts/" + relative] = relative_file(root / "artifacts", relative, "public artifact").read_bytes()
    manifest = {"schema_version": 1, "case_id": case["id"],
                "files": {name: digest(data) for name, data in files.items()}}
    manifest["packet_sha256"] = canonical_digest(manifest)
    return files, manifest


def prepare(case_id: str, destination: Path | None = None, root: Path = DEFAULT_SUITE) -> JsonObject:
    suite = load_suite(root)
    require(case_id in suite, f"unknown case: {case_id}")
    files, manifest = public_packet(suite[case_id], root)
    if destination is None:
        target = Path(tempfile.mkdtemp(prefix="moletta-case-"))
    else:
        require(not destination.exists() and not destination.is_symlink(), "destination must not exist")
        target = destination.resolve()
        require(not target.is_relative_to(root.resolve()), "packet must be outside the evaluation tree")
        target.mkdir(parents=True)
    try:
        for name, data in files.items():
            output = target / name
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(data)
        write_new_json(target / "packet-manifest.json", manifest)
    except OSError:
        shutil.rmtree(target)
        raise
    return {"packet": str(target), "case_id": case_id, "packet_sha256": manifest["packet_sha256"],
            "boundary": "Packaging only. The operator must isolate solver files and context from evaluator material."}
