"""Run public CLI checks, frozen regressions, quality gates and native checks offline."""

import argparse
import json
import os
import re
import subprocess
import uuid
from pathlib import Path


def command(image: str, candidate: Path, baseline: Path, work: Path, memory="512m") -> list[str]:
    return [
        "docker", "run", "--rm", "--network", "none", "--read-only",
        "--user", "65534:65534", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
        "--pids-limit", "256", "--memory", memory, "--memory-swap", memory, "--cpus", "2",
        "--tmpfs", "/tmp:rw,exec,nosuid,size=64m,mode=1777", "--workdir", "/candidate",
        "--env", "HOME=/work/home", "--env", "TMPDIR=/work",
        "--env", "GIT_CONFIG_COUNT=1", "--env", "GIT_CONFIG_KEY_0=safe.directory", "--env", "GIT_CONFIG_VALUE_0=/candidate",
        "--mount", f"type=bind,src={candidate},dst=/candidate,readonly",
        "--mount", f"type=bind,src={baseline},dst=/oracle,readonly",
        "--mount", f"type=bind,src={baseline / 'node_modules'},dst=/candidate/node_modules,readonly",
        "--mount", f"type=bind,src={Path(__file__).parent.resolve()},dst=/grader,readonly",
        "--mount", f"type=bind,src={work},dst=/work",
        image,
    ]


def summarize(completed: subprocess.CompletedProcess) -> dict:
    output = completed.stdout + completed.stderr
    counts = re.findall(r"\b(\d+) (pass|fail)\b", output)
    failures = re.findall(r"\(fail\) ([^\n]+)", output)
    return {"exit_code": completed.returncode,
            "passed": sum(int(n) for n, kind in counts if kind == "pass"),
            "failed": sum(int(n) for n, kind in counts if kind == "fail"),
            "failed_checks": list(dict.fromkeys(re.sub(r"\s+\[.*", "", s).strip() for s in failures))}


def passed(stage: dict, minimum: int = 0) -> bool:
    return stage.get("exit_code") == 0 and stage.get("passed", 0) >= minimum and stage.get("failed", 0) == 0


def invoke(args: list[str], log: Path, timeout: int = 180) -> dict:
    name = "hamio-grade-" + uuid.uuid4().hex
    args = args[:2] + ["--name", name] + args[2:]
    try:
        completed = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"exit_code": None, "status": "timeout", "passed": 0, "failed": None}
    finally:
        subprocess.run(["docker", "rm", "--force", name], capture_output=True, timeout=30)
    log.write_text(completed.stdout + completed.stderr)
    return summarize(completed)


def run(image: str, candidate: Path, baseline: Path, output: Path, reference=False) -> dict:
    if not list((baseline / "tests").glob("*.test.ts")):
        raise ValueError("No frozen baseline tests found")
    if not (baseline / "node_modules").is_dir():
        raise ValueError("Pinned baseline dependencies are missing")
    output.mkdir(parents=True, exist_ok=True)
    scratch = output / "scratch"
    scratch.mkdir(mode=0o777, exist_ok=True)
    os.chmod(scratch, 0o777)
    (scratch / "home").mkdir(mode=0o777, exist_ok=True)
    os.chmod(scratch / "home", 0o777)
    prefix = command(image, candidate, baseline, scratch)
    acceptance = ["bun", "test", "/grader/acceptance.test.ts", "--timeout", "60000"]
    result = {}
    if reference:
        prefix = prefix[:-1] + ["--env", "HAMIO_RECOVER_ENTRY=/grader/reference.ts", image]
    result["held_out"] = invoke(prefix + acceptance, output / "held-out.log")
    if not reference:
        quality = command(image, candidate, baseline, scratch, "2g")
        quality = quality[:-1] + ["--mount", f"type=bind,src={baseline / 'tests'},dst=/candidate/tests,readonly", image]
        result["frozen_quality"] = invoke(quality + ["bun", "run", "check"], output / "frozen-quality.log", 300)
        build = command(image, candidate, baseline, scratch, "2g")
        result["native_build"] = invoke(build + ["bun", "scripts/build.ts", "/work/hamio"], output / "native-build.log")
        if result["native_build"]["exit_code"] == 0 and (scratch / "hamio").is_file():
            native = prefix[:-1] + ["--env", "HAMIO_TEST_BINARY=/work/hamio", image]
            result["native_held_out"] = invoke(native + acceptance, output / "native-held-out.log")
        else:
            result["native_held_out"] = {"status": "untested", "reason": "Native build did not produce an executable"}
    (output / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reference", action="store_true")
    args = parser.parse_args()
    result = run(args.image, args.candidate.resolve(), args.baseline.resolve(), args.output.resolve(), args.reference)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    required = {"held_out": 60} if args.reference else {"held_out": 60, "frozen_quality": 114, "native_build": 0, "native_held_out": 60}
    raise SystemExit(0 if all(passed(result.get(name, {}), minimum) for name, minimum in required.items()) else 1)
