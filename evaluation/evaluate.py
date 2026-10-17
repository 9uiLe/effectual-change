#!/usr/bin/env python3
"""Package public cases and compare externally judged runs; never judge prose."""

import argparse
import hashlib
import json
import math
import tempfile
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
RATINGS = {"missed": 0, "partial": 0.5, "met": 1}
CONTROL_FIELDS = ("model", "effort", "tools", "environment_id", "budget", "control_prompt_sha256")


class Invalid(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise Invalid(message)


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise Invalid(f"{path}: {error}") from error


def write_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical_digest(data):
    return digest(json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode())


def nonempty(value, label):
    require(isinstance(value, str) and bool(value.strip()), f"{label} must be a nonempty string")


def number(value, label, integer=False, positive=False):
    require(type(value) in ((int,) if integer else (int, float)), f"{label} must be numeric")
    require(math.isfinite(value) and value >= 0, f"{label} must be finite and nonnegative")
    if positive:
        require(value > 0, f"{label} must be positive")


def sha(value, label):
    require(isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value),
            f"{label} must be a lowercase SHA-256")


def objects_by_id(items, label):
    require(isinstance(items, list) and bool(items), f"{label} must be a nonempty list")
    result = {}
    for item in items:
        require(isinstance(item, dict), f"{label} entries must be objects")
        nonempty(item.get("id"), f"{label}.id")
        require(item["id"] not in result, f"duplicate {label} id: {item['id']}")
        result[item["id"]] = item
    return result


def safe_artifact(root, relative):
    nonempty(relative, "artifact path")
    name = Path(relative)
    require(not name.is_absolute() and ".." not in name.parts, "artifact paths must stay relative")
    require(not (root / "artifacts").is_symlink(), "public artifact directory cannot be a symlink")
    base = (root / "artifacts").resolve()
    path = base / name
    # Reject links, including links in intermediate directories, before resolving.
    require(not any(part.is_symlink() for part in (path, *path.parents) if part != base.parent),
            f"artifact symlink is not allowed: {relative}")
    require(path.resolve().is_relative_to(base) and path.is_file(), f"missing public artifact: {relative}")
    return path


def load_suite(root=ROOT):
    root = Path(root).resolve()
    cases = {}
    for path in sorted((root / "cases").glob("*.json")):
        case = read_json(path)
        require(isinstance(case, dict) and case.get("schema_version") == 1, f"invalid case: {path}")
        for field in ("id", "title", "brief"):
            nonempty(case.get(field), f"{path.name}.{field}")
        require(case["id"] == path.stem and case["id"] not in cases, "case id must match unique filename")
        require(case.get("split") in ("regression", "holdout"), f"invalid split: {case['id']}")
        require(isinstance(case.get("artifacts"), list), "artifacts must be a list")
        require(len(case["artifacts"]) == len(set(case["artifacts"])), "duplicate public artifact")
        for relative in case["artifacts"]:
            safe_artifact(root, relative)
        rubric_path = root / "rubrics" / path.name
        rubric = read_json(rubric_path)
        require(rubric.get("schema_version") == 1 and rubric.get("case_id") == case["id"],
                f"rubric/case mismatch: {case['id']}")
        for item in objects_by_id(rubric.get("criteria"), "criteria").values():
            nonempty(item.get("description"), "criterion.description")
            number(item.get("weight"), "criterion.weight", positive=True)
        for item in objects_by_id(rubric.get("critical_failures"), "critical_failures").values():
            nonempty(item.get("description"), "critical_failure.description")
        nonempty(rubric.get("judging_guidance"), "judging_guidance")
        cases[case["id"]] = {"case": case, "rubric": rubric, "rubric_sha256": digest(rubric_path.read_bytes())}
    require(bool(cases), "suite has no cases")
    require(any(entry["case"]["split"] == "holdout" for entry in cases.values()), "suite needs a holdout")
    return cases


def public_packet(entry, root=ROOT):
    case = entry["case"]
    # Deliberately allowlist fields: adding a private field to a case cannot leak it.
    public = {field: case[field] for field in ("schema_version", "id", "title", "brief", "artifacts")}
    files = {"case.json": (json.dumps(public, indent=2, ensure_ascii=False) + "\n").encode()}
    for relative in case["artifacts"]:
        files["artifacts/" + relative] = safe_artifact(Path(root), relative).read_bytes()
    manifest = {"schema_version": 1, "case_id": case["id"],
                "files": {name: digest(data) for name, data in files.items()}}
    manifest["packet_sha256"] = canonical_digest(manifest)
    return files, manifest


