"""Structural evaluator tests; fixture verdicts are not behavioral measurements."""

import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import evaluate


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "suite"
        for name in ("cases", "rubrics", "artifacts"):
            shutil.copytree(evaluate.ROOT / name, self.root / name)

    def make_run(self, arm, rating="met", include_holdout=True):
        run = evaluate.template(arm, include_holdout, self.root)
        run["evaluation_id"] = "structural-fixture-only"
        run["configuration"].update({"label": arm, "skill_revision": arm + "-fixture",
                                     "model": "fixture-model", "effort": "fixture-effort", "tools": ["fixture-read"],
                                     "environment_id": "fixture-environment", "control_prompt_sha256": "a" * 64,
                                     "budget": {"max_tokens": 1000, "max_seconds": 100, "max_turns": 10}})
        run["judge"] = {"id": "fixture-judge", "independent_of_solver": True,
                        "judged_at": "2026-10-17T10:00:00+00:00"}
        transcript = self.base / f"{arm}-transcript.txt"
        transcript.write_text("Synthetic structure fixture, not an agent run or semantic assessment.\n")
        evidence = [{"artifact": transcript.name, "location": "line 1",
                     "observation": "Arbitrary fixture observation used only to test the JSON contract."}]
        for row in run["cases"]:
            row["artifacts"] = [{"path": transcript.name, "sha256": evaluate.digest(transcript.read_bytes()),
                                 "role": "transcript"}]
            row["metrics"] = {"wall_seconds": 2, "solver_turns": 1, "input_tokens": 20,
                              "output_tokens": 10, "cost_usd": None}
            for item in row["criteria"]:
                item.update(rating=rating, evidence=copy.deepcopy(evidence))
            for item in row["critical_failures"]:
                item.update(occurred=False, evidence=copy.deepcopy(evidence))
            row["process_assessment"] = {"unnecessary_process": False, "evidence": copy.deepcopy(evidence)}
        return run

    def save_run(self, arm, run):
        path = self.base / f"{arm}.json"
        evaluate.write_json(path, run)
        return path

    def comparison(self, baseline=None, candidate=None):
        return evaluate.compare(self.save_run("baseline", baseline or self.make_run("baseline", "missed")),
                                self.save_run("candidate", candidate or self.make_run("candidate")), self.root)

    def test_corpus_has_regressions_and_distinct_holdout(self):
        suite = evaluate.load_suite(self.root)
        self.assertEqual(6, len(suite))
        self.assertEqual(1, sum(row["case"]["split"] == "holdout" for row in suite.values()))

    def test_packet_copies_only_allowlisted_public_fields_and_files(self):
        case_id = "arrival-action-verification"
        source = self.root / "cases" / f"{case_id}.json"
        data = evaluate.read_json(source)
        data["private_expected_answer"] = "this must never enter a solver packet"
        evaluate.write_json(source, data)
        destination = self.base / "packet"
        result = evaluate.prepare(case_id, destination, self.root)
        public = evaluate.read_json(destination / "case.json")
        self.assertNotIn("private_expected_answer", public)
        self.assertNotIn("split", public)
        self.assertFalse((destination / "rubrics").exists())
        manifest = evaluate.read_json(destination / "packet-manifest.json")
        self.assertEqual(result["packet_sha256"], manifest.pop("packet_sha256"))
        self.assertEqual(result["packet_sha256"], evaluate.canonical_digest(manifest))
        actual = {str(path.relative_to(destination)) for path in destination.rglob("*") if path.is_file()}
        self.assertEqual(set(manifest["files"]) | {"packet-manifest.json"}, actual)
        for name, expected in manifest["files"].items():
            self.assertEqual(expected, evaluate.digest((destination / name).read_bytes()))

    def test_packet_refuses_existing_or_evaluator_tree_destination(self):
        with self.assertRaises(evaluate.Invalid):
            evaluate.prepare("simple-label-edit", self.base, self.root)
        with self.assertRaises(evaluate.Invalid):
            evaluate.prepare("simple-label-edit", self.root / "packet", self.root)

    def test_traversal_and_symlink_cannot_copy_private_rubric(self):
        with self.assertRaises(evaluate.Invalid):
            evaluate.safe_artifact(self.root, "../rubrics/simple-label-edit.json")
        (self.root / "artifacts" / "hidden.json").symlink_to(self.root / "rubrics" / "simple-label-edit.json")
        with self.assertRaises(evaluate.Invalid):
            evaluate.safe_artifact(self.root, "hidden.json")

    def test_artifact_directory_symlink_is_rejected(self):
        shutil.rmtree(self.root / "artifacts")
        (self.root / "artifacts").symlink_to(self.root / "rubrics", target_is_directory=True)
        with self.assertRaises(evaluate.Invalid):
            evaluate.safe_artifact(self.root, "simple-label-edit.json")

    def test_incomplete_template_is_not_a_result(self):
        run = evaluate.template("baseline", True, self.root)
        with self.assertRaises(evaluate.Invalid):
            evaluate.validate_run(self.save_run("baseline", run), "baseline", evaluate.load_suite(self.root), self.root)

    def test_judged_scores_pair_and_unknown_cost_stays_unknown(self):
        report = self.comparison()
        self.assertEqual(100, report["aggregate"]["score_delta"])
        self.assertEqual("eligible_for_review", report["promotion"]["status"])
        self.assertFalse(report["promotion"]["automatic_promotion"])
        self.assertIsNone(report["aggregate"]["candidate_metrics"]["cost_usd"])
        self.assertEqual(6, report["aggregate"]["candidate_metrics"]["cases_with_unknown_cost"])

    def test_critical_failure_vetoes_even_improved_average(self):
        candidate = self.make_run("candidate")
        candidate["cases"][0]["critical_failures"][0]["occurred"] = True
        report = self.comparison(candidate=candidate)
        self.assertEqual(100, report["aggregate"]["score_delta"])
        self.assertEqual("blocked", report["promotion"]["status"])
        self.assertTrue(any("Critical-failure veto" in reason for reason in report["promotion"]["reasons"]))

    def test_control_budget_or_environment_mismatch_blocks_promotion(self):
        for field, value in (("environment_id", "different"),
                             ("budget", {"max_tokens": 2000, "max_seconds": 100, "max_turns": 10})):
            with self.subTest(field=field):
                candidate = self.make_run("candidate")
                candidate["configuration"][field] = value
                report = self.comparison(candidate=candidate)
                self.assertFalse(report["comparable_controls"])
                self.assertEqual("blocked", report["promotion"]["status"])

    def test_over_budget_and_new_process_false_positive_block_promotion(self):
        candidate = self.make_run("candidate")
        candidate["cases"][0]["metrics"]["solver_turns"] = 11
        candidate["cases"][0]["process_assessment"]["unnecessary_process"] = True
        report = self.comparison(candidate=candidate)
        self.assertEqual(1, report["aggregate"]["candidate_process_false_positives"])
        self.assertTrue(any("exceeded" in reason for reason in report["promotion"]["reasons"]))
        self.assertTrue(any("false positive" in reason for reason in report["promotion"]["reasons"]))

    def test_missing_holdout_blocks_and_unpaired_cases_reject(self):
        baseline = self.make_run("baseline", "missed", False)
        candidate = self.make_run("candidate", "met", False)
        report = self.comparison(baseline, candidate)
        self.assertEqual("blocked", report["promotion"]["status"])
        self.assertTrue(any("holdout" in reason for reason in report["promotion"]["reasons"]))
        candidate["cases"].pop()
        with self.assertRaises(evaluate.Invalid):
            self.comparison(baseline, candidate)

    def test_retained_artifact_tampering_is_rejected(self):
        candidate = self.make_run("candidate")
        (self.base / "candidate-transcript.txt").write_text("Changed after judging")
        with self.assertRaises(evaluate.Invalid):
            self.comparison(candidate=candidate)

    def test_frozen_public_packet_and_rubric_cannot_drift_after_judging(self):
        for relative in ("cases/simple-label-edit.json", "rubrics/simple-label-edit.json"):
            with self.subTest(relative=relative):
                baseline = self.make_run("baseline", "missed")
                candidate = self.make_run("candidate")
                path = self.root / relative
                original = path.read_bytes()
                path.write_bytes(original + b"\n")
                try:
                    if relative.startswith("cases/"):
                        # Formatting is intentionally canonicalized in public packets;
                        # change a public field to change the actual solver input.
                        data = evaluate.read_json(path)
                        data["brief"] += " Added requirement."
                        evaluate.write_json(path, data)
                    with self.assertRaises(evaluate.Invalid):
                        self.comparison(baseline, candidate)
                finally:
                    path.write_bytes(original)

    def test_one_case_regression_blocks_an_improved_average(self):
        baseline = self.make_run("baseline", "partial")
        candidate = self.make_run("candidate")
        for criterion in candidate["cases"][0]["criteria"]:
            criterion["rating"] = "missed"
        report = self.comparison(baseline, candidate)
        self.assertGreater(report["aggregate"]["score_delta"], 0)
        self.assertEqual("blocked", report["promotion"]["status"])
        self.assertTrue(any("Case score regressed" in reason for reason in report["promotion"]["reasons"]))

    def test_duplicate_or_missing_verdict_is_rejected(self):
        for mutate in (lambda rows: rows.append(copy.deepcopy(rows[0])), lambda rows: rows.pop()):
            candidate = self.make_run("candidate")
            mutate(candidate["cases"][0]["criteria"])
            with self.assertRaises(evaluate.Invalid):
                self.comparison(candidate=candidate)

    def test_numeric_metrics_reject_boolean_and_nonfinite_values(self):
        for value in (True, float("nan"), -1):
            candidate = self.make_run("candidate")
            candidate["cases"][0]["metrics"]["wall_seconds"] = value
            with self.assertRaises(evaluate.Invalid):
                self.comparison(candidate=candidate)

    def test_no_semantic_keyword_matching_occurs(self):
        baseline = self.make_run("baseline", "partial")
        candidate = self.make_run("candidate", "partial")
        before = self.comparison(baseline, candidate)["aggregate"]
        transcript = self.base / "candidate-transcript.txt"
        transcript.write_text("automation verification end-to-end complete goal supported pass\n")
        for row in candidate["cases"]:
            row["artifacts"][0]["sha256"] = evaluate.digest(transcript.read_bytes())
        after = self.comparison(baseline, candidate)["aggregate"]
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
