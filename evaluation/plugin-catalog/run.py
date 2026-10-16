#!/usr/bin/env python3
"""One-command local Codex A/B trial. Candidate Bash is graded only in Docker."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import secrets
import signal
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
EVAL = Path(__file__).resolve().parent
SKILL = ROOT / "skills/effectual-change"
BASE = "78953271ced181e79016a28245dbdd1ca59e9dd8"
IMAGE = "effectual-change-grader:local"
TASK = (
    "このリポジトリのREADMEのプラグイン一覧で、同じプラグインへの行が重複しても"
    "検証が成功してしまいます。既存の正しい検証仕様と表以外の通常リンクの扱いを"
    "維持しながら、重複する場合に検証が失敗するようにしてください。"
    "回帰テストも追加し、実行した検証と残る未確認事項を報告してください。\n"
    "この作業ディレクトリ内だけを変更してください。commit、push、PR作成は"
    "行わないでください。外部通信も行わないでください。"
)


def run(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(args, check=True, **kwargs)


def private_dir(path: Path) -> None:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.chmod(0o700)


def conflicting_skills(codex_home: Path) -> list[Path]:
    """Only Effectual Change conflicts; Codex may install unrelated built-ins.

    Scan skill names as well as directory names. This is a local preflight,
    NOT proof that managed/system-wide Skills cannot be visible at runtime.
    """
    conflicts = []
    for skill_file in codex_home.rglob("SKILL.md"):
        if skill_file.parent.name.casefold() == "effectual-change":
            conflicts.append(skill_file)
            continue
        try:
            with skill_file.open(encoding="utf-8") as handle:
                start = handle.read(4096)
        except (OSError, UnicodeError):
            raise RuntimeError(f"Cannot inspect Codex Skill metadata: {skill_file}")
        frontmatter = start.split("\n---", 1)[0] if start.startswith("---\n") else ""
        if re.search(r"""(?im)^name:\s*['"]?effectual-change['"]?\s*$""",
                     frontmatter):
            conflicts.append(skill_file)
    return conflicts


def trial_order(value: str) -> tuple[str, str]:
    """Record the realized execution order, including randomized runs."""
    if value == "control-first":
        return ("control", "treatment")
    if value == "treatment-first":
        return ("treatment", "control")
    if value == "random":
        return ("control", "treatment") if secrets.randbelow(2) == 0 else (
            "treatment", "control"
        )
    raise ValueError(f"Unknown execution order: {value}")


def auth_check(state: Path) -> Path:
    for name in ("git", "codex", "python3"):
        if shutil.which(name) is None:
            raise RuntimeError(f"Missing executable: {name}")
    if not (SKILL / "SKILL.md").is_file() or not (EVAL / "grade.py").is_file():
        raise RuntimeError("Use this runner from the effectual-change evaluation branch")
    # Do not launch paid model calls when the local controller's own checks fail.
    run([sys.executable, "-m", "unittest", "discover",
         "-s", str(EVAL), "-p", "test_*.py", "-v"])
    codex_home = state / "codex-home"
    private_dir(codex_home)
    conflicts = conflicting_skills(codex_home)
    if conflicts:
        raise RuntimeError(
            "Evaluation Codex home exposes Effectual Change globally: "
            + ", ".join(str(path) for path in conflicts)
        )
    env = dict(os.environ, CODEX_HOME=str(codex_home))
    login = subprocess.run(
        ["codex", "login", "status"], env=env, capture_output=True, check=False
    )
    if login.returncode:
        raise RuntimeError(
            "One-time login needed. Run this locally and retry:\n"
            f"CODEX_HOME='{codex_home}' codex login"
        )
    return codex_home


