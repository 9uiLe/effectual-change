#!/usr/bin/env python3
"""Summarize observed Codex exec JSONL without trusting the agent's final claims.

By default this prints only counts, event positions and SHA-256 fingerprints.
Use --show-text only for a PRIVATE local review: commands and final messages
may contain repository content, absolute paths, or credentials.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Iterable

# An aid for finding verification commands, not a general shell parser.
# A matching command might still be a dry run, a quote, or a grep invocation.
VERIFICATION_HINT = re.compile(
    r"(?i)(?:\bpytest\b|\bunittest\b|\bshellcheck\b|"
    r"\bcargo\s+test\b|\bgo\s+test\b|\b(?:npm|pnpm)\s+(?:run\s+)?test\b|"
    r"\bgit\s+diff\s+--check\b|(?:^|[\s/])test_[^\s]*\.sh\b)"
)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def read_events(path: Path) -> list[dict]:
    """Fail closed for malformed JSONL, without printing the offending line."""
    events = []
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, 1):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at line {line_number}") from exc
            if not isinstance(event, dict):
                raise ValueError(f"Expected an event object at line {line_number}")
            events.append(event)
    return events


def audit(events: Iterable[dict], show_text: bool = False) -> dict:
    commands: dict[str, dict] = {}
    last_message = None
    completed_turns = 0
    failed_turns = 0
    total_events = 0

    for index, event in enumerate(events, 1):
        total_events += 1
        kind = event.get("type")
        if kind == "turn.completed":
            completed_turns += 1
        if kind in ("turn.failed", "error"):
            failed_turns += 1
        if kind not in ("item.started", "item.completed"):
            continue

        item = event.get("item")
        if not isinstance(item, dict):
            continue
        if kind == "item.completed" and item.get("type") == "agent_message":
            message = item.get("text")
            if isinstance(message, str):
                last_message = {"event_index": index, "sha256": digest(message)}
                if show_text:
                    last_message["text"] = message
        if item.get("type") != "command_execution":
            continue

        item_id = item.get("id")
        key = item_id if isinstance(item_id, str) and item_id else f"no-id-event-{index}"
        record = commands.setdefault(key, {
            "first_event": index, "last_event": index, "command": "",
            "started": False, "completed": False, "exit_code": None,
        })
        record["last_event"] = index
        command = item.get("command")
        if isinstance(command, str):
            record["command"] = command
        if kind == "item.started":
            record["started"] = True
        else:
            record["completed"] = True
            exit_code = item.get("exit_code")
            if isinstance(exit_code, int) and not isinstance(exit_code, bool):
                record["exit_code"] = exit_code

    summaries = []
    counts = {"succeeded": 0, "failed": 0, "unknown": 0, "incomplete": 0}
    verification_counts = dict.fromkeys(counts, 0)
    for item_id, record in sorted(commands.items(), key=lambda pair: pair[1]["first_event"]):
        if not record["completed"]:
            outcome = "incomplete"
        elif record["exit_code"] is None:
            outcome = "unknown"
        elif record["exit_code"] == 0:
            outcome = "succeeded"
        else:
            outcome = "failed"
        counts[outcome] += 1
        is_verification = bool(VERIFICATION_HINT.search(record["command"]))
        if is_verification:
            verification_counts[outcome] += 1
        entry = {
            "item_id": item_id,
            "first_event": record["first_event"],
            "last_event": record["last_event"],
            "command_sha256": digest(record["command"]),
            "exit_code": record["exit_code"],
            "outcome": outcome,
            "verification_hint": is_verification,
        }
        if show_text:
            entry["command"] = record["command"]
        summaries.append(entry)

    return {
        "events": total_events,
        "completed_turns": completed_turns,
        "failed_turn_or_error_events": failed_turns,
        "commands": summaries,
        "command_outcomes": counts,
        "verification_hints": verification_counts,
        "last_agent_message": last_message,
        "limitations": (
            "Exit code 0 shows that a command completed, not that a claimed test "
            "or behavior was correctly verified. Verification hints are heuristic; "
            "compare agent claims with the private event log and independent tests. "
            "Missing events or tests in other tools are not inferred."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", type=Path, required=True,
                        help="Path to a locally retained codex exec --json log")
    parser.add_argument("--show-text", action="store_true",
                        help="Include raw commands and final agent message; keep output private")
    parser.add_argument("--output", type=Path,
                        help="Write report to a local file instead of stdout")
    args = parser.parse_args()
    try:
        report = audit(read_events(args.events), show_text=args.show_text)
        output = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            args.output.write_text(output, encoding="utf-8")
        else:
            sys.stdout.write(output)
        return 0
    except (OSError, ValueError) as exc:
        print(f"Unable to audit event log: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
