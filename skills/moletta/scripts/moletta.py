#!/usr/bin/env python3
"""Keep design intent, bounded next actions and actual observations reviewable."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import policy
import store
from model import DataError, encode


def report(root: Path, stage: str = "plan") -> dict:
    try:
        loaded = store.load(root)
        return policy.evaluate(loaded.run, stage, loaded.findings, loaded.unusable_observations)
    except (OSError, UnicodeError, ValueError) as exc:
        return {"stage": stage, "structural_readiness": False, "semantic_review_required": True,
                "findings": [{"code": "INVALID_RUN", "path": str(root), "message": str(exc), "severity": "error"}]}


def next_action(root: Path) -> dict:
    result = report(root)
    errors = [item for item in result["findings"] if item["severity"] == "error"]
    if errors:
        return {"action": "repair_record", "focus": errors[0], "check": result}
    loaded = store.load(root)
    pending = policy.pending_observations(loaded.run, policy.observation_index(loaded.run, loaded.unusable_observations),
                                          selected_only=loaded.run.plan.decision.option_id is not None)
    if pending:
        return {"action": "resolve_observation", "focus": pending[0],
                "note": "An execution is not a verified result. Choose one bounded action to assess or resolve this observation."}
    action = loaded.run.plan.next_action
    if action is not None:
        return {"action": "execute_bounded_action", "next_action": encode(action),
                "note": "Respect the timebox and stop condition; judge information by its effect on the whole outcome."}
    verification = report(root, "verify")
    if verification["structural_readiness"]:
        return {"action": "semantic_outcome_review", "check": verification,
                "note": "Check the actual outcome and remaining limits. Structural readiness is not semantic proof."}
    return {"action": "choose_bounded_action", "required_fields": ["kind", "question", "rationale", "timebox_minutes", "stop_condition", "experiment_id"],
            "conditions": list(loaded.run.plan.decision.conditions), "check": verification,
            "note": "Choose the smallest next action that can change the whole-system decision; declare it in plan.json."}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="Create a new local run from the original request")
    init.add_argument("run", type=Path)
    init.add_argument("--brief", required=True, type=Path)
    init.add_argument("--goal", required=True)
    for name in ("seal", "next", "checkpoint"):
        command = sub.add_parser(name)
        command.add_argument("run", type=Path)
    check = sub.add_parser("check", help="Check structural readiness, never semantic truth")
    check.add_argument("run", type=Path)
    check.add_argument("--stage", choices=("plan", "decide", "verify"), default="plan")
    begin = sub.add_parser("begin", help="Bind a native-tool observation before execution")
    begin.add_argument("run", type=Path)
    begin.add_argument("--experiment", required=True)
    record = sub.add_parser("record", help="Import actual native-tool output as an attestation")
    record.add_argument("run", type=Path)
    record.add_argument("--observation", required=True)
    record.add_argument("--transcript", required=True, type=Path)
    record.add_argument("--method", required=True)
    record.add_argument("--artifact", action="append", default=[], type=Path)
    capture = sub.add_parser("capture", help="Capture literal argv; exit zero does not imply passing behavior")
    capture.add_argument("run", type=Path)
    capture.add_argument("--experiment", required=True)
    capture.add_argument("--timeout", type=float, default=30)
    capture.add_argument("--cwd", type=Path)
    assess = sub.add_parser("assess", help="Assess one observation against its predeclared criteria once")
    assess.add_argument("run", type=Path)
    assess.add_argument("--observation", required=True)
    assess.add_argument("--result", choices=("pass", "fail", "inconclusive"), required=True)
    assess.add_argument("--reason", required=True)
    assess.add_argument("--resolves", action="append", default=[])
    args, rest = parser.parse_known_args(argv)
    if args.command != "capture" and rest:
        parser.error("unrecognized arguments: " + " ".join(rest))
    root = args.run.resolve()
    try:
        if args.command == "init":
            value = store.initialize(root, args.brief, args.goal)
        elif args.command == "seal":
            value = store.seal(root)
        elif args.command == "check":
            value = report(root, args.stage)
        elif args.command == "next":
            value = next_action(root)
        elif args.command == "checkpoint":
            value = store.checkpoint(root, report(root))
        elif args.command == "begin":
            value = store.begin(root, args.experiment)
        elif args.command == "record":
            value = store.record(root, args.observation, args.transcript, args.method, tuple(args.artifact))
        elif args.command == "assess":
            value = store.assess(root, args.observation, args.result, args.reason, tuple(args.resolves))
        else:
            if not rest or rest[0] != "--":
                raise DataError("Separate the captured command with --")
            value = store.capture(root, args.experiment, rest[1:], args.timeout, args.cwd)
        print(json.dumps(value, ensure_ascii=False, indent=2))
        return 0 if args.command != "check" or value["structural_readiness"] else 1
    except (OSError, UnicodeError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
