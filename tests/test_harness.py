import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[1] / "skills/moletta/scripts"
sys.path.insert(0, str(SCRIPTS))
import harness
from checks import inspect_run, read_json, report
from checks import digest


class HarnessBehaviorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        brief = self.base / "request.md"
        brief.write_text("Without a person: reach the screen, operate it, and check its result.", encoding="utf-8")
        self.run = self.base / "run"
        harness.initialize(self.run, brief, "Complete the screen task without a person")
        intent = read_json(self.run / "intent.json")
        intent["outcomes"][0]["acceptance"] = "The complete task changes the expected state with no manual operation"
        intent["constraints"] = [{"id": "C1", "text": "Without a person"}]
        harness.write_json(self.run / "intent.json", intent)
        harness.seal(self.run)
        self.record = read_json(self.run / "record.json")
        self.record.update({
            "target_environment": "synthetic device environment",
            "requirements": [{"id": f"R{i}", "origin": "explicit", "source_quote": quote,
                              "outcome_ids": ["O1"], "constraint_ids": ["C1"], "criterion": quote}
                             for i, quote in enumerate(("reach the screen", "operate it", "check its result"), 1)],
            "options": [{"id": "P1", "mechanism": "One controller for the complete synthetic task",
                         "outcome_contribution": "Completes all steps without manual handoff", "tradeoffs": "Synthetic environment only",
                         "coverage": [{"requirement_id": f"R{i}", "mechanism": "Synthetic controller action",
                                       "status": "unknown", "evidence_ids": []} for i in range(1, 4)]}],
            "research": [{"question": "Can a different allocation work?", "sources": ["https://example.invalid/synthetic-spec"],
                          "finding": "One viable configuration in this synthetic fixture", "applicability": "Fixture facts only"}],
            "experiments": [{"id": "V1", "option_id": "P1", "outcome_ids": ["O1"], "requirement_ids": ["R1", "R2", "R3"],
                             "question": "Does the complete synthetic task run?", "scope": "end_to_end", "environment": "synthetic device environment",
                             "pass_criterion": "Observe the expected changed state", "fail_criterion": "Any step or state mismatch",
                             "retained_conditions": "Complete synthetic path", "omitted_conditions": "No actual phone tested",
                             "negative_control": "Omitting the operation must not satisfy the state check"}],
            "review": {"mode": "self_review", "raw_brief_read": True, "findings": []},
            "decision": {"status": "provisional", "option_id": "P1", "rationale": "Test the synthetic configuration",
                         "conditions": ["Complete path must pass"], "reconsider_when": "Whole outcome fails"},
        })
        self.save()

    def save(self):
        harness.write_json(self.run / "record.json", self.record)

    def codes(self, stage="plan"):
        self.save()
        return {x.code for x in inspect_run(self.run, stage) if x.severity == "error"}

    def measure(self, result="pass", ident="E1"):
        self.save()
        captured = harness.capture(self.run, "V1", [sys.executable, "-c", "print('synthetic expected state')"], 5)
        exp = self.record["experiments"][0]
        evidence = {"id": ident, "kind": "measurement", "claim": "Synthetic state observed; not a real phone test",
                    "experiment_id": "V1", "option_id": "P1", "outcome_ids": exp["outcome_ids"].copy(),
                    "requirement_ids": exp["requirement_ids"].copy(), "scope": exp["scope"],
                    "environment": exp["environment"], "locator": captured["locator"], "sha256": captured["sha256"], "result": result}
        self.record["evidence"].append(evidence)
        for row in self.record["options"][0]["coverage"]:
            row.update(status="supported", evidence_ids=[ident])
        self.record["decision"].update(status="selected", conditions=[])
        return evidence

    def test_missing_operation_is_detected_even_when_other_steps_have_mechanisms(self):
        self.record["options"][0]["coverage"][1]["mechanism"] = ""
        self.assertIn("MISSING_MECHANISM", self.codes())

    def test_missing_coverage_and_untraced_constraint_are_detected(self):
        self.record["options"][0]["coverage"].pop(1)
        for req in self.record["requirements"]:
            req["constraint_ids"] = []
        self.assertTrue({"CAPABILITY_GAP", "CONSTRAINT_GAP"}.issubset(self.codes()))

    def test_unknown_is_usable_for_a_conditional_decision_but_not_completion(self):
        self.assertEqual(self.codes("decide"), set())
        self.assertIn("UNVERIFIED_CAPABILITY", self.codes("verify"))

    def test_inference_does_not_count_as_a_supported_or_verified_capability(self):
        self.record["evidence"] = [{"id": "E0", "kind": "inference", "claim": "Probably works", "option_id": "P1",
                                    "outcome_ids": ["O1"], "requirement_ids": ["R1", "R2", "R3"]}]
        for row in self.record["options"][0]["coverage"]:
            row.update(status="supported", evidence_ids=["E0"])
        self.assertIn("INFERENCE_AS_PROOF", self.codes("verify"))

    def test_local_primary_sources_are_usable_without_inventing_a_web_url(self):
        path = self.run / "artifacts" / "local-spec.md"
        path.write_text("Synthetic controller implements the documented operations.", encoding="utf-8")
        self.record["evidence"] = [{"id": "S1", "kind": "source", "claim": "Local specification",
                                    "locator": "artifacts/local-spec.md", "sha256": digest(path.read_bytes()),
                                    "outcome_ids": ["O1"], "requirement_ids": ["R1", "R2", "R3"]}]
        self.record["research"][0]["sources"] = ["S1"]
        self.assertEqual(self.codes("decide"), set())
        path.write_text("Changed specification", encoding="utf-8")
        self.assertIn("SOURCE_CHANGED", self.codes("decide"))

    def test_real_capture_can_establish_structural_readiness_but_never_semantic_proof(self):
        self.measure()
        self.save()
        result = report(self.run, "verify")
        self.assertTrue(result["structural_readiness"], result)
        self.assertTrue(result["semantic_review_required"])

    def test_unit_results_do_not_prove_the_whole_outcome(self):
        self.record["experiments"][0]["scope"] = "unit"
        self.measure()
        self.assertIn("NO_WHOLE_OUTCOME_EVIDENCE", self.codes("verify"))

    def test_measurement_in_another_environment_does_not_prove_target_behavior(self):
        self.record["experiments"][0]["environment"] = "different simulator"
        self.measure()
        self.assertIn("UNVERIFIED_CAPABILITY", self.codes("verify"))

    def test_changing_experiment_after_capture_invalidates_its_application(self):
        self.measure()
        self.record["experiments"][0]["environment"] = "other environment"
        self.record["evidence"][0]["environment"] = "other environment"
        self.assertIn("CAPTURE_CONTEXT_CHANGED", self.codes("verify"))

    def test_changing_the_tested_option_or_capability_invalidates_the_capture(self):
        self.measure()
        self.record["options"][0]["mechanism"] = "Another controller"
        self.record["requirements"][1]["criterion"] = "A different observed operation"
        self.assertIn("CAPTURE_CONFIGURATION_CHANGED", self.codes("verify"))

    def test_failed_observation_cannot_support_unconditional_selection(self):
        self.measure("fail")
        self.assertIn("NEGATIVE_SUPPORT", self.codes("decide"))

    def test_same_observation_cannot_be_relabelled_as_new_success(self):
        failed = self.measure("fail")
        relabelled = copy.deepcopy(failed)
        relabelled.update(id="E2", result="pass")
        failed["superseded_by"] = "E2"
        self.record["evidence"].append(relabelled)
        for row in self.record["options"][0]["coverage"]:
            row["evidence_ids"] = ["E2"]
        self.assertIn("NEGATIVE_EVIDENCE", self.codes("verify"))

    def test_unselected_option_timeout_can_be_kept_without_blocking_success(self):
        self.measure()
        alternative = copy.deepcopy(self.record["options"][0])
        alternative["id"] = "P2"
        for row in alternative["coverage"]:
            row.update(status="unknown", evidence_ids=[])
        self.record["options"].append(alternative)
        exp = copy.deepcopy(self.record["experiments"][0])
        exp.update(id="V2", option_id="P2")
        self.record["experiments"].append(exp)
        self.save()
        captured = harness.capture(self.run, "V2", [sys.executable, "-c", "import time; time.sleep(5)"], 0.05)
        evidence = copy.deepcopy(self.record["evidence"][0])
        evidence.update(id="E2", option_id="P2", experiment_id="V2", result="inconclusive",
                        locator=captured["locator"], sha256=captured["sha256"])
        self.record["evidence"].append(evidence)
        self.assertEqual(self.codes("verify"), set())

    def test_capture_missing_observation_fields_is_not_accepted(self):
        evidence = self.measure()
        path = self.run / evidence["locator"]
        value = read_json(path)
        for key in ("command", "cwd", "started_at", "finished_at", "exit_code", "stdout", "stderr"):
            del value[key]
        harness.write_json(path, value)
        evidence["sha256"] = digest(path.read_bytes())
        self.assertIn("INVALID_CAPTURE", self.codes("verify"))

    def test_malformed_record_produces_a_diagnostic_instead_of_a_traceback(self):
        self.record["experiments"][0]["option_id"] = []
        self.assertIn("INVALID_RECORD", self.codes())

    def test_changing_goal_cannot_be_hidden_by_resealing(self):
        intent = read_json(self.run / "intent.json")
        intent["outcomes"][0]["statement"] = "Just reach the screen"
        harness.write_json(self.run / "intent.json", intent)
        self.assertIn("INTENT_CHANGED", self.codes())
        with self.assertRaises(ValueError):
            harness.seal(self.run)

    def test_original_request_cannot_be_silently_summarized(self):
        (self.run / "brief.md").write_text("reach the screen", encoding="utf-8")
        self.assertIn("BRIEF_CHANGED", self.codes())

    def test_altered_or_absent_execution_artifact_cannot_support_completion(self):
        evidence = self.measure()
        path = self.run / evidence["locator"]
        path.write_text("{}", encoding="utf-8")
        self.assertIn("EVIDENCE_CHANGED", self.codes("verify"))
        path.unlink()
        self.assertIn("MISSING_ARTIFACT", self.codes("verify"))

    def test_failure_must_be_resolved_explicitly_even_with_a_passing_run(self):
        failed = self.measure("fail", "E1")
        self.measure("pass", "E2")
        self.assertIn("NEGATIVE_EVIDENCE", self.codes("verify"))
        failed["superseded_by"] = "E2"
        self.assertEqual(self.codes("verify"), set())

    def test_known_violation_cannot_be_averaged_away_by_other_benefits(self):
        self.record["options"][0]["coverage"][1]["status"] = "violated"
        self.assertIn("MANDATORY_VIOLATION", self.codes("decide"))

    def test_unresolved_material_review_blocks_adoption(self):
        self.record["review"]["findings"] = [{"id": "F1", "severity": "material", "issue": "Whole outcome may fail",
                                              "disposition": "deferred", "reason": "Not yet investigated"}]
        self.assertIn("UNRESOLVED_FINDING", self.codes("decide"))

    def test_capture_exit_zero_never_assigns_a_passing_result(self):
        value = harness.capture(self.run, "V1", [sys.executable, "-c", "print('nothing verified')"], 5)
        self.assertEqual(value["exit_code"], 0)
        self.assertEqual(value["verdict"], "unassessed")
        self.assertEqual(read_json(self.run / "record.json")["evidence"], [])

    def test_capture_timeout_is_retained_and_cannot_be_passing_evidence(self):
        value = harness.capture(self.run, "V1", [sys.executable, "-c", "import time; time.sleep(5)"], 0.05)
        self.assertEqual(value["status"], "timeout")

    def test_next_points_to_an_experiment_without_hiding_unknowns(self):
        result = harness.next_action(self.run)
        self.assertEqual(result["action"], "choose_decision_changing_experiment")
        self.assertEqual(result["experiments"], ["V1"])

    def test_conditional_adoption_keeps_an_actionable_next_step(self):
        self.record["experiments"] = []
        self.save()
        result = harness.next_action(self.run)
        self.assertEqual(result["action"], "resolve_adoption_conditions")

    def test_cli_supports_command_separator_and_produces_a_reviewable_checkpoint(self):
        done = subprocess.run([sys.executable, str(SCRIPTS / "harness.py"), "capture", str(self.run),
                               "--experiment", "V1", "--", sys.executable, "-c", "print('observed')"],
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout)["verdict"], "unassessed")
        snapshot = harness.checkpoint(self.run)
        self.assertEqual(read_json(self.run / snapshot["snapshot"])["record"]["run_id"], self.record["run_id"])


if __name__ == "__main__":
    unittest.main()
