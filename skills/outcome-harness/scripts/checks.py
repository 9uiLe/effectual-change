"""Structural and evidence checks; semantic adequacy remains an agent review."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def document_digest(value: dict) -> str:
    return digest(json.dumps(value, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":")).encode())


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name}: expected an object")
    return value


def capture_context(record: dict, experiment: dict) -> dict:
    option = next((x for x in record.get("options", []) if x.get("id") == experiment.get("option_id")), {})
    return {"option": {"id": option.get("id"), "mechanism": option.get("mechanism")},
            "requirements": [x for x in record.get("requirements", [])
                             if x.get("id") in experiment.get("requirement_ids", [])]}


def valid_capture(value: dict) -> bool:
    command = value.get("command")
    if (not isinstance(command, list) or not command or any(not isinstance(x, str) for x in command)
            or type(value.get("exit_code")) is not int
            or not isinstance(value.get("stdout"), str) or not isinstance(value.get("stderr"), str)
            or not isinstance(value.get("cwd"), str) or not Path(value["cwd"]).is_absolute()
            or value.get("status") not in ("completed", "timeout")):
        return False
    try:
        started = datetime.fromisoformat(value["started_at"])
        ended = datetime.fromisoformat(value["finished_at"])
        return started.tzinfo is not None and ended.tzinfo is not None and ended >= started
    except (ValueError, TypeError, KeyError):
        return False


def local_artifact(root: Path, locator: str) -> Path:
    relative = Path(locator)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("artifact must be a relative path inside artifacts/")
    resolved = (root / relative).resolve()
    if not resolved.is_relative_to((root / "artifacts").resolve()):
        raise ValueError("artifact must remain inside artifacts/")
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError("artifact escapes the run directory")
    return resolved


@dataclass(frozen=True)
class Finding:
    code: str
    path: str
    message: str
    severity: str = "error"

    def as_dict(self) -> dict:
        return asdict(self)


class Inspection:
    def __init__(self):
        self.findings: list[Finding] = []

    def add(self, code, path, message, severity="error"):
        self.findings.append(Finding(code, path, message, severity))

    def text(self, obj, key, path):
        value = obj.get(key)
        if not isinstance(value, str) or not value.strip():
            self.add("MISSING_DETAIL", f"{path}.{key}", "Provide a nonempty description.")
            return ""
        return value

    def rows(self, obj, key, path="record", ids=True):
        value = obj.get(key)
        if not isinstance(value, list) or any(not isinstance(x, dict) for x in value):
            self.add("INVALID_COLLECTION", f"{path}.{key}", "Expected an array of objects.")
            return []
        if ids:
            seen = set()
            for index, row in enumerate(value):
                ident = row.get("id")
                if not isinstance(ident, str) or not ident.strip() or ident in seen:
                    self.add("INVALID_ID", f"{path}.{key}[{index}]", "Use a unique nonempty ID.")
                if isinstance(ident, str):
                    seen.add(ident)
        return value

    def links(self, obj, key, known, path, required=False):
        value = obj.get(key)
        if not isinstance(value, list) or any(not isinstance(x, str) for x in value):
            self.add("INVALID_LINKS", f"{path}.{key}", "Expected an array of IDs.")
            return []
        if len(value) != len(set(value)) or not set(value).issubset(known):
            self.add("BROKEN_LINK", f"{path}.{key}", "IDs must exist and occur once.")
        if required and not value:
            self.add("UNTRACED_WORK", f"{path}.{key}", "Link this work to its intended outcome.")
        return value


def inspect_intent(intent: dict) -> list[Finding]:
    check = Inspection()
    if type(intent.get("schema_version")) is not int or intent["schema_version"] != 1:
        check.add("SCHEMA_VERSION", "intent", "Expected schema_version 1.")
    outcomes = check.rows(intent, "outcomes", "intent")
    check.rows(intent, "constraints", "intent")
    if not outcomes:
        check.add("NO_OUTCOME", "intent.outcomes", "Define the user's desired result.")
    for outcome in outcomes:
        for field in ("statement", "acceptance"):
            check.text(outcome, field, f"intent.{outcome.get('id')}")
    for constraint in intent.get("constraints", []):
        if isinstance(constraint, dict):
            check.text(constraint, "text", f"intent.{constraint.get('id')}")
    return check.findings


def inspect_run(root: Path, stage: str = "plan") -> list[Finding]:
    try:
        return _inspect_run(root, stage)
    except (TypeError, AttributeError, KeyError) as exc:
        return [Finding("INVALID_RECORD", "record.json", f"Invalid field type or missing data: {exc}")]


def _inspect_run(root: Path, stage: str = "plan") -> list[Finding]:
    check = Inspection()
    try:
        intent = read_json(root / "intent.json")
        record = read_json(root / "record.json")
        brief_bytes = (root / "brief.md").read_bytes()
        brief = brief_bytes.decode("utf-8")
    except (OSError, ValueError, UnicodeError) as exc:
        return [Finding("INVALID_RUN", str(root), str(exc))]
    check.findings.extend(inspect_intent(intent))
    if type(record.get("schema_version")) is not int or record["schema_version"] != 1:
        check.add("SCHEMA_VERSION", "record", "Expected schema_version 1.")
    if record.get("brief_sha256") != digest(brief_bytes):
        check.add("BRIEF_CHANGED", "brief.md", "Original request changed; preserve it in a new run.")
    try:
        lock = read_json(root / "intent.lock.json")
        if lock.get("sha256") != document_digest(intent):
            check.add("INTENT_CHANGED", "intent.json", "Goal or constraints changed after sealing.")
    except FileNotFoundError:
        check.add("INTENT_UNSEALED", "intent.json", "Review original intent, then run seal.")
    except (OSError, ValueError) as exc:
        check.add("INVALID_LOCK", "intent.lock.json", str(exc))

    outcomes = {x.get("id") for x in intent.get("outcomes", []) if isinstance(x, dict)
                and isinstance(x.get("id"), str)}
    constraints = {x.get("id") for x in intent.get("constraints", []) if isinstance(x, dict)
                   and isinstance(x.get("id"), str)}
    requirements = check.rows(record, "requirements")
    options = check.rows(record, "options")
    experiments = check.rows(record, "experiments")
    evidence = check.rows(record, "evidence")
    research = check.rows(record, "research", ids=False)
    req_ids = {x.get("id") for x in requirements if isinstance(x.get("id"), str)}
    option_ids = {x.get("id") for x in options if isinstance(x.get("id"), str)}
    ev_ids = {x.get("id") for x in evidence if isinstance(x.get("id"), str)}
    source_ids = {x.get("id") for x in evidence if x.get("kind") == "source" and isinstance(x.get("id"), str)}
    experiment_map = {x.get("id"): x for x in experiments if isinstance(x.get("id"), str)}
    if not requirements:
        check.add("NO_REQUIREMENTS", "requirements", "Extract required capabilities from the original brief.")
    if not options:
        check.add("NO_OPTIONS", "options", "Explore whole-system approaches before choosing parts.")
    covered_constraints = set()
    covered_outcomes = set()
    for req in requirements:
        path = f"requirements.{req.get('id')}"
        if req.get("origin") not in ("explicit", "derived"):
            check.add("INVALID_ORIGIN", path, "Mark explicit requirements and derived hypotheses separately.")
        if req.get("origin") == "explicit":
            quote = check.text(req, "source_quote", path)
            if quote and quote not in brief:
                check.add("UNSUPPORTED_REQUIREMENT", path, "Explicit requirement quote must occur in brief.md.")
        check.text(req, "criterion", path)
        covered_outcomes.update(check.links(req, "outcome_ids", outcomes, path, True))
        covered_constraints.update(check.links(req, "constraint_ids", constraints, path))
    if constraints - covered_constraints:
        check.add("CONSTRAINT_GAP", "requirements", f"No capability traces to {sorted(constraints - covered_constraints)}.")
    if outcomes - covered_outcomes:
        check.add("OUTCOME_GAP", "requirements", f"No capability traces to {sorted(outcomes - covered_outcomes)}.")

    for option in options:
        path = f"options.{option.get('id')}"
        for field in ("mechanism", "outcome_contribution", "tradeoffs"):
            check.text(option, field, path)
        coverage = check.rows(option, "coverage", path, ids=False)
        seen = set()
        for row in coverage:
            rid = row.get("requirement_id")
            if not isinstance(rid, str) or rid not in req_ids or rid in seen:
                check.add("INVALID_COVERAGE", path, "Coverage must reference each requirement exactly once.")
                continue
            seen.add(rid)
            if not isinstance(row.get("mechanism"), str) or not row["mechanism"].strip():
                check.add("MISSING_MECHANISM", f"{path}.{rid}", "A required capability has no concrete mechanism.")
            if row.get("status") not in ("supported", "unknown", "violated"):
                check.add("INVALID_COVERAGE_STATUS", f"{path}.{rid}", "Use supported, unknown, or violated.")
            refs = check.links(row, "evidence_ids", ev_ids, f"{path}.{rid}")
            if row.get("status") == "supported" and not refs:
                check.add("UNSUPPORTED_COVERAGE", f"{path}.{rid}", "Supported capability needs cited evidence.")
            supporting = [x for x in evidence if x.get("id") in refs]
            if row.get("status") == "supported" and supporting:
                if not any(x.get("kind") in ("source", "measurement") for x in supporting):
                    check.add("INFERENCE_AS_PROOF", f"{path}.{rid}", "Inference alone cannot establish a required capability.")
                for item in supporting:
                    if rid not in item.get("requirement_ids", []) or item.get("option_id") not in (None, option.get("id")):
                        check.add("UNRELATED_EVIDENCE", f"{path}.{rid}", "Cited evidence must apply to this capability and option.")
                    if item.get("kind") == "measurement" and item.get("result") != "pass":
                        check.add("NEGATIVE_SUPPORT", f"{path}.{rid}", "A failed or inconclusive measurement cannot support satisfaction.")
            if row.get("status") == "unknown":
                check.add("UNKNOWN_CAPABILITY", f"{path}.{rid}", "Keep this uncertainty visible; investigate if it changes the decision.", "warning")
        if req_ids - seen:
            check.add("CAPABILITY_GAP", path, f"Missing capabilities: {sorted(req_ids - seen)}.")

    for item in research:
        path = "research"
        for field in ("question", "finding", "applicability"):
            check.text(item, field, path)
        sources = item.get("sources")
        if not isinstance(sources, list) or not sources or any(not (https_url(x) or isinstance(x, str) and x in source_ids) for x in sources):
            check.add("MISSING_RESEARCH_SOURCE", path, "Cite source URLs or recorded source evidence IDs supporting this investigation.")

    scopes = ("unit", "integration", "end_to_end")
    for exp in experiments:
        path = f"experiments.{exp.get('id')}"
        if exp.get("option_id") not in option_ids:
            check.add("BROKEN_LINK", path, "Experiment must reference an existing option.")
        check.links(exp, "outcome_ids", outcomes, path, True)
        check.links(exp, "requirement_ids", req_ids, path, True)
        for field in ("question", "environment", "pass_criterion", "fail_criterion",
                      "retained_conditions", "omitted_conditions", "negative_control"):
            check.text(exp, field, path)
        if exp.get("scope") not in scopes:
            check.add("INVALID_SCOPE", path, "Use unit, integration, or end_to_end.")

    measured = []
    captures = {}
    for item in evidence:
        path = f"evidence.{item.get('id')}"
        check.text(item, "claim", path)
        check.links(item, "outcome_ids", outcomes, path)
        check.links(item, "requirement_ids", req_ids, path)
        kind = item.get("kind")
        if kind == "source":
            if not https_url(item.get("locator")):
                try:
                    source = local_artifact(root, item.get("locator", ""))
                    if digest(source.read_bytes()) != item.get("sha256"):
                        check.add("SOURCE_CHANGED", path, "Local source artifact digest does not match.")
                except (OSError, ValueError, TypeError) as exc:
                    check.add("INVALID_SOURCE", path, f"Use an HTTPS URL or a hashed local source under artifacts/: {exc}")
        elif kind == "measurement":
            before = len(check.findings)
            exp = experiment_map.get(item.get("experiment_id"))
            if exp is None:
                check.add("MISSING_EXPERIMENT", path, "Measurement must reference its planned experiment.")
            else:
                for field in ("option_id", "scope", "environment"):
                    if item.get(field) != exp.get(field):
                        check.add("EVIDENCE_SCOPE_MISMATCH", path, f"{field} differs from the experiment.")
                for field in ("outcome_ids", "requirement_ids"):
                    if set(item.get(field, [])) != set(exp.get(field, [])):
                        check.add("EVIDENCE_SCOPE_MISMATCH", path, f"{field} differs from the experiment.")
            if item.get("result") not in ("pass", "fail", "inconclusive"):
                check.add("MISSING_VERDICT", path, "Assess observations against the planned criterion.")
            if not isinstance(item.get("locator"), str):
                check.add("MISSING_ARTIFACT", path, "Measurement needs a capture artifact.")
            else:
                try:
                    artifact = local_artifact(root, item["locator"])
                    raw = artifact.read_bytes()
                    captured = json.loads(raw)
                    if item.get("sha256") != digest(raw):
                        check.add("EVIDENCE_CHANGED", path, "Captured artifact digest does not match.")
                    if not isinstance(captured, dict) or captured.get("type") != "command_capture":
                        raise ValueError("Not a command capture.")
                    if not valid_capture(captured):
                        check.add("INVALID_CAPTURE", path, "Capture needs actual command, observations, exit status, directory and execution times.")
                    if captured.get("run_id") != record.get("run_id") or captured.get("experiment_id") != item.get("experiment_id"):
                        check.add("EVIDENCE_IDENTITY", path, "Capture belongs to a different run or experiment.")
                    if captured.get("experiment") != exp or captured.get("intent_sha256") != document_digest(intent):
                        check.add("CAPTURE_CONTEXT_CHANGED", path, "Experiment criteria, environment, or intent changed after capture.")
                    if exp is not None and captured.get("configuration") != capture_context(record, exp):
                        check.add("CAPTURE_CONFIGURATION_CHANGED", path, "Tested option or capability definition changed; reassess with new observations.")
                    if captured.get("status") != "completed" and item.get("result") == "pass":
                        check.add("INCOMPLETE_CAPTURE", path, "A timeout cannot establish a passing result; preserve it as fail or inconclusive.")
                    captures[item.get("id")] = captured
                except (OSError, ValueError, TypeError) as exc:
                    check.add("MISSING_ARTIFACT", path, str(exc))
            if len(check.findings) == before:
                measured.append(item)
        elif kind != "inference":
            check.add("INVALID_EVIDENCE_KIND", path, "Use source, measurement, or inference.")

    review = record.get("review")
    if not isinstance(review, dict):
        check.add("INVALID_REVIEW", "review", "Expected review metadata.")
        review = {}
    findings = check.rows(review, "findings", "review")
    for item in findings:
        if item.get("severity") not in ("critical", "material", "minor") or item.get("disposition") not in ("open", "accepted", "rejected", "deferred"):
            check.add("INVALID_REVIEW_FINDING", f"review.{item.get('id')}", "Use documented severity and disposition values.")
        check.text(item, "issue", f"review.{item.get('id')}")
        if item.get("disposition") != "open":
            check.text(item, "reason", f"review.{item.get('id')}")

    decision = record.get("decision")
    if not isinstance(decision, dict):
        check.add("INVALID_DECISION", "decision", "Expected decision metadata.")
        decision = {}
    if decision.get("status") not in ("exploring", "provisional", "selected", "verified", "rejected"):
        check.add("INVALID_DECISION_STATUS", "decision", "Use a documented decision status.")
    chosen = next((x for x in options if x.get("id") == decision.get("option_id")), None)
    if stage in ("decide", "verify"):
        if not research:
            check.add("NO_EXPLORATION", "research", "Investigate a structurally different approach, or document why only one is viable.")
        if review.get("mode") not in ("independent_context", "self_review") or review.get("raw_brief_read") is not True:
            check.add("RAW_BRIEF_REVIEW_REQUIRED", "review", "Reconstruct needed capabilities from the raw brief, not only the designer summary.")
        for item in findings:
            if item.get("severity") in ("critical", "material") and item.get("disposition") in ("open", "deferred"):
                check.add("UNRESOLVED_FINDING", f"review.{item.get('id')}", "Resolve this material concern before claiming readiness.")
        if chosen is None:
            check.add("NO_SELECTION", "decision", "Choose a whole-system option or keep investigating.")
        else:
            for row in chosen.get("coverage", []):
                if not isinstance(row, dict):
                    continue
                if row.get("status") == "violated":
                    check.add("MANDATORY_VIOLATION", "decision", "The chosen option violates a required capability.")
                if row.get("status") == "unknown" and decision.get("status") != "provisional":
                    check.add("UNCONDITIONAL_UNKNOWN", "decision", "Unknown required capability permits only conditional adoption.")
        check.text(decision, "rationale", "decision")
        check.text(decision, "reconsider_when", "decision")
        conditions = decision.get("conditions")
        if not isinstance(conditions, list) or any(not isinstance(x, str) or not x.strip() for x in conditions):
            check.add("INVALID_CONDITIONS", "decision", "Use an array of explicit conditions.")
        elif decision.get("status") == "provisional" and not conditions:
            check.add("MISSING_CONDITIONS", "decision", "Name the facts needed to adopt this option.")

        target = record.get("target_environment")
        passing = [x for x in measured if x.get("option_id") == decision.get("option_id")
                   and x.get("result") == "pass" and x.get("environment") == target]
        failures = [x for x in measured if x.get("option_id") == decision.get("option_id")
                    and x.get("environment") == target and x.get("result") != "pass"]
        for failed in failures:
            replacement = next((x for x in passing if x.get("id") == failed.get("superseded_by")), None)
            replacement_capture = captures.get(replacement.get("id"), {}) if replacement else {}
            failed_capture = captures.get(failed.get("id"), {})
            applicable = (replacement is not None
                          and replacement.get("locator") != failed.get("locator")
                          and replacement.get("sha256") != failed.get("sha256")
                          and replacement_capture.get("finished_at", "") > failed_capture.get("finished_at", "")
                          and replacement.get("scope") == failed.get("scope")
                          and set(failed.get("requirement_ids", [])).issubset(replacement.get("requirement_ids", []))
                          and set(failed.get("outcome_ids", [])).issubset(replacement.get("outcome_ids", [])))
            if not applicable:
                severity = "warning" if stage == "decide" and decision.get("status") == "provisional" else "error"
                check.add("NEGATIVE_EVIDENCE", f"evidence.{failed.get('id')}", "Resolve this failed or inconclusive measurement with explicitly linked applicable new observations.", severity)

    if stage == "verify":
        target = check.text(record, "target_environment", "record")
        passing = [x for x in measured if x.get("option_id") == decision.get("option_id")
                   and x.get("result") == "pass" and x.get("environment") == target]
        verified_requirements = {rid for x in passing for rid in x.get("requirement_ids", [])}
        if req_ids - verified_requirements:
            check.add("UNVERIFIED_CAPABILITY", "evidence", f"No passing target-environment measurement for {sorted(req_ids - verified_requirements)}.")
        whole = {oid for x in passing if x.get("scope") == "end_to_end" for oid in x.get("outcome_ids", [])}
        if outcomes - whole:
            check.add("NO_WHOLE_OUTCOME_EVIDENCE", "evidence", "Unit results do not establish the final outcome; capture a complete representative path.")
        if decision.get("status") in ("exploring", "provisional", "rejected"):
            check.add("NOT_READY_TO_VERIFY", "decision", "Resolve adoption conditions before reporting verified.")
    return check.findings


def https_url(value):
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def report(root: Path, stage: str) -> dict:
    findings = inspect_run(root, stage)
    return {"stage": stage, "structural_readiness": not any(x.severity == "error" for x in findings),
            "semantic_review_required": True, "findings": [x.as_dict() for x in findings]}
