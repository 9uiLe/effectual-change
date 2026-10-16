"""Offline checks for the harness; these do not replace the Docker comparison."""

import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import grade


class GraderTests(unittest.TestCase):
    def test_sandbox_is_offline_nonroot_readonly_and_bounded(self):
        args = grade.command("sha256:frozen", Path("/candidate"), Path("/baseline"), Path("/scratch"))
        for option, value in [("--network", "none"), ("--user", "65534:65534"), ("--cap-drop", "ALL"), ("--security-opt", "no-new-privileges"), ("--memory", "512m"), ("--memory-swap", "512m"), ("--pids-limit", "256"), ("--cpus", "2")]:
            self.assertEqual(args[args.index(option) + 1], value)
        self.assertIn("--read-only", args)
        self.assertEqual(args[-1], "sha256:frozen")
        for destination in ["/candidate", "/oracle", "/candidate/node_modules", "/grader"]:
            mounts = [s for s in args if f"dst={destination}," in s]
            self.assertEqual(len(mounts), 1)
            self.assertTrue(mounts[0].endswith(",readonly"))
        self.assertNotIn("/var/run/docker.sock", " ".join(args))
        self.assertIn("type=bind,src=/scratch,dst=/work", args)

    def test_summary_keeps_scores_and_deduplicates_failure_names(self):
        result = grade.summarize(subprocess.CompletedProcess([], 1, "", "(fail) prefix [1.2ms]\n(fail) prefix [1.2ms]\n59 pass\n1 fail\n"))
        self.assertEqual(result, {"exit_code": 1, "passed": 59, "failed": 1, "failed_checks": ["prefix"]})

    def test_no_results_or_timeout_cannot_be_success(self):
        self.assertFalse(grade.passed({}, 60))
        self.assertFalse(grade.passed({"exit_code": 0, "passed": 0, "failed": 0}, 60))
        self.assertFalse(grade.passed({"exit_code": None, "status": "timeout"}, 0))
        self.assertTrue(grade.passed({"exit_code": 0, "passed": 60, "failed": 0}, 60))

    def test_timeout_force_removes_named_container(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch("grade.subprocess.run", side_effect=[subprocess.TimeoutExpired("docker", 1), subprocess.CompletedProcess([], 0)]) as run:
                result = grade.invoke(["docker", "run", "--rm", "image", "bun"], Path(directory) / "log", timeout=1)
            self.assertEqual(result["status"], "timeout")
            launched = run.call_args_list[0].args[0]
            self.assertEqual(launched[:3], ["docker", "run", "--name"])
            self.assertEqual(run.call_args_list[1].args[0], ["docker", "rm", "--force", launched[3]])

    def test_empty_frozen_test_directory_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "No frozen"):
                grade.run("image", Path(directory), Path(directory), Path(directory) / "output")

    def test_preregistered_hashes_and_required_cases(self):
        root = Path(__file__).parent
        protocol = json.loads((root / "protocol.json").read_text())
        self.assertEqual(protocol["baseline_sha"], "59a675b4b02478fd75c230263f9ef92a385f069c")
        self.assertEqual(protocol["held_out_cases"], 60)
        for name, expected in protocol["frozen_files_sha256"].items():
            self.assertEqual(hashlib.sha256((root / name).read_bytes()).hexdigest(), expected, name)


if __name__ == "__main__":
    unittest.main()