def checkouts(destination: Path) -> dict[str, Path]:
    source = destination / "source"
    run(["git", "clone", "--quiet", "https://github.com/9uiLe/plugins.git", str(source)])
    run(["git", "-C", str(source), "checkout", "--quiet", "--detach", BASE])
    result: dict[str, Path] = {}
    for side in ("control", "treatment"):
        checkout = destination / side
        run(["git", "clone", "--quiet", "--no-hardlinks", str(source), str(checkout)])
        run(["git", "-C", str(checkout), "checkout", "--quiet", "--detach", BASE])
        sha = run(
            ["git", "-C", str(checkout), "rev-parse", "HEAD"],
            capture_output=True, text=True
        ).stdout.strip()
        if sha != BASE:
            raise RuntimeError(f"Wrong base in {side}: {sha}")
        if (checkout / ".agents/skills/effectual-change").exists():
            raise RuntimeError("Unexpected Skill in base source")
        result[side] = checkout
    target = result["treatment"] / ".agents/skills/effectual-change"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SKILL, target)
    return result


def trial(side: str, checkout: Path, out: Path, codex_home: Path,
          model: str | None, timeout: int) -> dict:
    # Repeat the targeted guard immediately before every trial; another run
    # could have populated CODEX_HOME since the previous preflight.
    conflicts = conflicting_skills(codex_home)
    if conflicts:
        raise RuntimeError(
            "Effectual Change found in shared Codex home: "
            + ", ".join(str(path) for path in conflicts)
        )
    skill_file = checkout / ".agents/skills/effectual-change/SKILL.md"
    project_skill_present = skill_file.is_file()
    if project_skill_present != (side == "treatment"):
        raise RuntimeError(f"{side}: unexpected project Skill exposure")
    artifacts = out / (side + "-results")
    private_dir(artifacts)
    home, tmp = artifacts / "home", artifacts / "tmp"
    private_dir(home)
    private_dir(tmp)
    env = os.environ.copy()
    for key in tuple(env):
        upper = key.upper()
        if (upper in {"GITHUB_TOKEN", "GH_TOKEN", "CODEX_API_KEY", "OPENAI_API_KEY"}
            or upper.endswith(("_TOKEN", "_SECRET", "_PASSWORD", "_API_KEY"))):
            del env[key]
    env.update(HOME=str(home), CODEX_HOME=str(codex_home), TMPDIR=str(tmp))
    command = [
        "codex", "--ask-for-approval", "never", "exec",
        "--ignore-user-config", "--json", "--ephemeral",
        "--sandbox", "workspace-write",
        "-c", "sandbox_workspace_write.network_access=false",
        "-c", 'shell_environment_policy.inherit="core"',
        "-C", str(checkout),
    ]
    if model:
        command += ["--model", model]
    command += ["-"]
    prompt = TASK if side == "control" else (
        "$effectual-change を使用して、以下の変更要求に対応してください。\n\n" + TASK
    )
    (artifacts / "prompt.txt").write_text(prompt, encoding="utf-8")
    print(f"Running {side}...", flush=True)
    started = time.monotonic()
    with (artifacts / "events.jsonl").open("wb") as events, (
        artifacts / "stderr.txt"
    ).open("wb") as stderr:
        proc = subprocess.Popen(
            command, stdin=subprocess.PIPE, stdout=events,
            stderr=stderr, env=env, cwd=checkout, start_new_session=True,
        )
        timed_out = False
        try:
            proc.communicate(prompt.encode("utf-8"), timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            # Kill the agent's child process group too; otherwise tool processes
            # can continue modifying the checkout after a trial times out.
            os.killpg(proc.pid, signal.SIGKILL)
            proc.communicate()
    events = []
    for line in (artifacts / "events.jsonl").read_text(
        encoding="utf-8", errors="replace"
    ).splitlines():
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                events.append(obj)
        except json.JSONDecodeError:
            pass
    usage = [
        obj.get("usage") for obj in events if obj.get("type") == "turn.completed"
    ]
    metrics = {}
    for key in ("input_tokens", "cached_input_tokens", "output_tokens"):
        values = [u[key] for u in usage if isinstance(u, dict) and
                  isinstance(u.get(key), int)]
        metrics[key] = sum(values) if values else None
    observed = any(
        "effectual-change" in str(item.get("command", ""))
        and "SKILL.md" in str(item.get("command", ""))
        for obj in events
        for item in [obj.get("item", {})]
        if obj.get("type") in ("item.started", "item.completed")
        and isinstance(item, dict)
    )
    # Standard Codex exec JSONL may expose only thread_id and usage, not a
    # resolved model name. Never infer model identity from the --model flag.
    event_models = set()
    for event in events:
        if event.get("type") not in ("thread.started", "turn.started",
                                     "turn.completed"):
            continue
        for field in (event, event.get("config", {})):
            if isinstance(field, dict):
                model_name = field.get("model")
                if isinstance(model_name, str) and model_name:
                    event_models.add(model_name)
    resolved_model = next(iter(event_models)) if len(event_models) == 1 else None
    head_after = run(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"],
        capture_output=True, text=True,
    ).stdout.strip()
    with (artifacts / "diff.patch").open("wb") as output:
        subprocess.run(
            ["git", "-C", str(checkout), "--no-pager", "diff",
             "--no-ext-diff", "HEAD"], stdout=output, check=False
        )
    with (artifacts / "status.txt").open("wb") as output:
        subprocess.run(
            ["git", "-C", str(checkout), "status", "--short"],
            stdout=output, check=False
        )
    return {
        "condition": side, "return_code": proc.returncode,
        "completed": any(obj.get("type") == "turn.completed" for obj in events),
        "timed_out": timed_out, "base_preserved": head_after == BASE,
        "head_after": head_after, "seconds": round(time.monotonic()-started, 2),
        "tokens": metrics,
        "skill_read_command_observed": observed,
        "project_skill_present": project_skill_present,
        "resolved_model_in_events": resolved_model,
        "stream_errors": any(e.get("type") in ("turn.failed", "error") for e in events),
        "artifacts": str(artifacts),
    }


def docker_image() -> None:
    probe = subprocess.run(
        ["docker", "image", "inspect", IMAGE],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    )
    if probe.returncode:
        print("Building the offline grader image (first run)...", flush=True)
        run(["docker", "build", "--tag", IMAGE, str(EVAL)])


def grade(checkout: Path, side: str, out: Path) -> dict:
    dest = out / (side + "-results")
    stdout, stderr = dest / "grade.json", dest / "grade-stderr.txt"
    command = [
        "docker", "run", "--rm", "--network", "none", "--read-only",
        "--user", "65534:65534", "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--pids-limit", "64", "--memory", "512m", "--cpus", "1",
        "--tmpfs", "/tmp:rw,nosuid,nodev,size=64m,mode=1777",
        "--mount", f"type=bind,src={EVAL / 'grade.py'},dst=/eval/grade.py,readonly",
        "--mount", f"type=bind,src={checkout},dst=/candidate,readonly",
        IMAGE, "python3", "/eval/grade.py", "--candidate", "/candidate",
    ]
    with stdout.open("wb") as so, stderr.open("wb") as se:
        try:
            code = subprocess.run(
                command, stdout=so, stderr=se, timeout=120, check=False
            ).returncode
        except subprocess.TimeoutExpired:
            code = -1
    try:
        data = json.loads(stdout.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    return {"return_code": code, "passed": data.get("passed"),
            "total": data.get("total"), "grade_file": str(stdout)}


def exposure_evidence(report: dict) -> bool:
    """Detect explicit treatment use and obvious control contamination.

    This is a trace-based eligibility check, not proof of every hidden Skill.
    """
    a, b = report["trials"]["control"], report["trials"]["treatment"]
    return (
        not a["project_skill_present"]
        and not a["skill_read_command_observed"]
        and b["project_skill_present"]
        and b["skill_read_command_observed"]
    )


def markdown(report: dict) -> str:
    rows = []
    for side in report["execution_order"]:
        item = report["trials"][side]
        scored = item["grade"]
        value = (f"{scored['passed']}/{scored['total']}"
                 if scored and isinstance(scored.get("passed"), int)
                 and isinstance(scored.get("total"), int) else "NOT VERIFIED")
        rows.append(
            f"| {side} | {value} | {item['return_code']} | "
            f"{item['seconds']} | {item['tokens']['input_tokens'] or 'n/a'} |"
        )
    resolved = {
        report["trials"][side].get("resolved_model_in_events")
        for side in ("control", "treatment")
    }
    model_evidence = (
        next(iter(resolved)) if len(resolved) == 1 and None not in resolved
        else "not reported consistently in JSONL (unverified)"
    )
    order = " -> ".join(report["execution_order"])
    control = report["trials"]["control"]
    treatment = report["trials"]["treatment"]
    return (
        "## Phase 2 local Codex comparison\n\n"
        f"Base: {BASE}. Requested model: {report['model'] or 'CLI default (unverified)'}.\n"
        f"Execution order: {order} (requested: {report['order_requested']}).\n"
        f"Resolved model observed in events: {model_evidence}.\n\n"
        "| Trial | Grader | Codex exit | Seconds | Input tokens |\n"
        "| --- | --- | --- | --- | --- |\n"
        + "\n".join(rows)
        + "\n\nA single pair is INCONCLUSIVE evidence about Skill efficacy, "
        "even when both candidates pass.\n\n"
        f"Control project Skill present: {control['project_skill_present']}; "
        f"Effectual Change read command observed: {control['skill_read_command_observed']}.\n"
        f"Treatment project Skill present: {treatment['project_skill_present']}; "
        f"Effectual Change read command observed: {treatment['skill_read_command_observed']}.\n"
        f"Exposure evidence sufficient for this pilot: {exposure_evidence(report)}. "
        "No command read does not rule out hidden system/admin Skills; a present "
        "project Skill is not proof of use.\n\n"
        "Raw agent logs, credentials, and diffs are stored locally, not posted to GitHub.\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", help="Use the same explicit model in both runs")
    parser.add_argument("--state-dir", type=Path,
                        default=Path.home() / ".local/share/effectual-change-eval")
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--order", default="random",
                        choices=("control-first", "treatment-first", "random"),
                        help="Execution order; random is the default and is recorded")
    parser.add_argument("--skip-grade", action="store_true",
                        help="Do not execute agent-written code; grade as NOT VERIFIED")
    parser.add_argument("--post-issue", action="store_true",
                        help="Post only a short summary to effectual-change Issue #13")
    args = parser.parse_args()
    if args.timeout < 30:
        parser.error("--timeout must be >= 30")
    state = args.state_dir.expanduser().resolve()
    private_dir(state)
    codex_home = auth_check(state)
    if not args.skip_grade:
        if shutil.which("docker") is None:
            raise RuntimeError("Docker required for safe grading; or pass --skip-grade")
        docker_image()
    if args.post_issue and shutil.which("gh") is None:
        raise RuntimeError("gh CLI required for --post-issue")
    private_dir(state / "runs")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = state / "runs" / (stamp + "-" + secrets.token_hex(4))
    private_dir(out)
    checkouts_map = checkouts(out)
    selected_order = trial_order(args.order)
    report = {
        "base_sha": BASE, "model": args.model, "created": stamp,
        "order_requested": args.order, "execution_order": list(selected_order),
        "trials": {},
    }
    for side in selected_order:
        result = trial(side, checkouts_map[side], out,
                       codex_home, args.model, args.timeout)
        result["grade"] = (None if args.skip_grade
                           else grade(checkouts_map[side], side, out))
        report["trials"][side] = result
    (out / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    summary = markdown(report)
    (out / "report.md").write_text(summary, encoding="utf-8")
    print("\n" + summary + "\nRun artifacts: " + str(out), flush=True)
    success = all(
        x["return_code"] == 0 and x["completed"] and not x["timed_out"]
        and x["base_preserved"] and not x["stream_errors"]
        for x in report["trials"].values()
    )
    # A failed *candidate* is a valid experiment result. A failed *grader* is not.
    graded = args.skip_grade or all(
        x["grade"]["return_code"] in (0, 1)
        and isinstance(x["grade"].get("passed"), int)
        and x["grade"].get("total") == 8
        for x in report["trials"].values()
    )
    eligible = success and graded and exposure_evidence(report)
    if args.post_issue:
        if not eligible or args.skip_grade:
            print("Skipping Issue comment: comparison incomplete, ungraded, "
                  "or Skill exposure not confirmed by available evidence.")
        else:
            run(["gh", "issue", "comment", "13", "--repo", "9uiLe/effectual-change",
                 "--body-file", str(out / "report.md")])
    return 0 if eligible else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, OSError, subprocess.CalledProcessError) as exc:
        print(f"Evaluation incomplete: {exc}", file=sys.stderr)
        sys.exit(2)
