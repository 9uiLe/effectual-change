"""Fast tests for the A/B controller; no Codex, Docker, GitHub, or network needed."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("phase2_plugin_runner", HERE / "run.py")
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class FakeCodex:
    returncode = 0

    def __init__(self, command, **kwargs):
        self.command = command
        self.env = kwargs["env"]
        self.out = kwargs["stdout"]
        self.out.write(
            (json.dumps({"type": "turn.completed", "usage": {
                "input_tokens": 100, "cached_input_tokens": 20, "output_tokens": 10
            }}) + "\n").encode("utf-8")
        )

    def communicate(self, input=None, timeout=None):
        self.prompt = input
        return None, None


class RunnerTests(unittest.TestCase):
    def test_control_treatment_are_separate_and_same_codex_options(self):
        calls = []
        def fake_popen(cmd, **kwargs):
            p = FakeCodex(cmd, **kwargs)
            calls.append(p)
            return p

        def fake_run(cmd, **kwargs):
            if "rev-parse" in cmd:
                return subprocess.CompletedProcess(cmd, 0, stdout=runner.BASE + "\n")
            return subprocess.CompletedProcess(cmd, 0, stdout="")

        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            private_home = base / "auth"
            private_home.mkdir()
            # run_trial is given two distinct source paths; it doesn't depend
            # on a Git checkout while external commands are mocked.
            with patch.object(runner.subprocess, "Popen", side_effect=fake_popen), \
                 patch.object(runner.subprocess, "run", side_effect=fake_run):
                control = runner.trial("control", base / "control", base,
                                       private_home, "test-model", 60)
                treatment = runner.trial("treatment", base / "treatment", base,
                                         private_home, "test-model", 60)
            self.assertTrue(control["base_preserved"])
            self.assertTrue(treatment["base_preserved"])
            self.assertTrue(control["completed"] and treatment["completed"])
            self.assertEqual(control["tokens"]["input_tokens"], 100)
            self.assertEqual(len(calls), 2)
            self.assertNotEqual(calls[0].env["HOME"], calls[1].env["HOME"])
            self.assertEqual(calls[0].env["CODEX_HOME"], calls[1].env["CODEX_HOME"])
            self.assertEqual(calls[0].command, [
                "codex", "--ask-for-approval", "never", "exec",
                "--ignore-user-config", "--json", "--ephemeral",
                "--sandbox", "workspace-write",
                "-c", "sandbox_workspace_write.network_access=false",
                "-c", 'shell_environment_policy.inherit="core"',
                "-C", str(base / "control"), "--model", "test-model", "-"
            ])
            self.assertNotIn("$effectual-change", calls[0].prompt.decode())
            self.assertIn("$effectual-change", calls[1].prompt.decode())
            self.assertIn(runner.TASK, calls[0].prompt.decode())
            self.assertIn(runner.TASK, calls[1].prompt.decode())
            self.assertFalse(control["timed_out"])
            self.assertFalse(treatment["timed_out"])

    def test_markdown_summary_does_not_contain_raw_logs(self):
        sample = {
            "model": "test-model",
            "trials": {
                side: {
                    "return_code": 0, "seconds": 12.0,
                    "tokens": {"input_tokens": 123},
                    "grade": {"passed": 8, "total": 8},
                    "skill_read_command_observed": True if side == "treatment" else None,
                    "artifacts": "/private/secret-path",
                } for side in ("control", "treatment")
            }
        }
        rendered = runner.markdown(sample)
        self.assertIn("| control | 8/8 |", rendered)
        self.assertIn("| treatment | 8/8 |", rendered)
        self.assertNotIn("/private/secret-path", rendered)


if __name__ == "__main__":
    unittest.main()
