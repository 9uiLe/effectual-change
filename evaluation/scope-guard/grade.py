"""Run held-out scope-guard checks and frozen baseline tests in Docker."""

import argparse
import json
import subprocess
from pathlib import Path


def command(image: str, candidate: Path, frozen_tests: Path) -> list[str]:
    return [
        "docker", "run", "--rm", "--network", "none", "--read-only",
        "--user", "65534:65534", "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges", "--pids-limit", "64",
        "--memory", "256m", "--cpus", "1",
        "--tmpfs", "/tmp:rw,noexec,nosuid,size=32m,mode=1777",
        "--workdir", "/candidate", "--env", "HOME=/tmp",
        "--mount", f"type=bind,src={candidate},dst=/candidate,readonly",
        "--mount", f"type=bind,src={frozen_tests},dst=/candidate/tests,readonly",
        "--mount", f"type=bind,src={Path(__file__).parent.resolve()},dst=/grader,readonly",
        image, "node",
    ]


def run(image: str, candidate: Path, frozen_tests: Path) -> dict:
    prefix = command(image, candidate, frozen_tests)
    result = {}
    for name, args in (
        ("held_out", ["/grader/grade.mjs"]),
        ("frozen_regression", ["--test", *[
            f"/candidate/tests/{p.name}" for p in sorted(frozen_tests.glob("*.test.mjs"))
        ]]),
    ):
        if name == "frozen_regression" and len(args) == 1:
            raise ValueError("No frozen baseline tests found")
        completed = subprocess.run(prefix + args, capture_output=True, text=True, timeout=90)
        entry = {"exit_code": completed.returncode}
        if name == "held_out":
            entry["result"] = json.loads(completed.stdout)
        else:
            entry["stdout"] = completed.stdout
        entry["stderr"] = completed.stderr
        result[name] = entry
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, help="Locally pinned image ID or digest")
    parser.add_argument("--candidate", required=True, type=Path, help="Candidate model-strategy directory")
    parser.add_argument("--frozen-tests", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = run(args.image, args.candidate.resolve(), args.frozen_tests.resolve())
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({name: {k: v for k, v in entry.items() if k != "stdout"}
                      for name, entry in result.items()}, ensure_ascii=False))
    return 0 if all(entry["exit_code"] == 0 for entry in result.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
