"""Offline tests for the Codex A/B runner, including repeatability and trial order."""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
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
        self.out.write((json.dumps({"type": "thread.started", "model": "test-model"}) +
                        "\n").encode("utf-8"))
        if kwargs["cwd"].name == "treatment":
            self.out.write((json.dumps({
                "type": "item.completed",
                "item": {
                    "type": "command_execution",
                    "command": "cat .agents/skills/effectual-change/SKILL.md",
                    "status": "completed", "exit_code": 0,
                }
            }) + "\n").encode("utf-8"))
        self.out.write((json.dumps({"type": "turn.completed", "usage": {
            "input_tokens": 100, "cached_input_tokens": 20, "output_tokens": 10
        }}) + "\n").encode("utf-8"))

    def communicate(self, input=None, timeout=None):
        self.prompt = input
        return None, None


class RunnerTests(unittest.TestCase):
    def test_only_matching_skills_conflict(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "codex-home"
            unrelated = home / "skills/.system/skill-creator/SKILL.md"
            unrelated.parent.mkdir(parents=True)
            unrelated.write_text("---\nname: skill-creator\n---\n")
            self.assertEqual(runner.conflicting_skills(home), [])
            # Simulate Codex copying a new unrelated skill between runs.
            second = home / "plugins/other-skill/SKILL.md"
            second.parent.mkdir(parents=True)
            second.write_text("---\nname: other-skill\n---\n")
            self.assertEqual(runner.conflicting_skills(home), [])
            canonical = home / "skills/effectual-change/SKILL.md"
            canonical.parent.mkdir(parents=True)
            canonical.write_text("---\nname: effectual-change\n---\n")
            self.assertEqual(runner.conflicting_skills(home), [canonical])
            canonical.unlink()
            renamed = home / "plugins/custom/SKILL.md"
            renamed.parent.mkdir(parents=True)
            renamed.write_text('---\nname: "effectual-change"\n---\n')
            self.assertEqual(runner.conflicting_skills(home), [renamed])

    def test_repeated_preflight_allows_unrelated_codex_skills(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            unrelated = state / "codex-home/skills/.system/skill-creator/SKILL.md"
            unrelated.parent.mkdir(parents=True)
            unrelated.write_text("---\nname: skill-creator\n---\n")
            login_success = subprocess.CompletedProcess(["codex", "login", "status"], 0)
            with patch.object(runner.shutil, "which", return_value="/usr/bin/fake"), \
                 patch.object(runner, "run"), \
                 patch.object(runner.subprocess, "run", return_value=login_success):
                self.assertEqual(runner.auth_check(state), state / "codex-home")
                self.assertEqual(runner.auth_check(state), state / "codex-home")

    def test_order_flags_and_random_selection(self):
        self.assertEqual(runner.trial_order("control-first"),
                         ("control", "treatment"))
        self.assertEqual(runner.trial_order("treatment-first"),
                         ("treatment", "control"))
        with patch.object(runner.secrets, "randbelow", return_value=0):
            self.assertEqual(runner.trial_order("random"),
                             ("control", "treatment"))
        with patch.object(runner.secrets, "randbelow", return_value=1):
            self.assertEqual(runner.trial_order("random"),
                             ("treatment", "control"))
        with self.assertRaises(ValueError):
            runner.trial_order("invalid")

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
            private_home = base / "codex-home"
            private_home.mkdir()
            treatment_skill = base / "treatment/.agents/skills/effectual-change/SKILL.md"
            treatment_skill.parent.mkdir(parents=True)
            treatment_skill.write_text("---\nname: effectual-change\n---\n")

            with patch.object(runner.subprocess, "Popen", side_effect=fake_popen), \
                 patch.object(runner.subprocess, "run", side_effect=fake_run):
                control = runner.trial("control", base / "control", base,
                                       private_home, "test-model", 60)
                treatment = runner.trial("treatment", base / "treatment", base,
                                         private_home, "test-model", 60)

            self.assertTrue(control["base_preserved"] and treatment["base_preserved"])
            self.assertTrue(control["completed"] and treatment["completed"])
            self.assertEqual(control["tokens"]["input_tokens"], 100)
            self.assertEqual(control["resolved_model_in_events"], "test-model")
            self.assertEqual(treatment["resolved_model_in_events"], "test-model")
            self.assertFalse(control["skill_read_command_observed"])
            self.assertFalse(control["skill_read_command_attempted"])
            self.assertTrue(treatment["skill_read_command_observed"])
            self.assertTrue(treatment["skill_read_command_attempted"])
            self.assertFalse(control["project_skill_present"])
            self.assertTrue(treatment["project_skill_present"])
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
            self.assertFalse(control["timed_out"] or treatment["timed_out"])

    def test_refuse_incorrect_skill_exposure(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            skill_file = home / "control/.agents/skills/effectual-change/SKILL.md"
            skill_file.parent.mkdir(parents=True)
            skill_file.write_text("---\nname: effectual-change\n---\n")
            with self.assertRaisesRegex(RuntimeError, "unexpected project Skill exposure"):
                runner.trial("control", home / "control", home, home / "auth",
                             None, 30)
            with self.assertRaisesRegex(RuntimeError, "unexpected project Skill exposure"):
                runner.trial("treatment", home / "treatment", home, home / "auth",
                             None, 30)

    @staticmethod
    def sample_report() -> dict:
        return {
            "model": "test-model",
            "order_requested": "treatment-first",
            "execution_order": ["treatment", "control"],
            "trials": {
                side: {
                    "return_code": 0, "seconds": 12.0,
                    "tokens": {"input_tokens": 123},
                    "grade": {"passed": 8, "total": 8},
                    "project_skill_present": side == "treatment",
                    "skill_read_command_observed": side == "treatment",
                    "skill_read_command_attempted": side == "treatment",
                    "resolved_model_in_events": None,
                    "artifacts": "/private/secret-path",
                } for side in ("control", "treatment")
            }
        }

    def test_markdown_summary_includes_order_and_uncertainty_not_paths(self):
        sample = self.sample_report()
        rendered = runner.markdown(sample)
        self.assertIn("Execution order: treatment -> control", rendered)
        self.assertIn("not reported consistently in JSONL (unverified)", rendered)
        self.assertIn("| control | 8/8 |", rendered)
        self.assertIn("| treatment | 8/8 |", rendered)
        self.assertNotIn("/private/secret-path", rendered)
        self.assertTrue(runner.exposure_evidence(sample))
        sample["trials"]["control"]["skill_read_command_observed"] = True
        self.assertFalse(runner.exposure_evidence(sample))
        sample["trials"]["control"]["skill_read_command_observed"] = False
        sample["trials"]["control"]["skill_read_command_attempted"] = True
        self.assertFalse(runner.exposure_evidence(sample))
        sample["trials"]["control"]["skill_read_command_attempted"] = False
        sample["trials"]["treatment"]["skill_read_command_observed"] = False
        self.assertFalse(runner.exposure_evidence(sample))

    def test_read_evidence_needs_a_completed_command(self):
        item = {"type": "command_execution",
                "command": "cat .agents/skills/effectual-change/SKILL.md"}
        self.assertEqual(
            runner.skill_command_evidence([{"type": "item.started", "item": item}]),
            (True, False),
        )
        self.assertEqual(
            runner.skill_command_evidence([
                {"type": "item.completed", "item": {**item, "exit_code": 1}}
            ]),
            (True, False),
        )
        self.assertEqual(
            runner.skill_command_evidence([
                {"type": "item.completed", "item": {**item, "exit_code": 0}}
            ]),
            (True, True),
        )
        self.assertEqual(
            runner.skill_command_evidence([
                {"type": "item.completed", "item": {**item, "status": "completed"}}
            ]),
            (True, True),
        )
        self.assertEqual(
            runner.skill_command_evidence([
                {"type": "item.completed", "item": {
                    **item, "command": "cat unrelated/SKILL.md", "exit_code": 0
                }}
            ]),
            (False, False),
        )

    def test_main_obeys_selected_order(self):
        calls = []

        def fake_trial(side, *_args):
            calls.append(side)
            return {
                "condition": side, "return_code": 0, "completed": True,
                "timed_out": False, "base_preserved": True, "stream_errors": False,
                "seconds": 1.0, "tokens": {"input_tokens": 1},
                "project_skill_present": side == "treatment",
                "skill_read_command_observed": side == "treatment",
                "skill_read_command_attempted": side == "treatment",
                "resolved_model_in_events": None,
            }

        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            with patch.object(sys, "argv", [
                "run.py", "--skip-grade", "--state-dir", str(state),
                "--order", "treatment-first", "--model", "test-model"
            ]), patch.object(runner, "auth_check", return_value=state / "auth"), \
                 patch.object(runner, "checkouts", return_value={
                    "control": state / "control", "treatment": state / "treatment"
                 }), patch.object(runner, "trial", side_effect=fake_trial):
                self.assertEqual(runner.main(), 0)
            self.assertEqual(calls, ["treatment", "control"])
            reports = list(state.glob("runs/*/report.json"))
            self.assertEqual(len(reports), 1)
            self.assertEqual(json.loads(reports[0].read_text())["execution_order"],
                             ["treatment", "control"])


if __name__ == "__main__":
    unittest.main()