def prepare(case_id, destination=None, root=ROOT):
    suite = load_suite(root)
    require(case_id in suite, f"unknown case: {case_id}")
    files, manifest = public_packet(suite[case_id], root)
    if destination is None:
        target = Path(tempfile.mkdtemp(prefix="moletta-case-"))
    else:
        target = Path(destination).resolve()
        require(not target.exists(), "destination must not exist")
        require(not target.is_relative_to(Path(root).resolve()), "packet must be outside the evaluation tree")
        target.mkdir(parents=True)
    for name, data in files.items():
        output = target / name
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(data)
    write_json(target / "packet-manifest.json", manifest)
    return {"packet": str(target), "case_id": case_id, "packet_sha256": manifest["packet_sha256"],
            "warning": "Grant the solver access only to this packet and its isolated workspace; rubrics stay evaluator-only."}


def template(arm, include_holdout=False, root=ROOT):
    suite = load_suite(root)
    rows = []
    for case_id, entry in suite.items():
        if entry["case"]["split"] == "holdout" and not include_holdout:
            continue
        _, manifest = public_packet(entry, root)
        rows.append({"id": case_id, "packet_sha256": manifest["packet_sha256"],
                     "rubric_sha256": entry["rubric_sha256"],
                     "artifacts": [],
                     "metrics": {"wall_seconds": None, "solver_turns": None, "input_tokens": None,
                                 "output_tokens": None, "cost_usd": None},
                     "criteria": [{"id": c["id"], "rating": None, "evidence": []}
                                  for c in entry["rubric"]["criteria"]],
                     "critical_failures": [{"id": c["id"], "occurred": None, "evidence": []}
                                           for c in entry["rubric"]["critical_failures"]],
                     "process_assessment": {"unnecessary_process": None, "evidence": []}})
    return {"schema_version": 1, "arm": arm, "evaluation_id": "",
            "configuration": {"label": "", "skill_revision": "", "model": "", "effort": "", "tools": [],
                              "environment_id": "", "control_prompt_sha256": "",
                              "budget": {"max_tokens": None, "max_seconds": None, "max_turns": None}},
            "judge": {"id": "", "independent_of_solver": False, "judged_at": ""}, "cases": rows}


def check_evidence(rows, artifact_paths, label):
    require(isinstance(rows, list) and bool(rows), f"{label} needs observational evidence")
    for row in rows:
        require(isinstance(row, dict), f"{label} evidence must be an object")
        require(row.get("artifact") in artifact_paths, f"{label} evidence must refer to a registered artifact")
        nonempty(row.get("location"), f"{label}.location")
        nonempty(row.get("observation"), f"{label}.observation")


