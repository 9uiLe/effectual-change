"""Limited credential signatures and bounded local observation ingress."""

import os
from pathlib import Path
import sys
import tempfile
import time
import unittest


SCRIPTS = Path(__file__).resolve().parents[1] / "skills/moletta/scripts"
sys.path.insert(0, str(SCRIPTS))
import data_policy
import store
from model import DataError


class SelectedInputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()

    def test_regular_utf8_input_is_retained_without_anonymization(self):
        path = self.base / "selected.txt"
        raw = "Synthetic observation: 保存 completed.\n".encode()
        path.write_bytes(raw)
        self.assertEqual(data_policy.read_file(path), raw)

    def test_credential_filenames_are_rejected_without_echoing_names(self):
        for name in (".env", ".env.local", "id_rsa", "credentials.json", "client_secret_123.json",
                     "private.pem", "private.key", "identity.p12", "identity.pfx", ".netrc"):
            with self.subTest(name=name):
                path = self.base / name
                path.write_text("Synthetic fixture", encoding="utf-8")
                with self.assertRaises(DataError) as caught:
                    data_policy.read_file(path)
                self.assertIn("credential filenames", str(caught.exception))
                self.assertNotIn(str(path), str(caught.exception))
                self.assertNotIn(name, str(caught.exception))

    def test_known_signatures_have_generic_diagnostics(self):
        values = ("ghp_" + "A" * 40, "github_pat_" + "B" * 30, "sk-" + "C" * 30,
                  "AKIA" + "D" * 16, "Authorization: Bearer synthetic-bearer-value",
                  '"api_key": "synthetic-api-value"', "password=synthetic-password-value",
                  "-----BEGIN OPENSSH PRIVATE KEY-----\nSynthetic body\n")
        for value in values:
            with self.subTest(value=value):
                with self.assertRaises(DataError) as caught:
                    data_policy.check_text(value)
                self.assertIn("credential signature", str(caught.exception))
                self.assertNotIn(value, str(caught.exception))

    def test_json_unicode_escapes_do_not_bypass_ingress_or_echo_values(self):
        token = "ghp_" + "A" * 40
        raw = ('{"source":"\\u0067hp_' + 'A' * 40 + '"}').encode()
        with self.assertRaises(DataError) as caught:
            data_policy.decode_json(raw)
        self.assertNotIn(token, str(caught.exception))
        for raw in (b'{"a":1,"a":2}', b'{"value":NaN}', b'{"value":1e999}'):
            with self.subTest(raw=raw), self.assertRaises(DataError):
                data_policy.decode_json(raw)

    def test_input_size_is_capped_and_caller_can_choose_a_fixed_larger_cap(self):
        path = self.base / "selected.txt"
        path.write_bytes(b"x" * (data_policy.MAX_BYTES + 1))
        with self.assertRaisesRegex(DataError, "size"):
            data_policy.read_file(path)
        self.assertEqual(len(data_policy.read_file(path, max_bytes=2 * data_policy.MAX_BYTES)),
                         data_policy.MAX_BYTES + 1)
        for invalid in (0, -1, True, float("inf")):
            with self.subTest(invalid=invalid), self.assertRaises(DataError):
                data_policy.read_file(path, max_bytes=invalid)

    def test_symlink_missing_and_nonregular_inputs_have_safe_errors(self):
        outside = self.base / "outside-sensitive-name.txt"
        outside.write_text("Synthetic input", encoding="utf-8")
        link = self.base / "link.txt"
        link.symlink_to(outside)
        fifo = self.base / "pipe"
        os.mkfifo(fifo)
        for path in (link, self.base / "missing.txt", self.base, fifo):
            with self.subTest(path=path):
                with self.assertRaises(DataError) as caught:
                    data_policy.read_file(path)
                self.assertNotIn(str(path), str(caught.exception))
                self.assertNotIn(str(outside), str(caught.exception))

    def test_opaque_opt_in_does_not_bypass_secret_or_size_checks(self):
        opaque = b"\x89PNG\x00\xff\x01synthetic"
        with self.assertRaisesRegex(DataError, "opaque"):
            data_policy.validate_bytes(opaque)
        data_policy.validate_bytes(opaque, allow_opaque=True)
        with self.assertRaisesRegex(DataError, "credential signature"):
            data_policy.validate_bytes(opaque + b"ghp_" + b"Z" * 40, allow_opaque=True)
        with self.assertRaisesRegex(DataError, "size"):
            data_policy.validate_bytes(opaque, allow_opaque=True, max_bytes=2)

    def test_argv_preflight_checks_values_and_credential_paths_without_binary_blacklist(self):
        rejected = (("cat", "/tmp/.env.local"), ("tool", "--password", "synthetic-value"),
                    ("tool", "--api-key=synthetic-value"),
                    ("python", "-c", "open('/tmp/credentials.json').read()"))
        for argv in rejected:
            with self.subTest(argv=argv), self.assertRaises(DataError):
                data_policy.check_argv(list(argv))
        data_policy.check_argv(["curl", "https://example.invalid/public-fixture"])
        data_policy.check_argv(["python", "-c", "print('ordinary synthetic output')"])


class ObservationIngressTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.brief = self.base / "request.md"
        self.brief.write_text("Complete the synthetic task.", encoding="utf-8")
        self.run = self.base / "run"
        store.initialize(self.run, self.brief, "Complete the synthetic task")
        intent = store.read_json(self.run / "intent.json")
        intent["outcomes"][0]["acceptance"] = "Synthetic expected state is observed"
        store.write_json(self.run / "intent.json", intent)
        store.seal(self.run)
        plan = store.read_json(self.run / "plan.json")
        plan.update(target_environment="Synthetic environment", requirements=[{
            "id": "R1", "origin": "explicit", "source_quote": "Complete the synthetic task",
            "outcome_ids": ["O1"], "constraint_ids": [], "criterion": "Synthetic state changes"}],
            options=[{"id": "P1", "architecture": "Synthetic test controller", "contribution": "Changes synthetic state",
                      "tradeoffs": "Synthetic evidence only", "subject": {"identity": "Synthetic fixture", "revision": "v1", "files": []},
                      "coverage": [{"requirement_id": "R1", "mechanism": "Synthetic operation", "status": "unknown", "evidence_ids": []}]}],
            experiments=[{"id": "V1", "option_id": "P1", "outcome_ids": ["O1"], "requirement_ids": ["R1"],
                          "question": "Does the synthetic operation change state?", "scope": "end_to_end",
                          "environment": "Synthetic environment", "pass_criterion": "Expected synthetic state", "fail_criterion": "Unexpected synthetic state",
                          "retained_conditions": "Complete synthetic task", "omitted_conditions": "No production behavior",
                          "negative_control": "Omitting the operation leaves state unchanged"}])
        store.write_json(self.run / "plan.json", plan)

    def program(self, text):
        path = self.base / "fixture.py"
        path.write_text(text, encoding="utf-8")
        return [sys.executable, str(path)]

    def captured_bytes(self):
        return b"\n".join(path.read_bytes() for path in self.run.rglob("*") if path.is_file())

    def native(self):
        ident = store.begin(self.run, "V1")["observation_id"]
        transcript = self.base / "transcript.txt"
        transcript.write_text("Synthetic native tool observed expected state.\n", encoding="utf-8")
        return ident, transcript

    def test_brief_or_goal_rejection_precedes_run_creation(self):
        self.brief.write_text("password=synthetic-private-value", encoding="utf-8")
        rejected = self.base / "rejected"
        with self.assertRaises(DataError):
            store.initialize(rejected, self.brief, "Synthetic goal")
        self.assertFalse(rejected.exists())
        self.brief.write_text("Synthetic request", encoding="utf-8")
        with self.assertRaises(DataError):
            store.initialize(rejected, self.brief, "Authorization: Bearer synthetic-private-value")
        self.assertFalse(rejected.exists())

    def test_native_transcript_method_and_text_attachment_are_checked_before_publish(self):
        ident, transcript = self.native()
        transcript.write_text("password=synthetic-private-value", encoding="utf-8")
        with self.assertRaises(DataError):
            store.record(self.run, ident, transcript, "Synthetic tool")
        transcript.write_text("Synthetic native observation", encoding="utf-8")
        with self.assertRaises(DataError):
            store.record(self.run, ident, transcript, "api_key=synthetic-private-value")
        attachment = self.base / "attachment.txt"
        attachment.write_text("Authorization: Bearer synthetic-private-value", encoding="utf-8")
        with self.assertRaises(DataError):
            store.record(self.run, ident, transcript, "Synthetic tool", (attachment,))
        self.assertIsNone(store.load(self.run).run.observations[0].completed)
        self.assertEqual(list((self.run / "artifacts").iterdir()), [])
        self.assertNotIn(b"synthetic-private-value", self.captured_bytes())

    def test_assessment_reason_cannot_persist_a_known_secret_or_oversized_text(self):
        ident, transcript = self.native()
        store.record(self.run, ident, transcript, "Synthetic tool")
        for reason in ("Authorization: Bearer synthetic-private-value", "x" * (data_policy.MAX_BYTES + 1)):
            with self.subTest(oversized=len(reason) > data_policy.MAX_BYTES), self.assertRaises(DataError):
                store.assess(self.run, ident, "pass", reason)
        self.assertIsNone(store.load(self.run).run.observations[0].assessment)
        self.assertNotIn(b"synthetic-private-value", self.captured_bytes())

    def test_binary_attachment_requires_explicit_opt_in_and_is_preserved_exactly(self):
        ident, transcript = self.native()
        attachment = self.base / "screen.png"
        raw = b"\x89PNG\r\n\x00\xffsynthetic-screen"
        attachment.write_bytes(raw)
        with self.assertRaises(DataError):
            store.record(self.run, ident, transcript, "Synthetic tool", (attachment,))
        result = store.record(self.run, ident, transcript, "Synthetic tool", (attachment,), allow_opaque_artifacts=True)
        self.assertEqual(result["provenance"], "attested_native")
        self.assertEqual((self.run / result["artifacts"][1]["path"]).read_bytes(), raw)

    def test_secret_in_opted_in_binary_attachment_still_rejected(self):
        ident, transcript = self.native()
        attachment = self.base / "screen.png"
        attachment.write_bytes(b"\x89PNG\x00ghp_" + b"Z" * 40)
        with self.assertRaises(DataError):
            store.record(self.run, ident, transcript, "Synthetic tool", (attachment,), allow_opaque_artifacts=True)
        self.assertIsNone(store.load(self.run).run.observations[0].completed)

    def test_capture_preflight_rejects_before_observation_or_execution(self):
        marker = self.base / "executed"
        argv = self.program(f"from pathlib import Path\nPath({str(marker)!r}).touch()\n")
        argv.append("api_key=synthetic-private-value")
        with self.assertRaises(DataError):
            store.capture(self.run, "V1", argv, 2)
        self.assertFalse(marker.exists())
        self.assertEqual(store.load(self.run).run.observations, ())
        self.assertNotIn(b"synthetic-private-value", self.captured_bytes())

    def test_secret_output_is_withheld_but_completion_is_retained_and_cannot_pass(self):
        argv = self.program("print('ghp_' + 'Z' * 40)\n")
        result = store.capture(self.run, "V1", argv, 2)
        self.assertEqual(result["command_status"], "output_blocked")
        self.assertEqual(result["execution_status"], "completed")
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(len(result["artifacts"]), 1)
        self.assertNotIn(b"ghp_" + b"Z" * 40, self.captured_bytes())
        observation = store.load(self.run).run.observations[0]
        self.assertEqual(observation.completed.command.status, "output_blocked")
        self.assertIsNone(observation.assessment)
        with self.assertRaises(DataError):
            store.assess(self.run, result["observation_id"], "pass", "An exit code is not evidence")
        store.assess(self.run, result["observation_id"], "inconclusive", "Output was withheld")

    def test_opaque_output_is_withheld_without_publishing_raw_bytes(self):
        argv = self.program("import os\nos.write(1, b'\\x00\\xffsynthetic-opaque-output')\n")
        result = store.capture(self.run, "V1", argv, 2)
        self.assertEqual(result["command_status"], "output_blocked")
        self.assertNotIn(b"synthetic-opaque-output", self.captured_bytes())

    def test_large_stdout_and_stderr_are_drained_and_withheld(self):
        argv = self.program("import os\nfor stream in (1, 2):\n for _ in range(64):\n  os.write(stream, b'x' * 65536)\n")
        result = store.capture(self.run, "V1", argv, 3)
        self.assertEqual(result["command_status"], "output_blocked")
        self.assertEqual(result["execution_status"], "completed")
        self.assertEqual(len(result["output_issues"]), 2)
        self.assertLess(len(self.captured_bytes()), 100_000)
        self.assertEqual([Path(item["path"]).name for item in result["artifacts"]], ["output-blocked.txt"])

    def test_large_output_and_timeout_both_remain_visible_without_raw_output(self):
        argv = self.program("import os,time\nfor _ in range(32): os.write(1, b'x' * 65536)\ntime.sleep(10)\n")
        result = store.capture(self.run, "V1", argv, 0.2)
        self.assertEqual(result["command_status"], "output_blocked")
        self.assertEqual(result["execution_status"], "timeout")
        diagnostic = (self.run / result["artifacts"][0]["path"]).read_text()
        self.assertIn("Execution status: timeout", diagnostic)
        self.assertLess(len(self.captured_bytes()), 100_000)

    def test_timeout_covers_descendants_holding_pipes_after_parent_exits(self):
        argv = self.program("import subprocess,sys\nsubprocess.Popen([sys.executable, '-c', 'import time; time.sleep(10)'])\nprint('Synthetic parent exit')\n")
        before = time.monotonic()
        result = store.capture(self.run, "V1", argv, 0.1)
        self.assertLess(time.monotonic() - before, 2)
        self.assertEqual(result["command_status"], "timeout")
        with self.assertRaises(DataError):
            store.assess(self.run, result["observation_id"], "pass", "Parent exit cannot prove completion")


if __name__ == "__main__":
    unittest.main()
