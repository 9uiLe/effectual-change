"""Public CLI wiring, persistence and composition guarantees.

The subprocess tests exercise real CLI parsing and temporary local files. The
device composition test substitutes policy readiness only: existing policy tests
own capability/observation correctness, and device tests own native lifecycles.
No real mobile device is allocated, launched, stopped or deleted here.
"""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import uuid


SCRIPTS = Path(__file__).resolve().parents[1] / "skills/moletta/scripts"
sys.path.insert(0, str(SCRIPTS))
import devices
import moletta
import store


class CliOperationsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.project = self.base / "project"
        self.project.mkdir()
        self.brief = self.project / "request.md"
        self.brief.write_text("Observe a synthetic setting change.", encoding="utf-8")
        self.run = self.project / ".moletta-runs" / "fixture"
        self.environment = os.environ.copy()
        for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_CEILING_DIRECTORIES"):
            self.environment.pop(key, None)

    def cli(self, *arguments, cwd=None, expected=0):
        result = subprocess.run([sys.executable, str(SCRIPTS / "moletta.py"), *map(str, arguments)],
            cwd=cwd or self.project, env=self.environment, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, expected, result.stderr or result.stdout)
        self.assertNotIn("Traceback", result.stderr)
        return json.loads(result.stdout if expected in (0, 1) else result.stderr)

    def initialize(self):
        return self.cli("init", self.run, "--brief", self.brief, "--goal", "Observe the saved setting")

    def selected_json(self, name, value):
        path = self.base / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    @unittest.skipUnless(shutil.which("git"), "Git is required for worktree discovery")
    def test_default_init_from_a_subdirectory_creates_distinct_worktree_local_units(self):
        initialized = subprocess.run(["git", "-C", str(self.project), "init", "--quiet"],
            env=self.environment, capture_output=True, text=True, timeout=10)
        self.assertEqual(initialized.returncode, 0, initialized.stderr)
        nested = self.project / "src/nested"
        nested.mkdir(parents=True)
        relative_brief = nested / "task.md"
        relative_brief.write_text(self.brief.read_text(), encoding="utf-8")
        first = self.cli("init", "--brief", "task.md", "--goal", "Synthetic CLI task", cwd=nested)
        self.assertEqual(first["gitignore"]["status"], "missing")
        ignore = self.project / ".gitignore"
        self.assertFalse(ignore.exists())
        original_ignore = b"# Existing project rule\n*.generated\n"
        ignore.write_bytes(original_ignore)
        second = self.cli("init", "--brief", "task.md", "--goal", "Synthetic CLI task", cwd=nested)
        workspace = self.project / ".moletta-runs"
        self.assertNotEqual(first["run"], second["run"])
        self.assertEqual(ignore.read_bytes(), original_ignore)
        self.assertFalse((nested / ".moletta-runs").exists())
        for value in (first, second):
            self.assertEqual(Path(value["project"]), self.project)
            self.assertEqual(Path(value["workspace"]), workspace)
            run = Path(value["run"])
            self.assertEqual(run.parent, workspace)
            self.assertEqual((run / "brief.md").read_bytes(), relative_brief.read_bytes())
            self.assertEqual(json.loads((run / "journal.json").read_text())["events"], [])
        readme = (workspace / "README.md").read_text(encoding="utf-8")
        for concept in ("brief.md", "intent.json", "journal.json", "artifacts/", "checkpoints/", "/.moletta-runs/"):
            self.assertIn(concept, readme)
        self.assertNotEqual(store.load(Path(first["run"])).run.run_id,
                            store.load(Path(second["run"])).run.run_id)

    def samples(self, name, values, *, revision="fixture-base", environment="fixture quiet lab"):
        source = self.base / name
        rows = [{"metric": "launch", "unit": "ms", "platform": "ios", "device": "fixture-device",
            "device_kind": "simulator", "os_version": "fixture-os", "environment": environment,
            "scenario": "fixture-launch", "build_revision": revision, "collector": "fixture-exporter",
            "sample_id": f"raw-sample-do-not-copy-{index}", "value": value}
            for index, value in enumerate(values)]
        source.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        return source

    def summarize(self, source):
        receipt = self.cli("metrics", "summarize", self.run, "--input", source, "--format", "jsonl")
        output = Path(receipt["output"])
        self.assertEqual(output.parent, self.run / "metrics")
        self.assertEqual(receipt["sha256"], hashlib.sha256(output.read_bytes()).hexdigest())
        self.assertIs(receipt["raw_input_copied"], False)
        return output, json.loads(output.read_text(encoding="utf-8"))

    def test_metrics_cli_persists_only_derived_summaries_and_matched_comparison(self):
        self.initialize()
        baseline_source = self.samples("baseline.jsonl", [10, 20, 30])
        candidate_source = self.samples("candidate.jsonl", [9, 18, 27], revision="fixture-candidate")
        before = {path: path.read_bytes() for path in (baseline_source, candidate_source)}
        baseline, base_value = self.summarize(baseline_source)
        candidate, candidate_value = self.summarize(candidate_source)
        self.assertEqual(base_value["kind"], "performance_summary")
        self.assertEqual(candidate_value["sample_count"], 3)
        self.assertEqual(base_value["source"]["sha256"], hashlib.sha256(before[baseline_source]).hexdigest())
        receipt = self.cli("metrics", "compare", self.run, "--baseline", baseline, "--candidate", candidate)
        comparison = Path(receipt["output"])
        self.assertEqual(comparison.parent, self.run / "metrics")
        self.assertIs(receipt["raw_input_copied"], False)
        value = json.loads(comparison.read_text(encoding="utf-8"))
        self.assertEqual(value["kind"], "performance_comparison")
        self.assertEqual(value["groups"][0]["candidate_minus_baseline"]["mean"],
                         {"absolute": -2, "percent": -10})
        self.assertEqual(set((self.run / "metrics").iterdir()), {baseline, candidate, comparison})
        self.assertEqual(list((self.run / "artifacts").iterdir()), [])
        for path, original in before.items():
            self.assertEqual(path.read_bytes(), original)
        for path in self.run.rglob("*"):
            if path.is_file():
                saved = path.read_bytes()
                self.assertNotIn(b"raw-sample-do-not-copy", saved)
                self.assertNotIn(str(baseline_source).encode(), saved)
                self.assertNotIn(str(candidate_source).encode(), saved)

    def test_metrics_cli_condition_mismatch_fails_without_publishing_a_comparison(self):
        self.initialize()
        baseline, _ = self.summarize(self.samples("baseline.jsonl", [10, 20]))
        candidate, _ = self.summarize(self.samples("different-condition.jsonl", [8, 16],
                                                  environment="fixture busy lab"))
        published = set((self.run / "metrics").iterdir())
        error = self.cli("metrics", "compare", self.run, "--baseline", baseline, "--candidate", candidate,
                         expected=2)
        self.assertIn("Comparison refused", error["error"])
        self.assertEqual(set((self.run / "metrics").iterdir()), published)

    def test_delegation_cli_records_scoped_choices_and_usage_without_spawning(self):
        self.initialize()
        initial = self.cli("delegation", "status", self.run)
        self.assertEqual((initial["mode"], initial["active"]), ("disabled", 0))
        now = datetime.now(timezone.utc)
        approval = self.selected_json("approval.json", {"schema_version": 1, "host": "codex", "mode": "adaptive",
            "approval_reference": "fictional approval fixture", "expires_at": (now + timedelta(hours=1)).isoformat(),
            "max_parallel": 1, "max_total_tokens": 100,
            "choices": [{"role": "execution", "model": "fixture-small", "effort": "medium"}]})
        catalog = self.selected_json("catalog.json", {"schema_version": 1, "host": "codex",
            "observed_at": now.isoformat(), "source": "fictional host capability fixture",
            "models": [{"id": "fixture-small", "efforts": ["low", "medium"]}]})
        request = {"task_id": "CLI1", "role": "execution", "model": "fixture-small", "effort": "medium",
            "max_tokens": 40, "max_seconds": 30,
            "context_sha256": hashlib.sha256(b"synthetic scoped context").hexdigest()}
        request_path = self.selected_json("request.json", request)
        configured = self.cli("delegation", "configure", self.run, "--approval", approval)
        self.assertIs(configured["configured"], True)
        self.assertIs(configured["approval_is_attested"], True)
        reserved = self.cli("delegation", "reserve", self.run, "--request", request_path, "--catalog", catalog)
        self.assertIs(reserved["spawn_performed"], False)
        assignment = reserved["assignment"]
        self.assertEqual((assignment["role"], assignment["model"], assignment["effort"]),
                         ("execution", "fixture-small", "medium"))
        status = self.cli("delegation", "status", self.run)
        self.assertEqual((status["active"], status["charged_or_reserved_tokens"]), (1, 40))
        usage = self.selected_json("usage.json", {"total_tokens": 32, "cost_usd": None, "source": "fixture host usage"})
        completed = self.cli("delegation", "complete", self.run, "--assignment", assignment["id"], "--usage", usage)
        self.assertIs(completed["recorded"], True)
        self.assertIs(completed["usage_is_attested"], True)
        self.assertEqual((completed["status"]["active"], completed["status"]["charged_or_reserved_tokens"]), (0, 32))
        self.assertIsNone(completed["status"]["cost_usd"])
        self.assertIs(completed["status"]["limits_enforced_by_host"], False)
        request_path = self.selected_json("over-budget.json", {**request, "task_id": "CLI2", "max_tokens": 69})
        error = self.cli("delegation", "reserve", self.run, "--request", request_path, "--catalog", catalog, expected=2)
        self.assertIn("budget", error["error"])
        final = self.cli("delegation", "status", self.run)
        self.assertEqual(len(final["assignments"]), 1)
        self.assertEqual(final["charged_or_reserved_tokens"], 32)

    def in_process_cli(self, *arguments):
        output, errors = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            result = moletta.main(list(map(str, arguments)))
        self.assertEqual(errors.getvalue(), "")
        return result, json.loads(output.getvalue())

    def test_device_receipt_composition_blocks_verify_and_surfaces_cleanup_after_actions(self):
        """Own only CLI composition; a ready policy stub is not task outcome evidence."""
        self.initialize()
        ident = uuid.uuid4().hex
        device_id = str(uuid.uuid4()).upper()
        timestamp = datetime.now(timezone.utc).isoformat()
        receipt = {"schema_version": 1, "lease_id": ident, "name": f"moletta-{ident}",
            "owner_token": uuid.uuid4().hex, "run": str(self.run), "state_dir": str(self.base / "unused-host-state"),
            "platform": "ios", "runtime": "fixture-runtime", "device_type": "fixture-phone",
            "device_id": device_id, "destination": device_id, "state": "allocated",
            "created_at": timestamp, "updated_at": timestamp, "tools": {"xcrun": "/fixture/xcrun"},
            "launch_env": {}, "launch_argv": ["/fixture/xcrun", "simctl", "boot", device_id]}
        directory = self.run / "devices"
        directory.mkdir()
        path = directory / f"{ident}.json"
        store.write_json(path, receipt)
        def ready_policy(run, stage, *unused):
            return {"stage": stage, "structural_readiness": True, "semantic_review_required": True, "findings": []}
        with mock.patch.object(moletta.policy, "evaluate", side_effect=ready_policy), \
             mock.patch.object(devices, "_command", side_effect=AssertionError("No real mobile operation allowed")):
            code, value = self.in_process_cli("check", self.run, "--stage", "verify")
            self.assertEqual(code, 1)
            self.assertIs(value["structural_readiness"], False)
            self.assertIn("DEVICE_CLEANUP_PENDING", {item["code"] for item in value["findings"]})
            plan = store.read_json(self.run / "plan.json")
            plan["next_action"] = {"kind": "explore", "question": "Synthetic remaining observation?",
                "rationale": "Collect evidence before releasing the fixture device", "timebox_minutes": 1,
                "stop_condition": "One observation recorded", "experiment_id": None}
            store.write_json(self.run / "plan.json", plan)
            self.assertEqual(self.in_process_cli("next", self.run)[1]["action"], "execute_bounded_action")
            plan["next_action"] = None
            store.write_json(self.run / "plan.json", plan)
            code, value = self.in_process_cli("next", self.run)
            self.assertEqual(code, 0)
            self.assertEqual(value["action"], "release_owned_devices")
            self.assertEqual([item["lease_id"] for item in value["leases"]], [ident])
            # Change only the synthetic receipt; real cleanup belongs to the
            # native adapter lifecycle tests, not to this composition fixture.
            store.write_json(path, {**receipt, "state": "released"})
            self.assertEqual(self.in_process_cli("check", self.run, "--stage", "verify")[0], 0)
            self.assertEqual(self.in_process_cli("next", self.run)[1]["action"], "semantic_outcome_review")
        self.assertFalse((self.base / "unused-host-state").exists())


if __name__ == "__main__":
    unittest.main()