def validate_run(path, expected_arm, suite, root=ROOT):
    path = Path(path).resolve()
    run = read_json(path)
    require(run.get("schema_version") == 1 and run.get("arm") == expected_arm, f"invalid {expected_arm} run")
    nonempty(run.get("evaluation_id"), "evaluation_id")
    config = run.get("configuration", {})
    for field in ("label", "skill_revision", "model", "effort", "environment_id"):
        nonempty(config.get(field), f"configuration.{field}")
    sha(config.get("control_prompt_sha256"), "control_prompt_sha256")
    require(isinstance(config.get("tools"), list) and len(config["tools"]) == len(set(config["tools"])),
            "tools must be a unique list")
    for tool in config["tools"]:
        nonempty(tool, "tool")
    budget = config.get("budget", {})
    for field in ("max_tokens", "max_seconds", "max_turns"):
        number(budget.get(field), f"budget.{field}", integer=field != "max_seconds", positive=True)
    judge = run.get("judge", {})
    nonempty(judge.get("id"), "judge.id")
    require(judge.get("independent_of_solver") is True, "judge must declare independence from solver")
    try:
        judged_at = datetime.fromisoformat(judge.get("judged_at", "").replace("Z", "+00:00"))
        require(judged_at.tzinfo is not None, "judged_at requires a timezone")
    except (ValueError, AttributeError) as error:
        raise Invalid("judged_at must be an ISO-8601 datetime with timezone") from error
    cases = objects_by_id(run.get("cases"), "run.cases")
    summaries = {}
    for case_id, case in cases.items():
        require(case_id in suite, f"unknown scored case: {case_id}")
        entry = suite[case_id]
        _, manifest = public_packet(entry, root)
        require(case.get("packet_sha256") == manifest["packet_sha256"], f"public packet changed: {case_id}")
        require(case.get("rubric_sha256") == entry["rubric_sha256"], f"rubric changed: {case_id}")
        artifacts = case.get("artifacts")
        require(isinstance(artifacts, list) and bool(artifacts), f"{case_id} needs retained raw artifacts")
        artifact_paths = set()
        roles = set()
        for artifact in artifacts:
            nonempty(artifact.get("path"), "artifact.path")
            require(artifact["path"] not in artifact_paths, "duplicate retained artifact")
            sha(artifact.get("sha256"), "artifact.sha256")
            target = path.parent / artifact["path"]
            require(target.is_file() and digest(target.read_bytes()) == artifact["sha256"],
                    f"missing or changed run artifact: {target}")
            require(artifact.get("role") in ("transcript", "result", "usage"), "invalid retained artifact role")
            artifact_paths.add(artifact["path"])
            roles.add(artifact["role"])
        require("transcript" in roles, "retain the solver transcript, including tool results")
        rubric = entry["rubric"]
        criteria = objects_by_id(case.get("criteria"), "scored criteria")
        expected_criteria = objects_by_id(rubric["criteria"], "rubric criteria")
        require(criteria.keys() == expected_criteria.keys(), f"criteria set mismatch: {case_id}")
        weighted = 0
        weight = 0
        for criterion_id, score in criteria.items():
            require(score.get("rating") in RATINGS, f"invalid rating: {criterion_id}")
            check_evidence(score.get("evidence"), artifact_paths, criterion_id)
            criterion_weight = expected_criteria[criterion_id]["weight"]
            weighted += RATINGS[score["rating"]] * criterion_weight
            weight += criterion_weight
        failures = objects_by_id(case.get("critical_failures"), "scored critical failures")
        require(failures.keys() == objects_by_id(rubric["critical_failures"], "rubric critical failures").keys(),
                f"critical failure set mismatch: {case_id}")
        occurred = []
        for failure_id, failure in failures.items():
            require(type(failure.get("occurred")) is bool, "critical failure verdict must be boolean")
            check_evidence(failure.get("evidence"), artifact_paths, failure_id)
            if failure["occurred"]:
                occurred.append(failure_id)
        process = case.get("process_assessment", {})
        require(type(process.get("unnecessary_process")) is bool, "process assessment must be boolean")
        check_evidence(process.get("evidence"), artifact_paths, "process assessment")
        metrics = case.get("metrics", {})
        for field in ("wall_seconds", "solver_turns", "input_tokens", "output_tokens"):
            number(metrics.get(field), f"metrics.{field}", integer=field != "wall_seconds")
        require("cost_usd" in metrics, "cost_usd must be explicit; use null if unavailable")
        if metrics["cost_usd"] is not None:
            number(metrics["cost_usd"], "cost_usd")
        over_budget = (metrics["wall_seconds"] > budget["max_seconds"] or
                       metrics["solver_turns"] > budget["max_turns"] or
                       metrics["input_tokens"] + metrics["output_tokens"] > budget["max_tokens"])
        summaries[case_id] = {"score": round(100 * weighted / weight, 6), "critical_failures": occurred,
                              "unnecessary_process": process["unnecessary_process"], "metrics": metrics,
                              "over_budget": over_budget, "split": entry["case"]["split"]}
    return run, summaries


def total_metrics(summaries):
    rows = [case["metrics"] for case in summaries.values()]
    totals = {key: sum(row[key] for row in rows) for key in ("wall_seconds", "solver_turns", "input_tokens", "output_tokens")}
    known_costs = [row["cost_usd"] for row in rows if row["cost_usd"] is not None]
    totals["cost_usd"] = sum(known_costs) if len(known_costs) == len(rows) else None
    totals["known_cost_subtotal_usd"] = sum(known_costs) if known_costs else None
    totals["cases_with_unknown_cost"] = len(rows) - len(known_costs)
    return totals


