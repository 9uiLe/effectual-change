"""Offline tests for trace evidence extraction. No agent, network, or secrets needed."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "audit.py"
SPEC = importlib.util.spec_from_file_location("codex_trace_audit", SCRIPT)
audit_tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit_tool)


def command_event(kind, command, item_id="item_1", exit_code=None):
    item = {
        "type": "command_execution", "id": item_id, "command": command,
    }
    if exit_code is not None:
        item["exit_code"] = exit_code
    return {"type": kind, "item": item}


class TraceEvidenceTests(unittest.TestCase):
    def test_completed_test_command_and_final_message_remain_distinct(self):
        events = [
            {"type": "thread.started", "thread_id": "not-a-credential"},
            {"type": "turn.started"},
            command_event("item.started", "python3 -m unittest discover -s tests"),
            command_event("item.completed", "python3 -m unittest discover -s tests",
                          exit_code=0),
            {"type": "item.completed", "item": {
                "type": "agent_message", "text": "All 30 tests passed"}},
            {"type": "turn.completed", "usage": {"input_tokens": 1}},
        ]
        report = audit_tool.audit(events)
        self.assertEqual(report["completed_turns"], 1)
        self.assertEqual(report["command_outcomes"]["succeeded"], 1)
        self.assertEqual(report["verification_hints"]["succeeded"], 1)
        self.assertEqual(report["commands"][0]["first_event"], 3)
        self.assertEqual(report["commands"][0]["last_event"], 4)
        self.assertIsNotNone(report["last_agent_message"]["sha256"])
        self.assertNotIn("text", report["last_agent_message"])
        self.assertNotIn("python3 -m unittest", json.dumps(report))
        self.assertNotIn("All 30 tests passed", json.dumps(report))

    def test_a_claim_without_a_completed_command_is_not_success(self):
        message = {"type": "item.completed", "item": {
            "type": "agent_message", "text": "The 16 tests all passed."
        }}
        started = command_event("item.started", "pytest -q")
        report = audit_tool.audit([started, message])
        self.assertEqual(report["completed_turns"], 0)
        self.assertEqual(report["command_outcomes"]["succeeded"], 0)
        self.assertEqual(report["verification_hints"]["incomplete"], 1)

    def test_unknown_exit_code_is_not_success(self):
        report = audit_tool.audit([
            command_event("item.completed", "pytest -q"),
        ])
        self.assertEqual(report["command_outcomes"]["unknown"], 1)
        self.assertEqual(report["verification_hints"]["succeeded"], 0)

    def test_failed_verification_and_nonverification_are_separate(self):
        report = audit_tool.audit([
            command_event("item.completed", "python3 -m unittest", "a", exit_code=1),
            command_event("item.completed", "ls docs", "b", exit_code=0),
            {"type": "item.completed", "item": {"type": "mcp_tool_call", "id": "c",
                                               "command": "pytest -q"}},
            {"type": "turn.failed", "error": {"message": "failure"}},
        ])
        self.assertEqual(report["command_outcomes"]["failed"], 1)
        self.assertEqual(report["command_outcomes"]["succeeded"], 1)
        self.assertEqual(report["verification_hints"]["failed"], 1)
        self.assertEqual(report["verification_hints"]["succeeded"], 0)
        self.assertEqual(report["failed_turn_or_error_events"], 1)

    def test_show_text_is_explicit_only(self):
        sensitive = "echo private-path-or-token-is-never-posted"
        e = [
            command_event("item.completed", sensitive, exit_code=0),
            {"type": "item.completed", "item": {"type": "agent_message",
                                               "text": sensitive}},
        ]
        default_report = audit_tool.audit(e)
        self.assertNotIn(sensitive, json.dumps(default_report))
        private_report = audit_tool.audit(e, show_text=True)
        self.assertEqual(private_report["commands"][0]["command"], sensitive)
        self.assertEqual(private_report["last_agent_message"]["text"], sensitive)

    def test_malformed_jsonl_fails_without_echoing_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.jsonl"
            path.write_text('{"type":"thread.started"}\n{"secret":"private",\n',
                            encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "line 2") as raised:
                audit_tool.read_events(path)
            self.assertNotIn("private", str(raised.exception))

    def test_cli_writes_sanitized_report(self):
        events = [
            command_event("item.completed", "git diff --check", exit_code=0),
            {"type": "turn.completed"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            event_file = Path(tmp) / "events.jsonl"
            report_file = Path(tmp) / "audit.json"
            event_file.write_text(
                "".join(json.dumps(event) + "\n" for event in events),
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--events", str(event_file),
                 "--output", str(report_file)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(report_file.read_text(encoding="utf-8"))
            self.assertEqual(report["verification_hints"]["succeeded"], 1)
            self.assertEqual(report["completed_turns"], 1)
            self.assertNotIn("git diff --check", report_file.read_text())


if __name__ == "__main__":
    unittest.main()
