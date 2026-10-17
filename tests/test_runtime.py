"""Behavioral contracts at the local run, observation and public CLI boundaries."""

import copy
import fcntl
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


SCRIPTS = Path(__file__).resolve().parents[1] / "skills/moletta/scripts"
sys.path.insert(0, str(SCRIPTS))
import moletta
import store
from model import DataError, canonical, digest


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        brief = self.base / "request.md"
        brief.write_text("Without a person: reach the screen, operate it, and check its result.", encoding="utf-8")
        self.run = self.base / "run"
        store.initialize(self.run, brief, "Complete the screen task without a person")
        intent = store.read_json(self.run / "intent.json")
        intent["outcomes"][0]["acceptance"] = "The complete task changes the expected state without manual operation"
        intent["constraints"] = [{"id": "C1", "text": "Without a person"}]
        store.write_json(self.run / "intent.json", intent)
        store.seal(self.run)
        self.subject = self.base / "controller.py"
        self.subject.write_text("print('synthetic expected state')\n", encoding="utf-8")
        self.plan = {
            "schema_version": 1, "target_environment": "synthetic device",
            "requirements": [{"id": f"R{i}", "origin": "explicit", "source_quote": quote,
                              "outcome_ids": ["O1"], "constraint_ids": ["C1"], "criterion": quote}
                             for i, quote in enumerate(("reach the screen", "operate it", "check its result"), 1)],
            "options": [{"id": "P1", "architecture": "One controller coordinates the complete synthetic task",
                         "contribution": "Completes the full path without manual handoff", "tradeoffs": "Synthetic environment only",
                         "subject": {"identity": "Synthetic task controller", "revision": "fixture-v1", "files": [str(self.subject)]},
                         "coverage": [{"requirement_id": f"R{i}", "mechanism": "Synthetic controller action",
                                       "status": "unknown", "evidence_ids": []} for i in range(1, 4)]}],
            "notes": [{"id": "S1", "kind": "source", "claim": "Synthetic fixture specification only",
                       "locator": "https://example.invalid/spec", "sha256": None, "outcome_ids": ["O1"],
                       "requirement_ids": ["R1", "R2", "R3"], "option_ids": ["P1"]}],
            "research": [{"question": "Could another allocation work?", "source_ids": ["S1"],
                          "finding": "Fixture has one currently viable configuration", "applicability": "Synthetic data only"}],
            "experiments": [{"id": "V1", "option_id": "P1", "outcome_ids": ["O1"], "requirement_ids": ["R1", "R2", "R3"],
                             "question": "Does the complete task change state?", "scope": "end_to_end", "environment": "synthetic device",
                             "pass_criterion": "Observe expected changed state", "fail_criterion": "Any step or state mismatch",
                             "retained_conditions": "The complete synthetic path", "omitted_conditions": "No actual phone tested",
                             "negative_control": "Omitting the operation must not satisfy the state check"}],
            "review": {"mode": "self_review", "raw_brief_read": True, "findings": []},
            "decision": {"status": "provisional", "option_id": "P1", "rationale": "Test whole-task feasibility",
                         "conditions": ["Complete path must pass"], "reconsider_when": "Whole outcome fails"},
            "next_action": {"kind": "experiment", "question": "Can this complete the task?", "rationale": "Missing operation changes the whole design",
                            "timebox_minutes": 5, "stop_condition": "One complete path and one negative control observed", "experiment_id": "V1"},
        }
        self.save()

    def save(self):
        store.write_json(self.run / "plan.json", self.plan)

    def check(self, stage="plan"):
        self.save()
        return moletta.report(self.run, stage)

    def codes(self, stage="plan"):
        return {item["code"] for item in self.check(stage)["findings"] if item["severity"] == "error"}

    def capture(self, result="pass", experiment="V1", resolves=()):
        self.save()
        value = store.capture(self.run, experiment, [sys.executable, str(self.subject)], 3)
        ident = value["observation_id"]
        store.assess(self.run, ident, result, "Synthetic observations assessed against the planned criterion", tuple(resolves))
        return ident

    def select(self, evidence_id="S1"):
        for row in self.plan["options"][0]["coverage"]:
            row.update(status="supported", evidence_ids=[evidence_id])
        self.plan["decision"].update(status="selected", conditions=[])
        self.save()

    def cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPTS / "moletta.py"), *map(str, args)],
                              capture_output=True, text=True)

    def test_missing_operation_and_untraced_hard_constraint_are_structural_errors(self):
        self.plan["options"][0]["coverage"][1]["mechanism"] = ""
        for requirement in self.plan["requirements"]:
            requirement["constraint_ids"] = []
        self.assertTrue({"MISSING_MECHANISM", "CONSTRAINT_GAP"}.issubset(self.codes()))

    def test_missing_capability_and_invalid_link_are_detected(self):
        self.plan["options"][0]["coverage"].pop(1)
        self.plan["experiments"][0]["requirement_ids"].append("R404")
        self.assertTrue({"CAPABILITY_GAP", "BROKEN_LINK"}.issubset(self.codes()))

    def test_conditional_unknowns_can_be_decided_but_do_not_establish_completion(self):
        self.assertEqual(self.codes("decide"), set())
        self.assertIn("UNVERIFIED_CAPABILITY", self.codes("verify"))
        self.plan["decision"].update(status="selected", conditions=[])
        self.assertIn("UNCONDITIONAL_UNKNOWN", self.codes("decide"))

    def test_known_violation_cannot_be_averaged_away(self):
        self.plan["options"][0]["coverage"][1]["status"] = "violated"
        self.assertIn("MANDATORY_VIOLATION", self.codes("decide"))

    def test_inference_does_not_establish_supported_or_measured_behavior(self):
        self.plan["notes"][0].update(kind="inference", locator=None)
        self.plan["research"] = []
        self.select()
        self.assertIn("UNSUPPORTED_COVERAGE", self.codes("verify"))
        self.assertIn("UNVERIFIED_CAPABILITY", self.codes("verify"))

    def test_supported_sources_must_apply_to_the_option_and_capability(self):
        self.select()
        self.plan["notes"][0]["requirement_ids"] = ["R1"]
        self.assertIn("UNRELATED_EVIDENCE", self.codes())

    def test_local_sources_are_hashed_and_confined_to_artifacts(self):
        path = self.run / "artifacts/spec.txt"
        path.write_text("Synthetic API", encoding="utf-8")
        self.plan["notes"][0].update(locator="artifacts/spec.txt", sha256=digest(path.read_bytes()))
        self.assertEqual(self.codes(), set())
        path.write_text("Changed API", encoding="utf-8")
        self.assertIn("SOURCE_INTEGRITY", self.codes())
        self.plan["notes"][0].update(locator="../controller.py", sha256=digest(self.subject.read_bytes()))
        self.assertIn("SOURCE_INTEGRITY", self.codes())

    def test_original_intent_and_brief_are_immutable_after_seal(self):
        intent = store.read_json(self.run / "intent.json")
        intent["outcomes"][0]["statement"] = "Only arrive"
        store.write_json(self.run / "intent.json", intent)
        self.assertIn("INTENT_CHANGED", self.codes())
        with self.assertRaises(DataError):
            store.seal(self.run)
        (self.run / "brief.md").write_text("Only arrive", encoding="utf-8")
        self.assertIn("BRIEF_CHANGED", self.codes())

    def test_existing_run_is_not_overwritten_and_seal_is_idempotent(self):
        with self.assertRaises(FileExistsError):
            store.initialize(self.run, self.run / "brief.md", "Other goal")
        self.assertFalse(store.seal(self.run)["changed"])

    def test_actual_command_capture_can_be_structurally_ready_but_never_semantic_proof(self):
        ident = self.capture()
        self.select(ident)
        result = self.check("verify")
        self.assertTrue(result["structural_readiness"], result)
        self.assertTrue(result["semantic_review_required"])
        self.assertEqual(store.load(self.run).run.observations[0].completed.provenance, "direct_command")

    def test_unit_or_other_environment_results_do_not_prove_the_target_outcome(self):
        for field, value, expected in (("scope", "unit", "NO_WHOLE_OUTCOME_EVIDENCE"),
                                       ("environment", "other simulator", "UNVERIFIED_CAPABILITY")):
            with self.subTest(field=field):
                for row in self.plan["options"][0]["coverage"]:
                    row.update(status="unknown", evidence_ids=[])
                self.plan["experiments"][0][field] = value
                ident = self.capture()
                self.select(ident)
                self.assertIn(expected, self.codes("verify"))
                self.plan["experiments"][0][field] = "end_to_end" if field == "scope" else "synthetic device"

    def test_arrival_only_end_to_end_plus_disjoint_unit_passes_does_not_prove_whole_task(self):
        self.plan["experiments"][0]["requirement_ids"] = ["R1"]
        operation_unit = copy.deepcopy(self.plan["experiments"][0])
        operation_unit.update(id="V2", scope="unit", requirement_ids=["R2", "R3"])
        self.plan["experiments"].append(operation_unit)
        self.capture()
        self.capture(experiment="V2")
        self.select()
        self.assertNotIn("UNVERIFIED_CAPABILITY", self.codes("verify"))
        self.assertIn("NO_WHOLE_OUTCOME_EVIDENCE", self.codes("verify"))

    def test_relabeling_experiment_scope_or_requirement_cannot_reuse_observation(self):
        ident = self.capture()
        self.select(ident)
        self.plan["experiments"][0]["scope"] = "unit"
        self.plan["requirements"][1]["criterion"] = "A stronger operation criterion"
        result = self.check("verify")
        self.assertFalse(result["structural_readiness"])
        self.assertIn("UNUSABLE_SUPPORT", self.codes("verify"))

    def test_changing_architecture_or_subject_revision_invalidates_old_success(self):
        ident = self.capture()
        self.select(ident)
        self.plan["options"][0]["architecture"] = "Another controller"
        self.plan["options"][0]["subject"]["revision"] = "fixture-v2"
        self.assertIn("UNVERIFIED_CAPABILITY", self.codes("verify"))

    def test_changing_actual_declared_input_without_editing_plan_invalidates_success(self):
        ident = self.capture()
        self.select(ident)
        self.subject.write_text("print('different behavior')", encoding="utf-8")
        self.assertIn("UNVERIFIED_CAPABILITY", self.codes("verify"))
        self.assertIn("SUBJECT_CHANGED", {item["code"] for item in self.check("verify")["findings"]})

    def test_failure_cannot_be_removed_by_plan_edits_or_overwritten_as_success(self):
        failed = self.capture("fail")
        self.select()
        self.capture("pass")
        self.assertIn("NEGATIVE_EVIDENCE", self.codes("verify"))
        self.plan["next_action"] = None
        self.save()
        self.assertEqual(len(store.load(self.run).run.observations), 2)
        with self.assertRaises(DataError):
            store.assess(self.run, failed, "pass", "Relabel it")

    def test_later_distinct_passing_observation_can_explicitly_resolve_failure(self):
        failed = self.capture("fail")
        fixed = self.capture("pass", resolves=(failed,))
        self.select(fixed)
        self.assertEqual(self.codes("verify"), set())

    def test_next_and_verification_agree_when_resolving_observation_inputs_change(self):
        failed = self.capture("fail")
        self.capture("pass", resolves=(failed,))
        self.select()
        self.subject.write_text("print('changed subject')", encoding="utf-8")
        self.assertIn("NEGATIVE_EVIDENCE", self.codes("verify"))
        self.assertEqual(moletta.next_action(self.run)["focus"]["observation_id"], failed)

    def test_different_scope_cannot_resolve_prior_failure(self):
        failed = self.capture("fail")
        self.plan["experiments"][0]["scope"] = "unit"
        self.save()
        value = store.capture(self.run, "V1", [sys.executable, str(self.subject)], 3)
        with self.assertRaises(DataError):
            store.assess(self.run, value["observation_id"], "pass", "Wrong scope", (failed,))

    def test_duplicate_or_self_resolution_is_refused_without_publishing_assessment(self):
        failed = self.capture("fail")
        value = store.capture(self.run, "V1", [sys.executable, str(self.subject)], 3)
        for resolves in ((failed, failed), (value["observation_id"],)):
            with self.subTest(resolves=resolves), self.assertRaises(DataError):
                store.assess(self.run, value["observation_id"], "pass", "Invalid resolution", resolves)
        self.assertIsNone(store.load(self.run).run.observations[-1].assessment)

    def test_failure_on_an_unselected_option_does_not_block_selected_success(self):
        passed = self.capture()
        self.select(passed)
        alternative = copy.deepcopy(self.plan["options"][0])
        alternative["id"] = "P2"
        for row in alternative["coverage"]:
            row.update(status="unknown", evidence_ids=[])
        self.plan["options"].append(alternative)
        experiment = copy.deepcopy(self.plan["experiments"][0])
        experiment.update(id="V2", option_id="P2")
        self.plan["experiments"].append(experiment)
        self.capture("fail", experiment="V2")
        self.assertEqual(self.codes("verify"), set())
        self.plan["next_action"] = None
        self.save()
        self.assertEqual(moletta.next_action(self.run)["action"], "semantic_outcome_review")

    def test_editing_subject_cannot_hide_an_unfinished_selected_observation(self):
        started = store.begin(self.run, "V1")["observation_id"]
        self.plan["options"][0]["subject"]["revision"] = "fixture-v2"
        passed = self.capture()
        self.select(passed)
        self.assertIn("UNASSESSED_OBSERVATION", self.codes("verify"))
        self.assertEqual(moletta.next_action(self.run)["focus"]["observation_id"], started)

    def test_unassessed_capture_and_exit_zero_never_imply_success(self):
        value = store.capture(self.run, "V1", [sys.executable, "-c", "print('nothing verified')"], 3)
        self.assertEqual(value["exit_code"], 0)
        self.assertEqual(value["verdict"], "unassessed")
        self.select()
        self.assertIn("UNASSESSED_OBSERVATION", self.codes("verify"))
        self.assertEqual(moletta.next_action(self.run)["action"], "resolve_observation")

    def test_timeout_and_launch_error_are_retained_and_cannot_pass(self):
        cases = (([sys.executable, "-c", "import time; time.sleep(3)"], 0.03, "timeout"),
                 ([str(self.base / "missing-command")], 3, "launch_error"))
        for argv, timeout, status in cases:
            value = store.capture(self.run, "V1", argv, timeout)
            self.assertEqual(value["command_status"], status)
            with self.assertRaises(DataError):
                store.assess(self.run, value["observation_id"], "pass", "Cannot be success")
            store.assess(self.run, value["observation_id"], "inconclusive", "Execution incomplete")
        self.assertEqual(len(store.load(self.run).run.observations), 2)

    def test_native_observation_shares_binding_and_assessment_rules(self):
        started = self.cli("begin", self.run, "--experiment", "V1")
        self.assertEqual(started.returncode, 0, started.stderr)
        ident = json.loads(started.stdout)["observation_id"]
        transcript = self.base / "tool-output.txt"
        transcript.write_text("Synthetic native tool: reached screen; clicked save; observed changed state.", encoding="utf-8")
        screenshot = self.base / "screen.bin"
        screenshot.write_bytes(b"synthetic binary attachment")
        completed = self.cli("record", self.run, "--observation", ident, "--transcript", transcript,
                             "--method", "Synthetic GUI tool transcript", "--artifact", screenshot)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)["provenance"], "attested_native")
        store.assess(self.run, ident, "pass", "Synthetic full task state observed")
        self.select(ident)
        result = self.check("verify")
        self.assertTrue(result["structural_readiness"], result)
        self.assertIn("ATTESTED_PROVENANCE", {item["code"] for item in result["findings"]})

    def test_native_record_requires_a_start_and_cannot_complete_twice(self):
        transcript = self.base / "tool-output.txt"
        transcript.write_text("Synthetic observation", encoding="utf-8")
        with self.assertRaises(DataError):
            store.record(self.run, "unknown", transcript, "Actual tool")
        ident = store.begin(self.run, "V1")["observation_id"]
        store.record(self.run, ident, transcript, "Synthetic tool")
        with self.assertRaises(DataError):
            store.record(self.run, ident, transcript, "Replacement transcript")

    def test_interrupted_completion_can_retry_import_without_repeating_the_operation(self):
        ident = store.begin(self.run, "V1")["observation_id"]
        transcript = self.base / "tool-output.txt"
        transcript.write_text("Already executed synthetic operation: changed state", encoding="utf-8")
        with mock.patch.object(store, "_append", side_effect=OSError("Interrupted journal write")):
            with self.assertRaises(OSError):
                store.record(self.run, ident, transcript, "Synthetic native tool")
        self.assertIsNone(store.load(self.run).run.observations[0].completed)
        self.assertEqual(list((self.run / "artifacts" / ident).iterdir()), [])
        store.record(self.run, ident, transcript, "Retry importing the same actual output")
        observation = store.load(self.run).run.observations[0]
        self.assertIsNotNone(observation.completed)
        self.assertEqual(len(list((self.run / "artifacts" / ident).iterdir())), 1)
        store.assess(self.run, ident, "pass", "Existing actual output meets the criterion")
        self.select(ident)
        self.assertEqual(self.codes("verify"), set())

    def test_partial_completion_file_write_removes_only_unpublished_output(self):
        previous = self.capture()
        previous_artifacts = store.load(self.run).run.observations[0].completed.artifacts
        ident = store.begin(self.run, "V1")["observation_id"]
        transcript = self.base / "tool-output.txt"
        transcript.write_text("Synthetic operation output", encoding="utf-8")
        attachment = self.base / "attachment.txt"
        attachment.write_text("Synthetic attachment", encoding="utf-8")
        write = store._write_private

        def interrupted_write(path, raw):
            if path.name.startswith("attachment-"):
                raise OSError("Interrupted attachment write")
            write(path, raw)

        with mock.patch.object(store, "_write_private", side_effect=interrupted_write):
            with self.assertRaises(OSError):
                store.record(self.run, ident, transcript, "Synthetic tool", (attachment,))
        loaded = store.load(self.run)
        self.assertEqual(loaded.run.observations[0].started.id, previous)
        self.assertEqual(loaded.run.observations[0].completed.artifacts, previous_artifacts)
        self.assertIsNone(loaded.run.observations[1].completed)
        self.assertEqual(list((self.run / "artifacts" / ident).iterdir()), [])
        self.assertFalse(loaded.findings)

    def test_published_completion_output_survives_an_error_after_journal_commit(self):
        ident = store.begin(self.run, "V1")["observation_id"]
        transcript = self.base / "tool-output.txt"
        transcript.write_text("Synthetic already committed output", encoding="utf-8")
        append = store._append

        def publish_then_interrupt(*args):
            append(*args)
            raise OSError("Interrupted after publication")

        with mock.patch.object(store, "_append", side_effect=publish_then_interrupt):
            with self.assertRaises(OSError):
                store.record(self.run, ident, transcript, "Synthetic tool")
        loaded = store.load(self.run)
        self.assertIsNotNone(loaded.run.observations[0].completed)
        self.assertFalse(loaded.findings)
        artifact = loaded.run.observations[0].completed.artifacts[0]
        self.assertEqual((self.run / artifact.path).read_bytes(), transcript.read_bytes())
        with self.assertRaisesRegex(DataError, "already completed"):
            store.record(self.run, ident, transcript, "Do not duplicate committed output")

    def test_native_observation_cannot_be_retroactively_bound_to_changed_design(self):
        ident = store.begin(self.run, "V1")["observation_id"]
        self.plan["options"][0]["coverage"][1]["mechanism"] = "New operation mechanism"
        self.save()
        transcript = self.base / "tool-output.txt"
        transcript.write_text("Synthetic actual output", encoding="utf-8")
        store.record(self.run, ident, transcript, "Synthetic tool")
        store.assess(self.run, ident, "pass", "Observed old design")
        self.select()
        self.assertIn("UNVERIFIED_CAPABILITY", self.codes("verify"))

    def test_deleted_or_changed_captured_artifact_cannot_support_success(self):
        ident = self.capture()
        self.select(ident)
        artifact = store.load(self.run).run.observations[0].completed.artifacts[0]
        path = self.run / artifact.path
        path.write_bytes(b"changed observations")
        self.assertIn("ARTIFACT_INTEGRITY", self.codes("verify"))
        path.unlink()
        self.assertIn("ARTIFACT_INTEGRITY", self.codes("verify"))

    def test_checkpoint_detects_rewriting_or_truncating_checksummed_history(self):
        self.capture()
        snapshot = store.checkpoint(self.run, self.check())
        self.assertTrue((self.run / snapshot["checkpoint"]).is_file())
        journal = store.read_json(self.run / "journal.json")
        journal["events"] = []
        journal["sha256"] = digest(canonical({key: journal[key] for key in ("schema_version", "run_id", "brief_sha256", "events")}))
        store.write_json(self.run / "journal.json", journal)
        self.assertIn("HISTORY_CHANGED", self.codes())

    def test_malformed_data_and_unknown_fields_have_diagnostics_not_tracebacks(self):
        self.plan["experiments"][0]["option_id"] = []
        self.assertIn("INVALID_RUN", self.codes())
        self.plan["experiments"][0]["option_id"] = "P1"
        self.plan["decision"]["unexpected_field"] = "unexpected value"
        self.save()
        done = self.cli("check", self.run)
        self.assertEqual(done.returncode, 1)
        self.assertNotIn("Traceback", done.stdout + done.stderr)
        self.assertIn("unknown fields", done.stdout)

    def test_duplicate_json_fields_and_non_finite_constants_are_rejected(self):
        for text in ('{"schema_version":1,"schema_version":1}', '{"timebox_minutes":NaN}'):
            with self.subTest(text=text):
                (self.run / "plan.json").write_text(text, encoding="utf-8")
                done = self.cli("check", self.run)
                self.assertEqual(done.returncode, 1)
                self.assertNotIn("Traceback", done.stdout + done.stderr)
                self.assertIn("INVALID_RUN", done.stdout)

    def test_malformed_journal_event_kind_is_a_diagnostic_not_a_traceback(self):
        journal = store.read_json(self.run / "journal.json")
        journal["events"] = [{"kind": [], "value": {}}]
        journal["sha256"] = digest(canonical({key: journal[key] for key in ("schema_version", "run_id", "brief_sha256", "events")}))
        store.write_json(self.run / "journal.json", journal)
        done = self.cli("check", self.run)
        self.assertEqual(done.returncode, 1)
        self.assertNotIn("Traceback", done.stdout + done.stderr)
        self.assertIn("event kind must be a string", done.stdout)

    def test_material_raw_brief_review_concerns_block_adoption(self):
        self.plan["review"]["raw_brief_read"] = False
        self.plan["review"]["findings"] = [{"id": "F1", "severity": "material", "issue": "Operation may need a person",
                                              "disposition": "deferred", "reason": "Needs investigation"}]
        self.assertTrue({"RAW_BRIEF_REVIEW_REQUIRED", "UNRESOLVED_FINDING"}.issubset(self.codes("decide")))

    def test_next_exposes_negative_observations_and_requires_a_bounded_action(self):
        self.assertEqual(moletta.next_action(self.run)["action"], "execute_bounded_action")
        self.capture("fail")
        self.assertEqual(moletta.next_action(self.run)["focus"]["code"], "NEGATIVE_EVIDENCE")
        self.plan["next_action"]["timebox_minutes"] = 0
        self.assertIn("UNBOUNDED_ACTION", self.codes())

    def test_next_without_an_action_never_automatically_spends_unbounded_work(self):
        self.plan["next_action"] = None
        self.save()
        self.assertEqual(moletta.next_action(self.run)["action"], "choose_bounded_action")

    def test_long_finite_experiment_budgets_are_valid_but_unbounded_capture_is_refused(self):
        self.plan["next_action"]["timebox_minutes"] = 72 * 60
        self.assertEqual(self.codes(), set())
        value = store.capture(self.run, "V1", [sys.executable, "-c", "print('observed')"], 72 * 3600)
        self.assertEqual(value["command_status"], "completed")
        count = len(store.load(self.run).run.observations)
        for timeout in (0, -1, float("nan"), float("inf")):
            with self.subTest(timeout=timeout), self.assertRaises(DataError):
                store.capture(self.run, "V1", [sys.executable, "-c", "print('never run')"], timeout)
        self.assertEqual(len(store.load(self.run).run.observations), count)

    def test_public_cli_passes_literal_arguments_without_shell_interpretation(self):
        done = self.cli("capture", self.run, "--experiment", "V1", "--cwd", self.base,
                        "--", sys.executable, "-c", "import sys; print(sys.argv[1])", "$(never_execute); value")
        self.assertEqual(done.returncode, 0, done.stderr)
        capture = store.load(self.run).run.observations[0].completed
        stdout = self.run / capture.artifacts[0].path
        self.assertEqual(stdout.read_text().strip(), "$(never_execute); value")
        self.assertEqual(capture.command.cwd, str(self.base.resolve()))

    def test_capture_requires_predeclared_criteria_and_a_valid_sealed_plan(self):
        self.plan["experiments"][0]["negative_control"] = ""
        self.save()
        done = self.cli("capture", self.run, "--experiment", "V1", "--", sys.executable, "-c", "print(1)")
        self.assertEqual(done.returncode, 2)
        self.assertEqual(store.load(self.run).run.observations, ())

    def test_run_mutations_refuse_an_active_writer_lock(self):
        with (self.run / ".write.lock").open("a+b") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(DataError):
                store.begin(self.run, "V1")

    def test_killed_writer_releases_lock_without_manual_file_removal(self):
        script = ("import fcntl,sys,time; stream=open(sys.argv[1],'a+b'); "
                  "fcntl.flock(stream.fileno(),fcntl.LOCK_EX); print('locked',flush=True); time.sleep(60)")
        process = subprocess.Popen([sys.executable, "-c", script, str(self.run / ".write.lock")],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertEqual(process.stdout.readline().strip(), "locked")
            with self.assertRaises(DataError):
                store.begin(self.run, "V1")
            process.kill()
            process.communicate(timeout=3)
            self.assertEqual(store.begin(self.run, "V1")["status"], "started")
            self.assertTrue((self.run / ".write.lock").is_file())
        finally:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=3)


if __name__ == "__main__":
    unittest.main()
