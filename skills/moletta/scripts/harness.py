#!/usr/bin/env python3
"""Local run records and evidence capture for the agent's design loop."""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from checks import capture_context, digest, document_digest, inspect_intent, read_json, report


def write_json(path: Path, value: dict):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def now():
    return datetime.now(timezone.utc).isoformat()


def initialize(root: Path, brief_path: Path, goal: str) -> dict:
    brief = brief_path.read_bytes()
    brief.decode("utf-8")
    if not goal.strip():
        raise ValueError("Goal must be nonempty.")
    root.mkdir(parents=True, exist_ok=False)
    (root / "brief.md").write_bytes(brief)
    (root / "artifacts").mkdir()
    (root / "snapshots").mkdir()
    write_json(root / "intent.json", {"schema_version": 1,
               "outcomes": [{"id": "O1", "statement": goal, "acceptance": ""}], "constraints": []})
    write_json(root / "record.json", {"schema_version": 1, "run_id": uuid.uuid4().hex,
               "brief_sha256": digest(brief), "target_environment": "", "requirements": [],
               "options": [], "research": [], "experiments": [], "evidence": [],
               "review": {"mode": "pending", "raw_brief_read": False, "findings": []},
               "decision": {"status": "exploring", "option_id": None, "rationale": "",
                            "conditions": [], "reconsider_when": ""}})
    return {"run": str(root), "next": "Read brief.md; fill original outcomes, acceptance and constraints in intent.json; seal, then develop record.json."}


def seal(root: Path) -> dict:
    intent = read_json(root / "intent.json")
    errors = inspect_intent(intent)
    if errors:
        raise ValueError("Intent incomplete: " + "; ".join(x.message for x in errors))
    record = read_json(root / "record.json")
    if digest((root / "brief.md").read_bytes()) != record.get("brief_sha256"):
        raise ValueError("Original brief changed; create a new run for changed intent.")
    lock_path = root / "intent.lock.json"
    value = document_digest(intent)
    if lock_path.exists():
        if read_json(lock_path).get("sha256") != value:
            raise ValueError("Cannot reseal changed intent. Create a new run and record the authorized change.")
        return {"sealed": True, "changed": False, "sha256": value}
    with lock_path.open("x", encoding="utf-8") as stream:
        json.dump({"sha256": value, "sealed_at": now()}, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return {"sealed": True, "changed": True, "sha256": value}


def capture(root: Path, experiment_id: str, command: list[str], timeout: float,
            cwd: Path | None = None) -> dict:
    if not command:
        raise ValueError("Provide a command after --.")
    if not 0 < timeout <= 3600:
        raise ValueError("timeout must be greater than zero and at most 3600 seconds.")
    record = read_json(root / "record.json")
    experiment = next((x for x in record.get("experiments", [])
                       if isinstance(x, dict) and x.get("id") == experiment_id), None)
    if experiment is None:
        raise ValueError("Record the experiment and its criteria before capturing evidence.")
    for field in ("question", "pass_criterion", "fail_criterion", "environment"):
        if not isinstance(experiment.get(field), str) or not experiment[field].strip():
            raise ValueError(f"Experiment needs {field} before execution.")
    intent_sha256 = document_digest(read_json(root / "intent.json"))
    configuration = capture_context(record, experiment)
    artifacts = root / "artifacts"
    if artifacts.is_symlink():
        raise ValueError("artifacts/ must not be a symlink.")
    artifacts.mkdir(exist_ok=True)
    command_cwd = (cwd or Path.cwd()).resolve(strict=True)
    started = now()
    process = subprocess.Popen(command, cwd=command_cwd, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, start_new_session=(os.name == "posix"))
    status = "completed"
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        status = "timeout"
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
        stdout, stderr = process.communicate()
    value = {"type": "command_capture", "run_id": record["run_id"],
             "experiment_id": experiment_id, "experiment": experiment,
             "configuration": configuration,
             "intent_sha256": intent_sha256, "command": command, "cwd": str(command_cwd),
             "started_at": started, "finished_at": now(), "status": status,
             "exit_code": process.returncode, "stdout": stdout.decode("utf-8", errors="replace"),
             "stderr": stderr.decode("utf-8", errors="replace"),
             "assessment": "unassessed: compare observations with the experiment criteria"}
    path = artifacts / f"capture-{uuid.uuid4().hex}.json"
    write_json(path, value)
    return {"locator": str(path.relative_to(root)), "sha256": digest(path.read_bytes()),
            "status": status, "exit_code": process.returncode, "verdict": "unassessed"}


def checkpoint(root: Path) -> dict:
    record = read_json(root / "record.json")
    intent = read_json(root / "intent.json")
    snapshots = root / "snapshots"
    if snapshots.is_symlink():
        raise ValueError("snapshots/ must not be a symlink.")
    snapshots.mkdir(exist_ok=True)
    path = snapshots / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:8]}.json"
    write_json(path, {"at": now(), "intent": intent, "record": record,
                      "plan_check": report(root, "plan")})
    return {"snapshot": str(path.relative_to(root)), "record_sha256": document_digest(record)}


