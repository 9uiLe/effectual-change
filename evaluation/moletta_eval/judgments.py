"""Validate retained observations and compare external judgments, never answer prose."""

from datetime import datetime
from pathlib import Path

from .corpus import DEFAULT_SUITE, Suite, load_suite, public_packet
from .validation import (Invalid, JsonObject, digest, nonempty, number, object_value, objects_by_id,
                         read_json, relative_file, require, sha, strings)

RATINGS = {"missed": 0, "partial": 0.5, "met": 1}
CONTROL_FIELDS = ("model", "effort", "tools", "environment_id", "budget", "control_prompt_sha256")
METRICS = ("wall_seconds", "solver_turns", "input_tokens", "output_tokens")
EXPOSURE_FLAGS = ("not_used_for_candidate_tuning", "solver_first_exposure_in_this_run")


def template(arm: str, root: Path = DEFAULT_SUITE) -> JsonObject:
    require(arm in ("baseline", "candidate"), "arm must be baseline or candidate")
    rows = []
    for case_id, entry in load_suite(root).items():
        _, manifest = public_packet(entry, root)
        row = {"id": case_id, "packet_sha256": manifest["packet_sha256"],
               "rubric_sha256": entry.rubric_sha256, "artifacts": [], "complete_transcript": False,
               "metrics": {**dict.fromkeys(METRICS), "cost_usd": None},
               "criteria": [{"id": item["id"], "rating": None, "evidence": []}
                            for item in entry.rubric["criteria"]],
               "critical_failures": [{"id": item["id"], "occurred": None, "evidence": []}
                                     for item in entry.rubric["critical_failures"]],
               "process_assessment": {"unnecessary_process": None, "evidence": []}}
        if entry.case["split"] == "holdout":
            row["holdout_exposure"] = dict.fromkeys(EXPOSURE_FLAGS, False)
        rows.append(row)
    return {"schema_version": 1, "arm": arm, "evaluation_id": "",
            "configuration": {"label": "", "skill_revision": "", "model": "", "effort": "", "tools": [],
                              "environment_id": "", "control_prompt_sha256": "",
                              "budget": {"max_tokens": None, "max_seconds": None, "max_turns": None}},
            "judge": {"id": "", "independent_of_solver": False, "judged_at": ""}, "cases": rows}


def _evidence(rows: object, paths: set[str], label: str) -> None:
    require(isinstance(rows, list) and bool(rows), f"{label} needs observational evidence")
    for row in rows:
        row = object_value(row, f"{label} evidence")
        artifact = nonempty(row.get("artifact"), f"{label}.artifact")
        require(artifact in paths, f"{label} evidence must refer to a registered artifact")
        nonempty(row.get("location"), f"{label}.location")
        nonempty(row.get("observation"), f"{label}.observation")


def _artifacts(case: JsonObject, bundle: Path, case_id: str) -> set[str]:
    artifacts = case.get("artifacts")
    require(isinstance(artifacts, list) and bool(artifacts), f"{case_id} needs retained raw artifacts")
    paths: set[str] = set()
    roles: set[str] = set()
    for artifact in artifacts:
        artifact = object_value(artifact, "retained artifact")
        name = nonempty(artifact.get("path"), "artifact.path")
        require(name not in paths, "duplicate retained artifact")
        expected = sha(artifact.get("sha256"), "artifact.sha256")
        target = relative_file(bundle, name, "retained artifact")
        require(digest(target.read_bytes()) == expected, f"changed run artifact: {name}")
        require(artifact.get("role") in ("transcript", "result", "usage"), "invalid retained artifact role")
        paths.add(name)
        roles.add(artifact["role"])
    require({"transcript", "usage"} <= roles, "retain the full solver transcript and raw usage record")
    require(case.get("complete_transcript") is True, "declare complete_transcript only for a retained full trace")
    return paths


