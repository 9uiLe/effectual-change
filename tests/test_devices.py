"""Mechanical mobile adapter checks using disposable executable fixtures.

These tests exercise literal argv and files, not real simulator boot or app behavior.
"""

from __future__ import annotations

import fcntl
import json
import os
import shutil
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "skills/moletta/scripts"
sys.path.insert(0, str(SCRIPTS))
import devices


FAKE_TOOL = r'''
import json, os, pathlib, sys, uuid
state_path = pathlib.Path(os.environ["FAKE_DEVICE_STATE"])
state = json.loads(state_path.read_text())
tool = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
with pathlib.Path(os.environ["FAKE_DEVICE_LOG"]).open("a") as stream:
    stream.write(json.dumps({"tool": tool, "argv": args,
        "avd_home": os.environ.get("ANDROID_AVD_HOME"),
        "android_home": os.environ.get("ANDROID_HOME")}) + "\n")
def save(): state_path.write_text(json.dumps(state))
if tool == "xcrun":
    assert args[0] == "simctl"
    args = args[1:]
    if args[0] == "list":
        print(json.dumps({"runtimes": [
            {"identifier": "ios.installed", "isAvailable": True},
            {"identifier": "ios.unavailable", "isAvailable": False}],
            "devicetypes": [{"identifier": "phone.installed"}],
            "devices": {"ios.installed": state["devices"]}}))
    elif args[0] == "create":
        ident = str(uuid.uuid4()).upper()
        state["devices"].append({"udid": ident, "name": args[1], "state": "Shutdown"})
        save()
        if state.get("create_error"):
            print("fixture failed after creation", file=sys.stderr)
            sys.exit(1)
        print(ident)
    elif args[0] == "shutdown":
        assert len(args) == 2 and args[1] not in ("all", "booted")
        for item in state["devices"]:
            if item["udid"] == args[1]: item["state"] = "Shutdown"
        save()
    elif args[0] == "delete":
        assert len(args) == 2 and args[1] not in ("all", "unavailable")
        if state.get("delete_error"):
            print("fixture delete blocked", file=sys.stderr)
            sys.exit(1)
        state["devices"] = [item for item in state["devices"] if item["udid"] != args[1]]
        save()
    else:
        raise AssertionError(args)
elif tool == "avdmanager":
    if args == ["list", "device", "-c"]: print("pixel_fixture")
    else:
        assert args[:2] == ["create", "avd"]
        assert "--force" not in args and "-f" not in args
        name = args[args.index("--name") + 1]
        data = pathlib.Path(args[args.index("--path") + 1])
        data.mkdir()
        (data / "config.ini").write_text("AvdId=" + name)
        avd_home = pathlib.Path(os.environ["ANDROID_AVD_HOME"])
        (avd_home / (name + ".ini")).write_text("path=" + str(data))
        if state.get("create_error"): sys.exit(1)
elif tool == "adb":
    assert args[:1] == ["-s"] and args[2] == "emu"
    if args[3:] == ["avd", "name"]:
        print(state.get("android_name", "foreign-avd"))
        print("OK")
    elif args[3:] == ["kill"]:
        print("OK")
    else: raise AssertionError(args)
elif tool == "ps":
    assert args == ["-axww", "-o", "command="]
    print(state.get("running_command", ""))
else:
    raise AssertionError("Allocation must not boot emulator: " + tool)
'''


class DeviceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.state_dir = self.base / "host-devices"
        self.run = self.base / "worktree-one/.moletta-runs/one"
        self.other_run = self.base / "worktree-two/.moletta-runs/two"
        self.run.mkdir(parents=True)
        self.other_run.mkdir(parents=True)
        self.fake_state = self.base / "fake.json"
        self.log = self.base / "commands.jsonl"
        self.log.touch()
        self.fake_state.write_text(json.dumps({"devices": [{"udid": str(uuid.uuid4()).upper(),
             "name": "personal-phone", "state": "Booted"}]}))
        self.bin = self.base / "bin"
        self.bin.mkdir()
        self.sdk = self.base / "sdk"
        image = self.sdk / "system-images/android-32/google_apis/arm64-v8a"
        image.mkdir(parents=True)
        (image / "source.properties").write_text("Pkg.Desc=Fixture Android 32")
        (image / "system.img").write_bytes(b"shared-system-image")
        for name, path in (("xcrun", self.bin / "xcrun"), ("ps", self.bin / "ps"),
                           ("avdmanager", self.sdk / "cmdline-tools/latest/bin/avdmanager"),
                           ("emulator", self.sdk / "emulator/emulator"),
                           ("adb", self.sdk / "platform-tools/adb")):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"#!{sys.executable}\n" + FAKE_TOOL)
            path.chmod(0o700)
        environment = mock.patch.dict(os.environ, {"PATH": str(self.bin),
            "FAKE_DEVICE_STATE": str(self.fake_state), "FAKE_DEVICE_LOG": str(self.log)})
        environment.start()
        self.addCleanup(environment.stop)
        # The sandbox can prohibit binding even an unused localhost port.
        # Model port occupancy; executable adapters still run as subprocesses.
        ports = mock.patch.object(devices, "_ports_free", return_value=True)
        ports.start()
        self.addCleanup(ports.stop)

    def commands(self, tool=None):
        values = [json.loads(line) for line in self.log.read_text().splitlines()]
        return [item for item in values if tool is None or item["tool"] == tool]

    def fixture(self, **changes):
        value = json.loads(self.fake_state.read_text())
        value.update(changes)
        self.fake_state.write_text(json.dumps(value))
        return value

    def allocate(self, platform="ios", run=None):
        return devices.allocate(run or self.run, platform,
             runtime="ios.installed" if platform == "ios" else "system-images;android-32;google_apis;arm64-v8a",
             device_type="phone.installed" if platform == "ios" else "pixel_fixture",
             state_dir=self.state_dir, sdk=self.sdk)

    def release(self, lease, run=None):
        return devices.release(run or self.run, lease["lease_id"], state_dir=self.state_dir)

    def test_inspection_only_lists_installed_available_profiles_without_allocating(self):
        ios = devices.inspect("ios")
        self.assertEqual([item["identifier"] for item in ios["runtimes"]], ["ios.installed"])
        android = devices.inspect("android", sdk=self.sdk)
        self.assertEqual(android["runtimes"][0]["identifier"], "system-images;android-32;google_apis;arm64-v8a")
        self.assertFalse(self.state_dir.exists())
        self.assertFalse((self.run / "devices").exists())

    def test_missing_runtime_never_downloads_or_creates_device(self):
        with self.assertRaisesRegex(devices.DeviceError, "no download attempted"):
            devices.allocate(self.run, "ios", runtime="missing", device_type="phone.installed",
                             state_dir=self.state_dir)
        self.assertFalse(self.state_dir.exists())
        self.assertTrue(all(item["argv"][1] == "list" for item in self.commands("xcrun")))

    def test_two_worktrees_share_runtime_but_release_only_their_own_simulator(self):
        first, second = self.allocate(), self.allocate(run=self.other_run)
        self.assertNotEqual(first["destination"], second["destination"])
        self.assertEqual(first["runtime"], second["runtime"])
        self.assertEqual(first["launch_argv"][-2:], ["boot", first["device_id"]])
        self.assertNotIn("boot", [item["argv"][1] for item in self.commands("xcrun")])
        state = self.fixture()
        for item in state["devices"]:
            if item["udid"] == first["device_id"]: item["state"] = "Booted"
        self.fixture(devices=state["devices"])
        self.assertEqual(self.release(first)["state"], "released")
        remaining = self.fixture()["devices"]
        self.assertEqual({item["name"] for item in remaining}, {"personal-phone", second["name"]})
        lifecycle = [item["argv"] for item in self.commands("xcrun") if item["argv"][1] in ("shutdown", "delete")]
        self.assertEqual(lifecycle, [["simctl", "shutdown", first["device_id"]],
                                     ["simctl", "delete", first["device_id"]]])
        self.assertEqual(devices.pending(self.run), [])
        self.assertEqual(len(devices.pending(self.other_run)), 1)
        self.release(first)
        self.assertEqual(len([item for item in self.commands("xcrun") if item["argv"][1] == "delete"]), 1)

    def test_owner_mismatch_cannot_release_a_different_run_lease(self):
        lease = self.allocate()
        receipt = dict(lease, run=str(self.other_run))
        (self.other_run / "devices").mkdir()
        (self.other_run / "devices" / f"{lease['lease_id']}.json").write_text(json.dumps(receipt))
        with self.assertRaisesRegex(devices.DeviceError, "does not own"):
            self.release(lease, run=self.other_run)
        self.assertFalse(any(item["argv"][1] == "delete" for item in self.commands("xcrun")))

    def test_failed_create_discovers_its_own_partial_device_and_rolls_back(self):
        self.fixture(create_error=True)
        with self.assertRaisesRegex(devices.DeviceError, "is released"):
            self.allocate()
        self.assertEqual([item["name"] for item in self.fixture()["devices"]], ["personal-phone"])
        self.assertEqual(devices.pending(self.run), [])
        self.assertEqual(list((self.state_dir / "resources").iterdir()), [])

    def test_failed_release_remains_pending_until_a_successful_retry(self):
        lease = self.allocate()
        self.fixture(delete_error=True)
        with self.assertRaisesRegex(devices.DeviceError, "cleanup_pending"):
            self.release(lease)
        self.assertEqual(devices.pending(self.run)[0]["state"], "cleanup_pending")
        self.fixture(delete_error=False)
        self.assertEqual(self.release(lease)["state"], "released")
        self.assertEqual(devices.pending(self.run), [])

    def test_failed_create_with_failed_cleanup_is_recoverable_and_gc_is_explicit(self):
        self.fixture(create_error=True, delete_error=True)
        with self.assertRaisesRegex(devices.DeviceError, "cleanup_pending"):
            self.allocate()
        pending = devices.pending(self.run)[0]
        self.fixture(delete_error=False)
        preview = devices.gc(state_dir=self.state_dir, older_than_hours=0)
        self.assertEqual(preview["candidates"][0]["lease_id"], pending["lease_id"])
        self.assertEqual(len(self.fixture()["devices"]), 2)
        applied = devices.gc(state_dir=self.state_dir, older_than_hours=0, apply=True)
        self.assertEqual(applied["candidates"][0]["state"], "released")
        self.assertEqual(len(self.fixture()["devices"]), 1)

    def test_gc_never_expires_an_intact_run_based_on_age_alone(self):
        lease = self.allocate()
        self.assertEqual(devices.gc(state_dir=self.state_dir, older_than_hours=0, apply=True)["candidates"], [])
        receipt = self.run / "devices" / f"{lease['lease_id']}.json"
        receipt.unlink()
        preview = devices.gc(state_dir=self.state_dir, older_than_hours=0)
        self.assertEqual(preview["candidates"][0]["reason"], "missing_run_receipt")
        self.assertEqual(len(self.fixture()["devices"]), 2)
        devices.gc(state_dir=self.state_dir, older_than_hours=0, apply=True)
        self.assertEqual(len(self.fixture()["devices"]), 1)
        self.assertFalse(receipt.exists())

    def test_android_uses_shared_image_and_isolated_data_and_reserved_ports(self):
        first, second = self.allocate("android"), self.allocate("android", run=self.other_run)
        self.assertNotEqual(first["port"], second["port"])
        self.assertNotEqual(first["launch_env"]["ANDROID_AVD_HOME"], second["launch_env"]["ANDROID_AVD_HOME"])
        self.assertEqual(first["launch_env"]["ANDROID_HOME"], second["launch_env"]["ANDROID_HOME"])
        self.assertIn("-no-snapshot", first["launch_argv"])
        self.assertEqual(first["launch_argv"][first["launch_argv"].index("-port") + 1], str(first["port"]))
        creates = [item for item in self.commands("avdmanager") if item["argv"][:2] == ["create", "avd"]]
        self.assertEqual(len(creates), 2)
        self.assertTrue(all("--package" in item["argv"] and "--path" in item["argv"] for item in creates))
        self.assertEqual(list((self.state_dir / "resources").rglob("system.img")), [])
        self.assertFalse(self.commands("emulator"))
        self.release(first)
        self.assertTrue((self.state_dir / "resources" / second["lease_id"]).is_dir())

    def test_failed_android_create_removes_only_owned_partial_avd_data(self):
        self.fixture(create_error=True)
        with self.assertRaisesRegex(devices.DeviceError, "is released"):
            self.allocate("android")
        self.assertEqual(list((self.state_dir / "resources").iterdir()), [])
        self.assertEqual(devices.pending(self.run), [])
        self.assertEqual((self.sdk / "system-images/android-32/google_apis/arm64-v8a/system.img").read_bytes(),
                         b"shared-system-image")

    def test_android_refuses_recycled_foreign_serial_then_targets_owned_avd(self):
        lease = self.allocate("android")
        with mock.patch.object(devices, "_ports_free", return_value=False):
            with self.assertRaisesRegex(devices.DeviceError, "different AVD"):
                self.release(lease)
        self.assertFalse(any(item["argv"][-1] == "kill" for item in self.commands("adb")))
        self.assertTrue((self.state_dir / "resources" / lease["lease_id"]).is_dir())
        self.fixture(android_name=lease["name"])
        with mock.patch.object(devices, "_ports_free", side_effect=[False, True]):
            self.release(lease)
        self.assertEqual(self.commands("adb")[-1]["argv"], ["-s", lease["destination"], "emu", "kill"])
        self.assertFalse((self.state_dir / "resources" / lease["lease_id"]).exists())

    def test_starting_android_process_blocks_data_deletion_until_stopped(self):
        lease = self.allocate("android")
        self.fixture(running_command=f"emulator -avd {lease['name']}")
        with self.assertRaisesRegex(devices.DeviceError, "starting or uses another port"):
            self.release(lease)
        self.assertTrue((self.state_dir / "resources" / lease["lease_id"]).is_dir())
        self.fixture(running_command="")
        self.release(lease)

    def test_host_allocator_lock_serializes_different_worktrees(self):
        self.allocate()
        with (self.state_dir / ".lock").open("a+b") as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(devices.DeviceError, "Host device allocator is busy"):
                self.allocate(run=self.other_run)
        self.assertFalse((self.other_run / "devices").exists())

    def test_private_registry_receipts_and_locks_ignore_permissive_umask(self):
        previous = os.umask(0)
        try:
            lease = self.allocate()
        finally:
            os.umask(previous)
        for directory in (self.state_dir, self.state_dir / "leases", self.state_dir / "resources",
                          self.state_dir / "resources" / lease["lease_id"], self.run / "devices"):
            self.assertEqual(directory.stat().st_mode & 0o777, 0o700)
        for path in (self.state_dir / ".lock", self.state_dir / "leases" / f"{lease['lease_id']}.json",
                     self.run / "devices" / f"{lease['lease_id']}.json"):
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_reserved_and_busy_port_pairs_are_not_assigned_again(self):
        with mock.patch.object(devices, "_ports_free", side_effect=[False, True]):
            first = self.allocate("android")
        self.assertEqual(first["port"], 5556)
        second = self.allocate("android", run=self.other_run)
        self.assertNotEqual(second["port"], first["port"])
        with mock.patch.object(devices, "_ports_free", return_value=False):
            with self.assertRaisesRegex(devices.DeviceError, "No free emulator"):
                self.allocate("android")

    def test_resource_symlink_is_refused_before_any_device_deletion(self):
        lease = self.allocate()
        resource = self.state_dir / "resources" / lease["lease_id"]
        resource.rename(resource.with_name("preserved"))
        outside = self.base / "personal-data"
        outside.mkdir()
        (outside / "keep.txt").write_text("keep")
        resource.symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(devices.DeviceError, "must not be a symlink"):
            self.release(lease)
        self.assertEqual((outside / "keep.txt").read_text(), "keep")
        self.assertFalse(any(item["argv"][1] == "delete" for item in self.commands("xcrun")))

    def test_tampered_identifier_cannot_become_a_global_simctl_selector(self):
        lease = self.allocate()
        record = self.state_dir / "leases" / f"{lease['lease_id']}.json"
        value = json.loads(record.read_text())
        value["device_id"] = "all"
        record.write_text(json.dumps(value))
        with self.assertRaisesRegex(devices.DeviceError, "Invalid owned simulator identifier"):
            self.release(lease)
        self.assertFalse(any(item["argv"][1] == "delete" for item in self.commands("xcrun")))

    def test_missing_android_tools_are_capability_diagnostics_without_download(self):
        shutil.rmtree(self.sdk / "cmdline-tools")
        inventory = devices.inspect("android", sdk=self.sdk)
        self.assertIn("Required Android tool unavailable: avdmanager", inventory["diagnostics"])
        with self.assertRaisesRegex(devices.DeviceError, "avdmanager"):
            self.allocate("android")
        self.assertFalse(self.state_dir.exists())


if __name__ == "__main__":
    unittest.main()
