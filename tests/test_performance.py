"""Synthetic input contracts and arithmetic only; these are not app efficacy measurements."""

import copy
import csv
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "skills/moletta/scripts"
sys.path.insert(0, str(SCRIPTS))
import performance
from model import DataError


class PerformanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.row = {"metric": "launch", "unit": "ms", "platform": "ios", "device": "lab-phone-1",
                    "device_kind": "physical", "os_version": "synthetic-os", "environment": "release; cold; quiet lab",
                    "scenario": "fixture-launch", "build_revision": "fixture-base", "collector": "fixture-exporter-v1",
                    "sample_id": "1", "value": 1}

    def samples(self, values=(1, 2, 3, 4), **changes):
        return [{**self.row, **changes, "sample_id": str(index), "value": value}
                for index, value in enumerate(values)]

    def jsonl(self, rows, name="samples.jsonl"):
        path = self.base / name
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        return path

    def summary(self, values=(1, 2, 3, 4), **changes):
        return performance.summarize(self.jsonl(self.samples(values, **changes)), "jsonl")

    def source_json(self, value, name="export.json"):
        path = self.base / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def apple(self):
        return [{"testIdentifier": "Fixture/testLaunch()", "testIdentifierURL": "test://fixture/Fixture/testLaunch()",
                 "testRuns": [{"device": {"deviceId": "synthetic-private-id", "deviceName": "Fixture phone"},
                               "testPlanConfiguration": {"configurationId": "1", "configurationName": "release"},
                               "metrics": [{"displayName": "Clock time", "identifier": "clock",
                                            "unitOfMeasurement": "s", "measurements": [1.0, 2.0, 3.0]}]}]}]

    def apple_context(self):
        return {"platform": "ios", "device_kind": "physical", "os_version": "synthetic-os",
                "environment": "release; cold", "build_revision": "fixture-base", "collector": "xcresulttool schema 0.4.0"}

    def android(self):
        return {"context": {"build": {"model": "Fixture phone", "fingerprint": "synthetic-fingerprint", "version": {"sdk": 35}},
                            "cpuLocked": True, "compilationMode": "speed"},
                "benchmarks": [{"name": "launch", "className": "FixtureBenchmark", "params": {"mode": "cold"},
                                "metrics": {"timeToInitialDisplayMs": {"runs": [2, 4, 6], "median": 999}},
                                "sampledMetrics": {}, "warmupIterations": 1, "repeatIterations": 3,
                                "thermalThrottleSleepSeconds": 0}]}

    def android_context(self):
        return {"device": "lab-phone-2", "device_kind": "physical", "environment": "release; cold",
                "build_revision": "fixture-base", "collector": "androidx-fixture-version",
                "units": {"timeToInitialDisplayMs": "ms"}}

    def test_statistics_define_interpolation_and_retain_sample_count(self):
        stats = self.summary()["groups"][0]["statistics"]
        self.assertEqual(stats["count"], 4)
        self.assertEqual(stats["mean"], 2.5)
        self.assertEqual(stats["p50"], 2.5)
        self.assertAlmostEqual(stats["p95"], 3.85)
        self.assertEqual((stats["minimum"], stats["maximum"]), (1, 4))
        self.assertEqual(self.summary((.1, .1, .1))["groups"][0]["statistics"]["mean"], .1)
        singleton = self.summary((5,))["groups"][0]["statistics"]
        self.assertEqual([singleton[key] for key in performance.STATISTICS], [5] * 5)

    def test_source_digest_binds_exact_input_without_copying_samples_or_path(self):
        source = self.jsonl(self.samples())
        before = set(self.base.iterdir())
        result = performance.summarize(source, "jsonl")
        self.assertEqual(set(self.base.iterdir()), before)
        self.assertEqual(result["source"]["sha256"], hashlib.sha256(source.read_bytes()).hexdigest())
        self.assertEqual(result["source"]["bytes"], source.stat().st_size)
        self.assertNotIn(str(source), json.dumps(result))
        self.assertNotIn("sample_id", json.dumps(result))
        self.assertNotIn('"value"', json.dumps(result))

    def test_units_and_contexts_are_separate_groups_without_implicit_conversion(self):
        rows = self.samples((1, 2)) + self.samples((.001,), unit="s") + self.samples((3,), device_kind="simulator")
        result = performance.summarize(self.jsonl(rows), "jsonl")
        self.assertEqual(len(result["groups"]), 3)
        self.assertEqual(result["sample_count"], 4)

    def test_csv_matches_jsonl_arithmetic_with_quoted_environment(self):
        rows = self.samples(environment="release, quiet lab")
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=performance.SAMPLE_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
        path = self.base / "metrics.csv"
        path.write_text(stream.getvalue(), encoding="utf-8")
        self.assertEqual(performance.summarize(path, "csv")["groups"],
                         performance.summarize(self.jsonl(rows), "jsonl")["groups"])

    def test_invalid_or_missing_samples_abort_instead_of_changing_denominator(self):
        for invalid in (None, True, "1", [], float("nan"), float("inf"), 10 ** 400):
            with self.subTest(invalid=type(invalid).__name__), self.assertRaises(DataError):
                self.summary((1, invalid, 3))
        rows = self.samples()
        del rows[1]["value"]
        with self.assertRaisesRegex(DataError, "missing fields"):
            performance.summarize(self.jsonl(rows), "jsonl")

    def test_blank_records_duplicate_ids_and_json_duplicate_keys_are_errors(self):
        path = self.jsonl(self.samples((1, 2)))
        path.write_text(path.read_text().replace("\n", "\n\n", 1))
        with self.assertRaisesRegex(DataError, "blank"):
            performance.summarize(path, "jsonl")
        with self.assertRaisesRegex(DataError, "duplicate sample_id"):
            performance.summarize(self.jsonl([self.row, self.row]), "jsonl")
        path.write_text('{"value": 1, "value": 2}')
        with self.assertRaisesRegex(DataError, "duplicate .*key"):
            performance.summarize(path, "jsonl")

    def test_limits_and_unsupported_inputs_have_bounded_explicit_failure(self):
        path = self.jsonl(self.samples())
        with mock.patch.object(performance, "MAX_BYTES", 20), self.assertRaisesRegex(DataError, "allowed size"):
            performance.summarize(path, "jsonl")
        with mock.patch.object(performance, "MAX_SAMPLES", 2), self.assertRaisesRegex(DataError, "samples"):
            performance.summarize(path, "jsonl")
        with self.assertRaisesRegex(DataError, "Unsupported measurement format"):
            performance.summarize(path, "logcat")
        with self.assertRaisesRegex(DataError, "bundle or directory"):
            performance.summarize(self.base, "xcresult-metrics-json", self.apple_context())

    def test_selected_files_and_sidecars_cannot_be_symlinks(self):
        source = self.jsonl(self.samples())
        link = self.base / "alias.jsonl"
        link.symlink_to(source)
        with self.assertRaisesRegex(DataError, "symlinks"):
            performance.summarize(link, "jsonl")
        with self.assertRaisesRegex(DataError, "symlinks"):
            performance.read_context(link)

    def test_known_credentials_are_blocked_without_echoing_input_or_secret(self):
        secret = "ghp_" + "a" * 32
        path = self.jsonl(self.samples(environment=secret), name="private-selected-file.jsonl")
        with self.assertRaisesRegex(DataError, "credential signature") as captured:
            performance.summarize(path, "jsonl")
        self.assertNotIn(secret, str(captured.exception))
        self.assertNotIn(path.name, str(captured.exception))
        path = self.jsonl(self.samples(), name=".env")
        with self.assertRaisesRegex(DataError, "credential filenames"):
            performance.summarize(path, "jsonl")
        context = self.apple_context()
        context["environment"] = secret
        with self.assertRaisesRegex(DataError, "credential signature"):
            performance.summarize(self.source_json(self.apple()), "xcresult-metrics-json", context)

    def test_comparison_allows_only_build_change_and_reports_descriptive_deltas(self):
        result = performance.compare(self.summary(), self.summary((2, 4, 6, 8), build_revision="fixture-candidate"))
        row = result["groups"][0]
        self.assertEqual(row["candidate_minus_baseline"]["mean"], {"absolute": 2.5, "percent": 100.0})
        self.assertEqual(row["baseline_build"], "fixture-base")
        self.assertEqual(row["candidate_build"], "fixture-candidate")
        self.assertNotIn("verdict", result)
        zero = performance.compare(self.summary((0,)), self.summary((5,), build_revision="fixture-candidate"))
        self.assertIsNone(zero["groups"][0]["candidate_minus_baseline"]["p95"]["percent"])

    def test_cross_context_and_partial_metric_comparisons_are_refused(self):
        baseline = self.summary()
        for field, replacement in (("device", "other-device"), ("device_kind", "simulator"), ("unit", "s"),
                                   ("os_version", "other-os"), ("environment", "debug"), ("scenario", "warm"),
                                   ("collector", "other-version"), ("metric", "cpu")):
            with self.subTest(field=field), self.assertRaisesRegex(DataError, "Comparison refused"):
                performance.compare(baseline, self.summary(**{field: replacement}))
        extra = performance.summarize(self.jsonl(self.samples() + self.samples(metric="cpu")), "jsonl")
        with self.assertRaisesRegex(DataError, "Comparison refused"):
            performance.compare(baseline, extra)

    def test_multiple_builds_and_malformed_saved_summaries_are_refused(self):
        combined = performance.summarize(self.jsonl(self.samples() + self.samples(build_revision="second")), "jsonl")
        with self.assertRaisesRegex(DataError, "one build"):
            performance.compare(combined, combined)
        saved = self.summary()
        saved["sample_count"] = 100
        with self.assertRaisesRegex(DataError, "sample_count"):
            performance.load_summary(self.source_json(saved))
        saved = self.summary()
        saved["groups"][0]["statistics"]["p95"] = 100
        with self.assertRaisesRegex(DataError, "inconsistent ranges"):
            performance.compare(saved, self.summary())

    def test_apple_import_preserves_metric_units_configuration_and_hashes_device_id(self):
        source = self.source_json(self.apple())
        result = performance.summarize(source, "xcresult-metrics-json", self.apple_context())
        row = result["groups"][0]
        self.assertEqual((row["metric"], row["unit"], row["statistics"]["count"]), ("clock", "s", 3))
        self.assertIn("test://fixture/Fixture/testLaunch()", row["scenario"])
        self.assertIn("configuration", row["scenario"])
        self.assertNotIn("synthetic-private-id", json.dumps(result))
        self.assertIn("sha256:", row["device"])
        self.assertIsNotNone(result["source"]["context_sha256"])

    def test_apple_ambiguous_targets_multiple_devices_and_missing_measurements_fail(self):
        for mutate, message in ((lambda data: data[0].pop("testIdentifierURL"), "testIdentifierURL"),
                                (lambda data: data[0]["testRuns"][0]["metrics"][0].update(measurements=[]), "nonempty")):
            data = self.apple()
            mutate(data)
            with self.assertRaisesRegex(DataError, message):
                performance.summarize(self.source_json(data), "xcresult-metrics-json", self.apple_context())
        data = self.apple()
        second = copy.deepcopy(data[0]["testRuns"][0])
        second["device"]["deviceId"] = "second-device"
        data[0]["testRuns"].append(second)
        with self.assertRaisesRegex(DataError, "multiple devices"):
            performance.summarize(self.source_json(data), "xcresult-metrics-json", self.apple_context())

    def test_android_import_uses_numeric_runs_not_vendor_summary_and_requires_units(self):
        data, context = self.android(), self.android_context()
        result = performance.summarize(self.source_json(data), "android-benchmark-json", context)
        row = result["groups"][0]
        self.assertEqual((row["platform"], row["unit"], row["statistics"]["mean"]), ("android", "ms", 4))
        self.assertIn('"mode":"cold"', row["scenario"])
        self.assertIn("synthetic-fingerprint", row["os_version"])
        context["units"] = {}
        with self.assertRaisesRegex(DataError, "explicit unit"):
            performance.summarize(self.source_json(data), "android-benchmark-json", context)

    def test_android_context_changes_are_not_hidden_from_comparison(self):
        data = self.android()
        baseline = performance.summarize(self.source_json(data), "android-benchmark-json", self.android_context())
        data["context"]["cpuLocked"] = False
        candidate = performance.summarize(self.source_json(data), "android-benchmark-json", self.android_context())
        with self.assertRaisesRegex(DataError, "Comparison refused"):
            performance.compare(baseline, candidate)

    def test_android_frame_samples_are_rejected_instead_of_flattened(self):
        data = self.android()
        data["benchmarks"][0]["sampledMetrics"] = {"frameDurationCpuMs": {"runs": [[1, 2], [3, 4]], "P95": 99}}
        with self.assertRaisesRegex(DataError, "No frame samples were flattened"):
            performance.summarize(self.source_json(data), "android-benchmark-json", self.android_context())


if __name__ == "__main__":
    unittest.main()