def _configuration(run: JsonObject) -> JsonObject:
    config = object_value(run.get("configuration"), "configuration")
    for field in ("label", "skill_revision", "model", "effort", "environment_id"):
        nonempty(config.get(field), f"configuration.{field}")
    sha(config.get("control_prompt_sha256"), "control_prompt_sha256")
    strings(config.get("tools"), "configuration.tools")
    budget = object_value(config.get("budget"), "configuration.budget")
    for field in ("max_tokens", "max_seconds", "max_turns"):
        number(budget.get(field), f"budget.{field}", integer=field != "max_seconds", positive=True)
    judge = object_value(run.get("judge"), "judge")
    nonempty(judge.get("id"), "judge.id")
    require(judge.get("independent_of_solver") is True, "judge must declare independence from solver")
    timestamp = nonempty(judge.get("judged_at"), "judge.judged_at")
    try:
        judged_at = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        require(judged_at.tzinfo is not None, "judged_at requires a timezone")
    except ValueError as error:
        raise Invalid("judged_at must be an ISO-8601 datetime with timezone") from error
    return config


def validate_run(path: Path, expected_arm: str, suite: Suite,
                 root: Path = DEFAULT_SUITE) -> tuple[JsonObject, dict[str, JsonObject]]:
    path = path.resolve()
    run = read_json(path)
    require(type(run.get("schema_version")) is int and run["schema_version"] == 1
            and run.get("arm") == expected_arm, f"invalid {expected_arm} run")
    nonempty(run.get("evaluation_id"), "evaluation_id")
    config = _configuration(run)
    summaries: dict[str, JsonObject] = {}
    for case_id, case in objects_by_id(run.get("cases"), "run.cases").items():
        require(case_id in suite, f"unknown scored case: {case_id}")
        entry = suite[case_id]
        _, manifest = public_packet(entry, root)
        require(case.get("packet_sha256") == manifest["packet_sha256"], f"public packet changed: {case_id}")
        require(case.get("rubric_sha256") == entry.rubric_sha256, f"rubric changed: {case_id}")
        paths = _artifacts(case, path.parent, case_id)
        criteria = objects_by_id(case.get("criteria"), "scored criteria")
        expected = objects_by_id(entry.rubric["criteria"], "rubric criteria")
        require(criteria.keys() == expected.keys(), f"criteria set mismatch: {case_id}")
        weighted = 0.0
        for criterion_id, score in criteria.items():
            rating = nonempty(score.get("rating"), f"{criterion_id}.rating")
            require(rating in RATINGS, f"invalid rating: {criterion_id}")
            _evidence(score.get("evidence"), paths, criterion_id)
            weighted += RATINGS[rating] * expected[criterion_id]["weight"]
        failures = objects_by_id(case.get("critical_failures"), "scored critical failures")
        require(failures.keys() == objects_by_id(entry.rubric["critical_failures"], "rubric failures").keys(),
                f"critical failure set mismatch: {case_id}")
        occurred = []
        for failure_id, failure in failures.items():
            require(type(failure.get("occurred")) is bool, "critical failure verdict must be boolean")
            _evidence(failure.get("evidence"), paths, failure_id)
            if failure["occurred"]:
                occurred.append(failure_id)
        process = object_value(case.get("process_assessment"), "process_assessment")
        require(type(process.get("unnecessary_process")) is bool, "process assessment must be boolean")
        _evidence(process.get("evidence"), paths, "process assessment")
        metrics = object_value(case.get("metrics"), "metrics")
        for field in METRICS:
            number(metrics.get(field), f"metrics.{field}", integer=field != "wall_seconds")
        require("cost_usd" in metrics, "cost_usd must be explicit; use null if unavailable")
        if metrics["cost_usd"] is not None:
            number(metrics["cost_usd"], "metrics.cost_usd")
        budget = config["budget"]
        over_budget = (metrics["wall_seconds"] > budget["max_seconds"] or
                       metrics["solver_turns"] > budget["max_turns"] or
                       metrics["input_tokens"] + metrics["output_tokens"] > budget["max_tokens"])
        exposure = None
        if entry.case["split"] == "holdout":
            exposure = object_value(case.get("holdout_exposure"), "holdout_exposure")
            for flag in EXPOSURE_FLAGS:
                require(type(exposure.get(flag)) is bool, f"holdout_exposure.{flag} must be boolean")
        summaries[case_id] = {"score": round(weighted / sum(c["weight"] for c in expected.values()) * 100, 6),
                              "critical_failures": occurred, "unnecessary_process": process["unnecessary_process"],
                              "metrics": metrics, "over_budget": over_budget, "split": entry.case["split"],
                              "holdout_exposure": exposure}
    return run, summaries