def compare(baseline_path, candidate_path, root=ROOT):
    suite = load_suite(root)
    baseline, before = validate_run(baseline_path, "baseline", suite, root)
    candidate, after = validate_run(candidate_path, "candidate", suite, root)
    require(baseline["evaluation_id"] == candidate["evaluation_id"], "evaluation ids must match")
    require(before.keys() == after.keys(), "baseline and candidate must contain exactly the same cases")
    control_differences = [field for field in CONTROL_FIELDS
                           if (sorted(baseline["configuration"][field]) if field == "tools" else baseline["configuration"][field]) !=
                           (sorted(candidate["configuration"][field]) if field == "tools" else candidate["configuration"][field])]
    reasons = []
    if control_differences:
        reasons.append("Baseline/candidate control conditions differ: " + ", ".join(control_differences))
    missing = sorted(set(suite) - set(before))
    if missing:
        reasons.append("Full frozen suite, including holdout, was not evaluated: " + ", ".join(missing))
    pairs = []
    for case_id in sorted(before):
        b, c = before[case_id], after[case_id]
        delta = round(c["score"] - b["score"], 6)
        pairs.append({"id": case_id, "split": c["split"], "baseline": b, "candidate": c, "score_delta": delta})
        if c["critical_failures"]:
            reasons.append(f"Critical-failure veto: {case_id}: {', '.join(c['critical_failures'])}")
        if delta < 0:
            reasons.append(f"Case score regressed: {case_id}")
        if c["unnecessary_process"] and not b["unnecessary_process"]:
            reasons.append(f"New process false positive: {case_id}")
        if b["over_budget"] or c["over_budget"]:
            reasons.append(f"A paired run exceeded its resource budget: {case_id}")
    baseline_mean = sum(c["score"] for c in before.values()) / len(before)
    candidate_mean = sum(c["score"] for c in after.values()) / len(after)
    if candidate_mean <= baseline_mean:
        reasons.append("No aggregate behavioral improvement was judged")
    return {"schema_version": 1, "evaluation_id": baseline["evaluation_id"],
            "report_kind": "comparison_of_external_behavioral_judgments",
            "limitations": ["Scores express the external judge's observations, not programmatically verified semantic truth.",
                            "Judge independence and resource measurements are declared by the operator; this script cannot establish them.",
                            "Structural tests validate packaging, schema, integrity, pairing and arithmetic; they do not measure harness efficacy.",
                            "A small suite is not statistical proof of general improvement."],
            "comparable_controls": not control_differences, "control_differences": control_differences,
            "judges": {"baseline": baseline["judge"], "candidate": candidate["judge"]},
            "configurations": {"baseline": baseline["configuration"], "candidate": candidate["configuration"]},
            "pairs": pairs,
            "aggregate": {"baseline_mean_score": round(baseline_mean, 6), "candidate_mean_score": round(candidate_mean, 6),
                          "score_delta": round(candidate_mean - baseline_mean, 6),
                          "baseline_process_false_positives": sum(c["unnecessary_process"] for c in before.values()),
                          "candidate_process_false_positives": sum(c["unnecessary_process"] for c in after.values()),
                          "baseline_metrics": total_metrics(before), "candidate_metrics": total_metrics(after)},
            "promotion": {"status": "blocked" if reasons else "eligible_for_review", "automatic_promotion": False,
                          "reasons": reasons}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate", help="validate case/rubric structure; no agent is run")
    listing = commands.add_parser("list")
    listing.add_argument("--include-holdout", action="store_true")
    packet = commands.add_parser("prepare", help="copy only public material into a new isolated directory")
    packet.add_argument("case_id")
    packet.add_argument("--dest")
    skeleton = commands.add_parser("template", help="write evaluator-only, incomplete verdict structure")
    skeleton.add_argument("--arm", choices=("baseline", "candidate"), required=True)
    skeleton.add_argument("--include-holdout", action="store_true")
    skeleton.add_argument("--output", required=True)
    grading = commands.add_parser("grade", help="compare retained artifacts and independent external judgments")
    grading.add_argument("--baseline", required=True)
    grading.add_argument("--candidate", required=True)
    grading.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        if args.command == "validate":
            suite = load_suite()
            result = {"structural_validation": "passed", "case_count": len(suite), "behavioral_runs_performed": 0}
        elif args.command == "list":
            result = [{"id": key, "title": entry["case"]["title"], "split": entry["case"]["split"]}
                      for key, entry in load_suite().items()
                      if args.include_holdout or entry["case"]["split"] == "regression"]
        elif args.command == "prepare":
            result = prepare(args.case_id, args.dest)
        elif args.command == "template":
            require(not Path(args.output).exists(), "refusing to overwrite an existing verdict file")
            write_json(args.output, template(args.arm, args.include_holdout))
            result = {"template": args.output, "status": "incomplete; not a behavioral result"}
        else:
            result = compare(args.baseline, args.candidate)
            require(not Path(args.output).exists(), "refusing to overwrite an existing report")
            require(Path(args.output).resolve() not in (Path(args.baseline).resolve(), Path(args.candidate).resolve()),
                    "report cannot replace a verdict file")
            write_json(args.output, result)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except (Invalid, OSError, TypeError, KeyError) as error:
        parser.exit(2, f"error: {error}\n")


if __name__ == "__main__":
    main()
