"""Filesystem/argument interface; no model calls, solvers or semantic grader."""

import argparse
import json
from pathlib import Path

from .corpus import DEFAULT_SUITE, load_suite, prepare
from .judgments import compare, template
from .validation import Invalid, write_new_json


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", type=Path, default=DEFAULT_SUITE,
                        help="evaluator-owned corpus directory (cases/, artifacts/, rubrics/)")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate", help="validate the corpus; no agent or grader runs")
    commands.add_parser("list", help="list all cases in the selected corpus")
    packet = commands.add_parser("prepare", help="package only public input into a new directory")
    packet.add_argument("case_id")
    packet.add_argument("--dest", type=Path)
    skeleton = commands.add_parser("template", help="write evaluator-only incomplete verdict structure")
    skeleton.add_argument("--arm", choices=("baseline", "candidate"), required=True)
    skeleton.add_argument("--output", type=Path, required=True)
    grading = commands.add_parser("grade", help="compare externally judged paired runs")
    grading.add_argument("--baseline", type=Path, required=True)
    grading.add_argument("--candidate", type=Path, required=True)
    grading.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            suite = load_suite(args.suite)
            result = {"structural_validation": "passed", "case_count": len(suite),
                      "holdout_count": sum(entry.case["split"] == "holdout" for entry in suite.values()),
                      "behavioral_runs_performed": 0}
        elif args.command == "list":
            result = [{"id": key, "title": entry.case["title"], "split": entry.case["split"]}
                      for key, entry in load_suite(args.suite).items()]
        elif args.command == "prepare":
            result = prepare(args.case_id, args.dest, args.suite)
        elif args.command == "template":
            write_new_json(args.output, template(args.arm, args.suite))
            result = {"template": str(args.output), "status": "incomplete; not a behavioral result"}
        else:
            result = compare(args.baseline, args.candidate, args.suite)
            write_new_json(args.output, result)
        print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
    except (Invalid, OSError) as error:
        parser.exit(2, f"error: {error}\n")