def next_action(root: Path) -> dict:
    result = report(root, "plan")
    try:
        record = read_json(root / "record.json")
    except (OSError, ValueError):
        return {"action": "repair_record", "check": result}
    errors = [x for x in result["findings"] if x["severity"] == "error"]
    if errors:
        first = errors[0]
        code = first["code"]
        action = "resolve_gap"
        if code in ("INTENT_CHANGED", "BRIEF_CHANGED", "INTENT_UNSEALED"):
            action = "align_intent"
        elif code in ("NO_OPTIONS", "MISSING_MECHANISM", "CAPABILITY_GAP", "UNKNOWN_CAPABILITY"):
            action = "explore_mechanism_or_reframe_whole_option"
        return {"action": action, "focus": first, "check": result}
    observed = {x.get("experiment_id") for x in record.get("evidence", [])
                if isinstance(x, dict) and x.get("kind") == "measurement"}
    pending = [x.get("id") for x in record.get("experiments", []) if x.get("id") not in observed]
    if pending:
        return {"action": "choose_decision_changing_experiment", "experiments": pending,
                "note": "Choose by whole-outcome impact and cost; run only within the authorized scope and budget."}
    if record.get("decision", {}).get("status") == "provisional":
        return {"action": "resolve_adoption_conditions", "conditions": record["decision"].get("conditions", []),
                "note": "Gather the smallest evidence that changes the whole-system choice; a provisional choice is not verified completion."}
    stage = "verify" if record.get("decision", {}).get("status") in ("selected", "verified") else "decide"
    result = report(root, stage)
    return {"action": "semantic_outcome_review" if result["structural_readiness"] else "gather_decision_changing_evidence",
            "check": result, "note": "Prefer the smallest action that changes the whole-system decision; do not optimize a part in isolation."}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="Create a run without changing an existing directory")
    init.add_argument("run", type=Path)
    init.add_argument("--brief", required=True, type=Path)
    init.add_argument("--goal", required=True)
    for name in ("seal", "next", "checkpoint"):
        child = sub.add_parser(name)
        child.add_argument("run", type=Path)
    check = sub.add_parser("check", help="Check recorded relationships and evidence, not semantic truth")
    check.add_argument("run", type=Path)
    check.add_argument("--stage", choices=("plan", "decide", "verify"), default="plan")
    command = sub.add_parser("capture", help="Capture a command; exit zero is not a passing verdict")
    command.add_argument("run", type=Path)
    command.add_argument("--experiment", required=True)
    command.add_argument("--timeout", type=float, default=30)
    command.add_argument("--cwd", type=Path, help="command directory; defaults to the caller's working directory")
    args, rest = parser.parse_known_args(argv)
    if args.command != "capture" and rest:
        parser.error("unrecognized arguments: " + " ".join(rest))
    try:
        if args.command == "init":
            value = initialize(args.run, args.brief, args.goal)
        elif args.command == "seal":
            value = seal(args.run)
        elif args.command == "capture":
            if not rest or rest[0] != "--":
                raise ValueError("Separate the captured command with --.")
            value = capture(args.run, args.experiment, rest[1:], args.timeout, args.cwd)
        elif args.command == "checkpoint":
            value = checkpoint(args.run)
        elif args.command == "next":
            value = next_action(args.run)
        else:
            value = report(args.run, args.stage)
        print(json.dumps(value, ensure_ascii=False, indent=2))
        return 0 if args.command != "check" or value["structural_readiness"] else 1
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
