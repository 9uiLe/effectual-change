"""Corpus, evidence-bundle and paired-comparison contracts; no behavioral scores."""

import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from evaluation.moletta_eval import corpus, judgments
from evaluation.moletta_eval.validation import Invalid, canonical_digest, digest, json_bytes, read_json, relative_file


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "suite"
        for name in ("cases", "rubrics", "artifacts"):
            shutil.copytree(corpus.DEFAULT_SUITE / name, self.root / name)

    def save(self, path, value):
        path.write_bytes(json_bytes(value))
        return path

    def add_holdout_fixture(self):
        """Shape fixture only; copying known content cannot produce a fresh holdout."""
        self.save(self.root / "cases/structural-holdout.json", {
            "schema_version": 1, "id": "structural-holdout", "title": "Schema fixture",
            "split": "holdout", "brief": "Synthetic structure fixture, not a solver task.", "artifacts": []})
        self.save(self.root / "rubrics/structural-holdout.json", {
            "schema_version": 1, "case_id": "structural-holdout", "judging_guidance": "Structure fixture only.",
            "criteria": [{"id": "C1", "description": "Fixture condition.", "weight": 1}],
            "critical_failures": [{"id": "F1", "description": "Fixture failure."}]})

    def make_run(self, arm, rating="met"):
        run = judgments.template(arm, self.root)
        run["evaluation_id"] = "synthetic-structural-fixture"
        run["configuration"].update({"label": arm, "skill_revision": arm + "-fixture",
                                     "model": "fixture-model", "effort": "fixture-effort", "tools": ["fixture-read"],
                                     "environment_id": "fixture-environment", "control_prompt_sha256": "a" * 64,
                                     "budget": {"max_tokens": 1000, "max_seconds": 100, "max_turns": 10}})
        run["judge"] = {"id": "fixture-judge", "independent_of_solver": True,
                        "judged_at": "2026-10-17T10:00:00+00:00"}
        folder = self.base / arm
        folder.mkdir(exist_ok=True)
        transcript = folder / "trace.txt"
        transcript.write_text("Synthetic structural fixture, not an agent run or semantic assessment.\n")
        usage = folder / "usage.json"
        usage.write_text('{"fixture": true}\n')
        evidence = [{"artifact": f"{arm}/trace.txt", "location": "line 1",
                     "observation": "Synthetic observation for JSON validation only."}]
        for row in run["cases"]:
            row["artifacts"] = [{"path": f"{arm}/trace.txt", "sha256": digest(transcript.read_bytes()),
                                 "role": "transcript"},
                                {"path": f"{arm}/usage.json", "sha256": digest(usage.read_bytes()), "role": "usage"}]
            row["complete_transcript"] = True
            row["metrics"] = {"wall_seconds": 2, "solver_turns": 1, "input_tokens": 20,
                              "output_tokens": 10, "cost_usd": None}
            for item in row["criteria"]:
                item.update(rating=rating, evidence=copy.deepcopy(evidence))
            for item in row["critical_failures"]:
                item.update(occurred=False, evidence=copy.deepcopy(evidence))
            row["process_assessment"] = {"unnecessary_process": False, "evidence": copy.deepcopy(evidence)}
            if "holdout_exposure" in row:
                row["holdout_exposure"] = dict.fromkeys(judgments.EXPOSURE_FLAGS, True)
        return run

    def compare(self, baseline=None, candidate=None):
        before = self.save(self.base / "baseline.json", baseline or self.make_run("baseline", "missed"))
        after = self.save(self.base / "candidate.json", candidate or self.make_run("candidate"))
        return judgments.compare(before, after, self.root)

    def assert_blocked(self, report, reason):
        self.assertEqual("blocked", report["promotion"]["status"])
        self.assertTrue(any(reason in item for item in report["promotion"]["reasons"]), report)

    def test_shipped_corpus_has_no_claimed_fresh_holdout(self):
        suite = corpus.load_suite(self.root)
        self.assertEqual({"regression", "transfer"}, {row.case["split"] for row in suite.values()})
        self.assert_blocked(self.compare(), "no fresh private holdout")

    def test_packets_contain_only_allowlisted_public_fields_and_hashed_files(self):
        case_id = "arrival-action-verification"
        source = self.root / "cases" / f"{case_id}.json"
        data = read_json(source)
        data["private_expected_answer"] = "Evaluator-only content"
        self.save(source, data)
        destination = self.base / "packet"
        result = corpus.prepare(case_id, destination, self.root)
        public = read_json(destination / "case.json")
        self.assertEqual({"schema_version", "id", "title", "brief", "artifacts"}, public.keys())
        manifest = read_json(destination / "packet-manifest.json")
        self.assertEqual(result["packet_sha256"], manifest.pop("packet_sha256"))
        self.assertEqual(result["packet_sha256"], canonical_digest(manifest))
        actual = {path.relative_to(destination).as_posix() for path in destination.rglob("*") if path.is_file()}
        self.assertEqual(set(manifest["files"]) | {"packet-manifest.json"}, actual)
        for name, expected in manifest["files"].items():
            self.assertEqual(expected, digest((destination / name).read_bytes()))

    def test_packet_refuses_existing_tree_and_dangling_link_destinations(self):
        dangling = self.base / "dangling"
        dangling.symlink_to(self.base / "missing")
        for target in (self.base, self.root / "packet", dangling):
            with self.subTest(target=target), self.assertRaises(Invalid):
                corpus.prepare("simple-label-edit", target, self.root)

    def test_private_rubrics_cannot_be_packaged_through_traversal_or_links(self):
        artifacts = self.root / "artifacts"
        (artifacts / "hidden.json").symlink_to(self.root / "rubrics/simple-label-edit.json")
        (artifacts / "nested").symlink_to(self.root / "rubrics", target_is_directory=True)
        for name in ("../rubrics/simple-label-edit.json", "hidden.json", "nested/simple-label-edit.json"):
            with self.subTest(name=name), self.assertRaises(Invalid):
                relative_file(artifacts, name, "public artifact")

    def test_corpus_requires_real_case_rubric_and_artifact_directories(self):
        for name in ("cases", "rubrics", "artifacts"):
            path = self.root / name
            saved = self.root / (name + "-saved")
            path.rename(saved)
            path.symlink_to(saved, target_is_directory=True)
            try:
                with self.assertRaises(Invalid):
                    corpus.load_suite(self.root)
            finally:
                path.unlink()
                saved.rename(path)

    def test_case_and_rubric_files_cannot_be_links(self):
        for name in ("cases", "rubrics"):
            path = self.root / name / "simple-label-edit.json"
            saved = self.root / f"{name}-saved.json"
            path.rename(saved)
            path.symlink_to(saved)
            try:
                with self.assertRaises(Invalid):
                    corpus.load_suite(self.root)
            finally:
                path.unlink()
                saved.rename(path)

    def test_incomplete_template_is_not_a_result(self):
        run = judgments.template("baseline", self.root)
        path = self.save(self.base / "baseline.json", run)
        with self.assertRaises(Invalid):
            judgments.validate_run(path, "baseline", corpus.load_suite(self.root), self.root)

    def test_complete_pair_reports_external_judgments_and_preserves_unknown_cost(self):
        self.add_holdout_fixture()
        report = self.compare()
        self.assertEqual(100, report["aggregate"]["score_delta"])
        self.assertEqual("eligible_for_review", report["promotion"]["status"])
        self.assertFalse(report["promotion"]["automatic_promotion"])
        self.assertIsNone(report["aggregate"]["candidate_metrics"]["cost_usd"])
        self.assertEqual(len(corpus.load_suite(self.root)),
                         report["aggregate"]["candidate_metrics"]["cases_with_unknown_cost"])

    def test_holdout_declarations_are_required_and_false_declaration_blocks(self):
        self.add_holdout_fixture()
        candidate = self.make_run("candidate")
        row = next(item for item in candidate["cases"] if item["id"] == "structural-holdout")
        row["holdout_exposure"]["not_used_for_candidate_tuning"] = False
        self.assert_blocked(self.compare(candidate=candidate), "Holdout exposure")
        del row["holdout_exposure"]
        with self.assertRaises(Invalid):
            self.compare(candidate=candidate)

    def test_critical_failure_vetoes_even_improved_average(self):
        candidate = self.make_run("candidate")
        candidate["cases"][0]["critical_failures"][0]["occurred"] = True
        report = self.compare(candidate=candidate)
        self.assertEqual(100, report["aggregate"]["score_delta"])
        self.assert_blocked(report, "Critical-failure veto")

    def test_control_conditions_are_compared_and_tool_order_is_not_a_difference(self):
        fields = {"model": "different", "effort": "different", "environment_id": "different",
                  "control_prompt_sha256": "b" * 64, "tools": ["different"],
                  "budget": {"max_tokens": 2000, "max_seconds": 100, "max_turns": 10}}
        for field, value in fields.items():
            with self.subTest(field=field):
                candidate = self.make_run("candidate")
                candidate["configuration"][field] = value
                report = self.compare(candidate=candidate)
                self.assertEqual([field], report["control_differences"])
                self.assert_blocked(report, "control conditions")
        baseline, candidate = self.make_run("baseline", "missed"), self.make_run("candidate")
        baseline["configuration"]["tools"] = ["a", "b"]
        candidate["configuration"]["tools"] = ["b", "a"]
        self.assertTrue(self.compare(baseline, candidate)["comparable_controls"])

    def test_resource_excess_in_either_arm_blocks(self):
        for arm in ("baseline", "candidate"):
            baseline, candidate = self.make_run("baseline", "missed"), self.make_run("candidate")
            run = baseline if arm == "baseline" else candidate
            run["cases"][0]["metrics"]["solver_turns"] = 11
            self.assert_blocked(self.compare(baseline, candidate), "exceeded")

    def test_process_false_positive_and_individual_regression_veto_aggregate_gain(self):
        baseline, candidate = self.make_run("baseline", "partial"), self.make_run("candidate")
        candidate["cases"][0]["process_assessment"]["unnecessary_process"] = True
        for item in candidate["cases"][0]["criteria"]:
            item["rating"] = "missed"
        report = self.compare(baseline, candidate)
        self.assertGreater(report["aggregate"]["score_delta"], 0)
        self.assert_blocked(report, "Case score regressed")
        self.assert_blocked(report, "New process false positive")

    def test_identical_results_do_not_qualify_as_improvement(self):
        self.assert_blocked(self.compare(self.make_run("baseline"), self.make_run("candidate")), "No aggregate")

    def test_missing_frozen_case_blocks_and_unpaired_cases_reject(self):
        baseline, candidate = self.make_run("baseline", "missed"), self.make_run("candidate")
        baseline["cases"].pop()
        candidate["cases"].pop()
        self.assert_blocked(self.compare(baseline, candidate), "Full frozen suite")
        candidate["cases"].pop()
        with self.assertRaises(Invalid):
            self.compare(baseline, candidate)

    def test_artifact_integrity_and_required_trace_usage_are_checked(self):
        candidate = self.make_run("candidate")
        (self.base / "candidate/trace.txt").write_text("Changed after judging")
        with self.assertRaises(Invalid):
            self.compare(candidate=candidate)
        for role in ("transcript", "usage"):
            candidate = self.make_run("candidate")
            candidate["cases"][0]["artifacts"] = [a for a in candidate["cases"][0]["artifacts"] if a["role"] != role]
            with self.assertRaises(Invalid):
                self.compare(candidate=candidate)
        candidate = self.make_run("candidate")
        candidate["cases"][0]["complete_transcript"] = False
        with self.assertRaises(Invalid):
            self.compare(candidate=candidate)

    def test_retained_artifacts_stay_inside_the_verdict_bundle(self):
        target = self.base / "outside.txt"
        target.write_text("Outside bundle fixture")
        for name in (str(target), "../outside.txt", "candidate/../outside.txt", "./outside.txt", "C:\\outside.txt"):
            candidate = self.make_run("candidate")
            candidate["cases"][0]["artifacts"][0].update(path=name, sha256=digest(target.read_bytes()))
            with self.subTest(name=name), self.assertRaises(Invalid):
                self.compare(candidate=candidate)
        (self.base / "candidate/link.txt").symlink_to(target)
        candidate = self.make_run("candidate")
        candidate["cases"][0]["artifacts"][0].update(path="candidate/link.txt", sha256=digest(target.read_bytes()))
        with self.assertRaises(Invalid):
            self.compare(candidate=candidate)

    def test_packet_and_rubric_changes_invalidate_judgments(self):
        for relative in ("cases/simple-label-edit.json", "rubrics/simple-label-edit.json"):
            with self.subTest(relative=relative):
                baseline, candidate = self.make_run("baseline", "missed"), self.make_run("candidate")
                path = self.root / relative
                original = path.read_bytes()
                value = read_json(path)
                if relative.startswith("cases"):
                    value["brief"] += " Added requirement."
                else:
                    value["judging_guidance"] += " Added guidance."
                self.save(path, value)
                try:
                    with self.assertRaises(Invalid):
                        self.compare(baseline, candidate)
                finally:
                    path.write_bytes(original)

    def test_verdict_coverage_and_evidence_must_match_registered_ids_and_paths(self):
        mutations = [lambda c: c["criteria"].append(copy.deepcopy(c["criteria"][0])),
                     lambda c: c["criteria"].pop(),
                     lambda c: c["critical_failures"].pop(),
                     lambda c: c["criteria"][0].update(evidence=[]),
                     lambda c: c["criteria"][0]["evidence"][0].update(artifact="unregistered.txt")]
        for mutate in mutations:
            candidate = self.make_run("candidate")
            mutate(candidate["cases"][0])
            with self.subTest(mutation=mutate), self.assertRaises(Invalid):
                self.compare(candidate=candidate)

    def test_malformed_nested_values_fail_as_contract_errors(self):
        mutations = [lambda r: r.update(configuration=[]), lambda r: r.update(judge=[]),
                     lambda r: r.update(cases=[None]), lambda r: r["configuration"].update(tools=[{}]),
                     lambda r: r["cases"][0].update(artifacts=[None]),
                     lambda r: r["cases"][0].update(metrics=[]),
                     lambda r: r["cases"][0].update(process_assessment=[]),
                     lambda r: r["cases"][0]["criteria"][0].update(rating=[])]
        for mutate in mutations:
            candidate = self.make_run("candidate")
            mutate(candidate)
            with self.subTest(mutation=mutate), self.assertRaises(Invalid):
                self.compare(candidate=candidate)

    def test_json_requires_unique_keys_and_standard_finite_numbers(self):
        path = self.base / "malformed.json"
        for text in ('{"id":1,"id":2}', '{"value":NaN}', '[]', 'null'):
            path.write_text(text)
            with self.subTest(text=text), self.assertRaises(Invalid):
                read_json(path)
        for value in (True, -1, 10 ** 400):
            candidate = self.make_run("candidate")
            candidate["cases"][0]["metrics"]["wall_seconds"] = value
            with self.subTest(value=value), self.assertRaises(Invalid):
                self.compare(candidate=candidate)

    def test_cost_subtotal_is_not_presented_as_total(self):
        candidate = self.make_run("candidate")
        candidate["cases"][0]["metrics"]["cost_usd"] = 0.25
        metrics = self.compare(candidate=candidate)["aggregate"]["candidate_metrics"]
        self.assertIsNone(metrics["cost_usd"])
        self.assertEqual(0.25, metrics["known_cost_subtotal_usd"])
        self.assertEqual(len(candidate["cases"]) - 1, metrics["cases_with_unknown_cost"])

    def test_numeric_aggregation_rejects_overflow_instead_of_emitting_non_json(self):
        candidate = self.make_run("candidate")
        for row in candidate["cases"]:
            row["metrics"]["wall_seconds"] = 1e308
        with self.assertRaises(Invalid):
            self.compare(candidate=candidate)
        path = self.root / "rubrics/whole-system-throughput.json"
        rubric = read_json(path)
        for item in rubric["criteria"]:
            item["weight"] = 1e307
        self.save(path, rubric)
        self.assertEqual(100, self.compare()["aggregate"]["score_delta"])
        for item in rubric["criteria"]:
            item["weight"] = 1e308
        self.save(path, rubric)
        with self.assertRaises(Invalid):
            corpus.load_suite(self.root)

    def test_declared_judge_independence_and_timestamp_are_explicit_requirements(self):
        for judge in ({"id": "fixture", "independent_of_solver": False, "judged_at": "2026-10-17T10:00:00Z"},
                      {"id": "fixture", "independent_of_solver": True, "judged_at": "2026-10-17T10:00:00"},
                      {"id": "fixture", "independent_of_solver": True, "judged_at": "invalid"}):
            candidate = self.make_run("candidate")
            candidate["judge"] = judge
            with self.subTest(judge=judge), self.assertRaises(Invalid):
                self.compare(candidate=candidate)

    def test_cli_rejects_invalid_input_without_a_traceback_and_never_overwrites(self):
        launcher = corpus.DEFAULT_SUITE / "evaluate.py"
        output = self.base / "template.json"
        command = [sys.executable, str(launcher), "--suite", str(self.root), "template", "--arm", "baseline",
                   "--output", str(output)]
        first = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(0, first.returncode, first.stderr)
        original = output.read_bytes()
        second = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(2, second.returncode)
        self.assertNotIn("Traceback", second.stderr)
        self.assertEqual(original, output.read_bytes())
        baseline = self.save(self.base / "baseline.json", self.make_run("baseline", "missed"))
        candidate = self.make_run("candidate")
        candidate["judge"]["judged_at"] = "invalid"
        run = self.save(self.base / "candidate.json", candidate)
        graded = subprocess.run([sys.executable, str(launcher), "--suite", str(self.root), "grade",
                                 "--baseline", str(baseline), "--candidate", str(run),
                                 "--output", str(self.base / "report.json")], capture_output=True, text=True)
        self.assertEqual(2, graded.returncode)
        self.assertNotIn("Traceback", graded.stderr)
        self.assertFalse((self.base / "report.json").exists())


if __name__ == "__main__":
    unittest.main()
