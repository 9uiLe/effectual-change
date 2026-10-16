"""Offline runner tests; these do not execute independent Agent trials."""

import importlib.util
import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("scope_grade", Path(__file__).with_name("grade.py"))
GRADE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GRADE)


class ScopeGraderTests(unittest.TestCase):
    def test_dispatch_hashes_match_frozen_files(self):
        root = Path(__file__).parent
        protocol = json.loads((root / "protocol.json").read_text())
        for name in ("grade.py", "grade.mjs", "common-prompt.txt", "control-prompt.txt", "treatment-prompt.txt"):
            with self.subTest(name=name):
                self.assertEqual(hashlib.sha256((root / name).read_bytes()).hexdigest(), protocol["hashes"][name])

    def test_sandbox_has_no_network_credentials_or_writeable_candidate(self):
        args = GRADE.command("sha256:local", Path("/candidate-source"), Path("/frozen"))
        self.assertIn("none", args)
        self.assertIn("--read-only", args)
        self.assertIn("65534:65534", args)
        self.assertIn("no-new-privileges", args)
        for option, value in (("--network", "none"), ("--user", "65534:65534"),
                              ("--cap-drop", "ALL"), ("--memory", "256m"),
                              ("--pids-limit", "64"), ("--cpus", "1")):
            self.assertEqual(args[args.index(option) + 1], value)
        self.assertIn("type=bind,src=/candidate-source,dst=/candidate,readonly", args)
        self.assertIn("type=bind,src=/frozen,dst=/candidate/tests,readonly", args)
        self.assertEqual(args[-2:], ["sha256:local", "node"])
        self.assertEqual(args[args.index("--env") + 1], "HOME=/tmp")

    def test_runs_held_out_and_frozen_tests_separately(self):
        with tempfile.TemporaryDirectory() as directory:
            frozen = Path(directory)
            (frozen / "original.test.mjs").touch()
            outputs = [
                subprocess.CompletedProcess([], 1, json.dumps({"passed": 0, "total": 43}), ""),
                subprocess.CompletedProcess([], 0, "frozen tests passed", ""),
            ]
            with patch.object(GRADE.subprocess, "run", side_effect=outputs) as run:
                result = GRADE.run("sha256:local", Path("/candidate"), frozen)
            self.assertEqual(result["held_out"]["exit_code"], 1)
            self.assertEqual(result["frozen_regression"]["exit_code"], 0)
            self.assertEqual(run.call_args_list[0].args[0][-1], "/grader/grade.mjs")
            self.assertEqual(run.call_args_list[1].args[0][-2:], ["--test", "/candidate/tests/original.test.mjs"])
            self.assertEqual(run.call_args_list[0].kwargs["timeout"], 90)

    def test_missing_frozen_tests_are_not_a_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(GRADE.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "{}", "")):
                with self.assertRaisesRegex(ValueError, "No frozen baseline tests"):
                    GRADE.run("sha256:local", Path("/candidate"), Path(directory))

    def test_invalid_grader_output_is_not_a_pass(self):
        with patch.object(GRADE.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "not json", "")):
            with self.assertRaises(json.JSONDecodeError):
                GRADE.run("sha256:local", Path("/candidate"), Path("/frozen"))


if __name__ == "__main__":
    unittest.main()
