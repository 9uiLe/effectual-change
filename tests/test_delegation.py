"""Approval scope and budget tests use fictional host models, not model quality."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/moletta/scripts"))
import delegation
from model import DataError
import store


class DelegationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.run = self.base / "run"
        brief = self.base / "brief.md"
        brief.write_text("Implement and observe a fictional setting change.")
        store.initialize(self.run, brief, "Observe a saved setting")
        self.approval = {"schema_version": 1, "host": "codex", "mode": "adaptive",
                         "approval_reference": "fictional user approval in test fixture",
                         "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
                         "max_parallel": 2, "max_total_tokens": 1000,
                         "choices": [{"role": "execution", "model": "host-small", "effort": "medium"},
                                     {"role": "judgment", "model": "host-large", "effort": "high"}]}
        self.catalog = {"schema_version": 1, "host": "codex",
                        "observed_at": datetime.now(timezone.utc).isoformat(),
                        "source": "fictional host capability fixture",
                        "models": [{"id": "host-small", "efforts": ["low", "medium"]},
                                   {"id": "host-large", "efforts": ["medium", "high"]}]}

    def request(self, task="T1", tokens=400):
        return {"task_id": task, "role": "execution", "model": "host-small", "effort": "medium",
                "max_tokens": tokens, "max_seconds": 60, "context_sha256": "a" * 64}

    def configure(self):
        delegation.configure(self.run, self.approval)

    def finish(self, job, tokens=None, cost=None):
        return delegation.complete(self.run, job["assignment"]["id"],
                                   {"total_tokens": tokens, "cost_usd": cost, "source": "host usage fixture"})

    def test_no_approval_does_not_enable_model_changes(self):
        self.assertEqual(delegation.status(self.run)["mode"], "disabled")
        with self.assertRaisesRegex(DataError, "approval"):
            delegation.reserve(self.run, self.request(), self.catalog)
        self.assertEqual(delegation.status(self.run)["mode"], "disabled")

    def test_scope_checks_role_model_effort_host_and_availability(self):
        self.configure()
        for change in ({"role": "judgment"}, {"model": "unavailable"}, {"effort": "ultra"}):
            with self.subTest(change=change), self.assertRaises(DataError):
                delegation.reserve(self.run, {**self.request(), **change}, self.catalog)
        catalog = {**self.catalog, "host": "claude"}
        with self.assertRaisesRegex(DataError, "different host"):
            delegation.reserve(self.run, self.request(), catalog)
        value = delegation.reserve(self.run, self.request(), self.catalog)
        self.assertFalse(value["spawn_performed"])
        self.assertEqual(value["assignment"]["effort"], "medium")

    def test_reserved_capacity_and_parallelism_are_shared(self):
        self.configure()
        first = delegation.reserve(self.run, self.request(), self.catalog)
        delegation.reserve(self.run, self.request("T2"), self.catalog)
        with self.assertRaisesRegex(DataError, "parallelism"):
            delegation.reserve(self.run, self.request("T3", 1), self.catalog)
        self.finish(first, 390)
        with self.assertRaisesRegex(DataError, "budget"):
            delegation.reserve(self.run, self.request("T3", 211), self.catalog)
        delegation.reserve(self.run, self.request("T3", 210), self.catalog)

    def test_unknown_usage_is_not_zero_and_completion_is_once(self):
        self.configure()
        job = delegation.reserve(self.run, self.request(), self.catalog)
        report = self.finish(job)["status"]
        self.assertEqual(report["charged_or_reserved_tokens"], 400)
        self.assertIsNone(report["cost_usd"])
        with self.assertRaises(DataError):
            self.finish(job, 0, 0)
        with self.assertRaisesRegex(DataError, "already assigned"):
            delegation.reserve(self.run, self.request(), self.catalog)

    def test_reported_overrun_blocks_further_reservation(self):
        self.configure()
        job = delegation.reserve(self.run, self.request(), self.catalog)
        report = self.finish(job, 1001)["status"]
        self.assertTrue(report["budget_exceeded"])
        self.assertFalse(report["limits_enforced_by_host"])
        with self.assertRaisesRegex(DataError, "budget"):
            delegation.reserve(self.run, self.request("T2", 1), self.catalog)

    def test_policy_refresh_does_not_reset_spending(self):
        self.configure()
        job = delegation.reserve(self.run, self.request(), self.catalog)
        self.finish(job, 800, .05)
        delegation.configure(self.run, self.approval)
        self.assertEqual(delegation.status(self.run)["charged_or_reserved_tokens"], 800)
        with self.assertRaises(DataError):
            delegation.reserve(self.run, self.request("T2", 201), self.catalog)

    def test_stale_catalog_and_expired_consent_require_refresh(self):
        self.configure()
        catalog = {**self.catalog, "observed_at": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()}
        with self.assertRaisesRegex(DataError, "Refresh"):
            delegation.reserve(self.run, self.request(), catalog)
        expired = {**self.approval, "expires_at": (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()}
        with self.assertRaisesRegex(DataError, "expired"):
            delegation.configure(self.run, expired)

    def test_fixed_mode_does_not_permit_multiple_choices_for_one_role(self):
        approval = deepcopy(self.approval)
        approval["mode"] = "fixed"
        approval["choices"].append({"role": "execution", "model": "host-large", "effort": "medium"})
        with self.assertRaisesRegex(DataError, "Fixed"):
            delegation.configure(self.run, approval)

    def test_host_native_effort_requires_both_current_catalog_and_approval(self):
        effort = "host-adaptive-v2"
        self.approval["choices"][0]["effort"] = effort
        self.catalog["models"][0]["efforts"] = [effort]
        self.configure()
        request = {**self.request(), "effort": effort}
        job = delegation.reserve(self.run, request, self.catalog)
        self.assertEqual(job["assignment"]["effort"], effort)
        for invalid in ("", 1, []):
            with self.subTest(invalid=invalid), self.assertRaises(DataError):
                delegation.reserve(self.run, {**self.request("T2"), "effort": invalid}, self.catalog)

    def test_receipt_identifiers_are_strings_and_symlinked_state_is_not_read(self):
        self.configure()
        for change in ({"task_id": 123}, {"context_sha256": int("1" * 64)}):
            with self.subTest(change=change), self.assertRaises(DataError):
                delegation.reserve(self.run, {**self.request(), **change}, self.catalog)
        directory = self.run / "delegation"
        moved = self.base / "other"
        directory.rename(moved)
        directory.symlink_to(moved, target_is_directory=True)
        with self.assertRaises(DataError):
            delegation.status(self.run)
        directory.unlink()
        moved.rename(directory)
        policy = directory / "policy.json"
        elsewhere = self.base / "elsewhere.json"
        policy.rename(elsewhere)
        policy.symlink_to(elsewhere)
        with self.assertRaises(DataError):
            delegation.status(self.run)

    def test_reported_usage_cannot_store_known_secret_values(self):
        self.configure()
        job = delegation.reserve(self.run, self.request(), self.catalog)
        token = "ghp_" + "A" * 40
        with self.assertRaises(DataError) as caught:
            delegation.complete(self.run, job["assignment"]["id"],
                                {"total_tokens": 10, "cost_usd": None, "source": token})
        self.assertNotIn(token, str(caught.exception))
        self.assertNotIn(token, (self.run / "delegation/assignments.json").read_text())


if __name__ == "__main__":
    unittest.main()