def _total_metrics(summaries: dict[str, JsonObject]) -> JsonObject:
    rows = [case["metrics"] for case in summaries.values()]
    totals = {key: sum(row[key] for row in rows) for key in METRICS}
    known = [row["cost_usd"] for row in rows if row["cost_usd"] is not None]
    totals.update(cost_usd=sum(known) if len(known) == len(rows) else None,
                  known_cost_subtotal_usd=sum(known) if known else None,
                  cases_with_unknown_cost=len(rows) - len(known))
    for key, value in totals.items():
        if value is not None:
            number(value, f"aggregate.{key}")
    return totals


def compare(baseline_path: Path, candidate_path: Path, root: Path = DEFAULT_SUITE) -> JsonObject:
    suite = load_suite(root)
    baseline, before = validate_run(baseline_path, "baseline", suite, root)
    candidate, after = validate_run(candidate_path, "candidate", suite, root)
    require(baseline["evaluation_id"] == candidate["evaluation_id"], "evaluation ids must match")
    require(before.keys() == after.keys(), "baseline and candidate must contain exactly the same cases")
    controls = []
    for field in CONTROL_FIELDS:
        b, c = baseline["configuration"][field], candidate["configuration"][field]
        if field == "tools":
            b, c = sorted(b), sorted(c)
        if b != c:
            controls.append(field)
    reasons = []
    if controls:
        reasons.append("Baseline/candidate control conditions differ: " + ", ".join(controls))
    missing = sorted(set(suite) - set(before))
    if missing:
        reasons.append("Full frozen suite was not evaluated: " + ", ".join(missing))
    if not any(entry.case["split"] == "holdout" for entry in suite.values()):
        reasons.append("The suite contains no fresh private holdout")
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
        if c["split"] == "holdout" and not all(b["holdout_exposure"][flag] and c["holdout_exposure"][flag]
                                                 for flag in EXPOSURE_FLAGS):
            reasons.append(f"Holdout exposure declarations do not support a fresh test: {case_id}")
    baseline_mean = sum(case["score"] for case in before.values()) / len(before)
    candidate_mean = sum(case["score"] for case in after.values()) / len(after)
    if candidate_mean <= baseline_mean:
        reasons.append("No aggregate behavioral improvement was judged")
    return {"schema_version": 1, "evaluation_id": baseline["evaluation_id"],
            "report_kind": "comparison_of_external_behavioral_judgments",
            "limitations": ["Ratings and evidence prose are external judgments, not programmatically established semantic truth.",
                            "Judge independence, transcript completeness, usage accuracy and holdout exposure are operator declarations.",
                            "This tool checks packaging, schema, integrity, pairing and arithmetic; it runs no agent or behavioral grader.",
                            "The packet builder is not a sandbox. A small suite is not statistical proof of general improvement."],
            "comparable_controls": not controls, "control_differences": controls,
            "judges": {"baseline": baseline["judge"], "candidate": candidate["judge"]},
            "configurations": {"baseline": baseline["configuration"], "candidate": candidate["configuration"]},
            "pairs": pairs,
            "aggregate": {"baseline_mean_score": round(baseline_mean, 6), "candidate_mean_score": round(candidate_mean, 6),
                          "score_delta": round(candidate_mean - baseline_mean, 6),
                          "baseline_process_false_positives": sum(case["unnecessary_process"] for case in before.values()),
                          "candidate_process_false_positives": sum(case["unnecessary_process"] for case in after.values()),
                          "baseline_metrics": _total_metrics(before), "candidate_metrics": _total_metrics(after)},
            "promotion": {"status": "blocked" if reasons else "eligible_for_review", "automatic_promotion": False,
                          "reasons": reasons}}
