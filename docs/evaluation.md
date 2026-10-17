# Behavioral evaluation and bounded learning

The evaluation suite asks whether Outcome Harness helps an agent achieve the user's whole outcome, investigate a consequential unknown and keep its claims within its evidence. It also checks whether the agent can finish a simple edit without imposing a large process. The evaluator never scores an answer by matching words, API names or checklist phrases.

**Current results status:** no paired baseline/candidate evaluation or independent behavioral verdicts are supplied. Initial, unpaired smoke observations and their limits are recorded in [validation.md](validation.md). The case corpus and evaluator have deterministic structural tests. Passing those tests is not evidence that the skill improves agent behavior. Test-generated verdicts are temporary synthetic fixtures, never behavioral results.

## What is supplied

`evaluation/cases/*.json` contains original public briefs and explicit artifact lists. `evaluation/artifacts/` contains synthetic product facts, reference material and one SVG to edit. These facts describe fictional interfaces; they make no claims about features of real products. `evaluation/rubrics/*.json` is evaluator-only material, separate from the solver packets. Rubrics describe observable behavior, alternatives that may be acceptable and critical failures. They do not require exact phrases or one predetermined component choice.

| Case | Split | Behavior under test |
| --- | --- | --- |
| `arrival-action-verification` | Regression | Preserve unattended arrival → state-changing interaction → saved-result verification; detect an observer-only configuration. |
| `whole-system-throughput` | Regression | Compare complete configurations against batch completion rather than select the fastest component. |
| `unfamiliar-change-mechanism` | Regression | Investigate an unfamiliar documented mechanism and its limits before committing to the familiar API. |
| `prototype-environment-gap` | Regression | Separate a local probe from deployment evidence and make a useful conditional decision. |
| `simple-label-edit` | Regression | Deliver a small file edit directly; detect unnecessary procedure as a process false positive. |
| `crash-consistent-catalog` | Holdout | Transfer whole-outcome and evidence reasoning to interrupted publication and recovery in another domain. |

The held-out case is held out **from the solver and from candidate tuning**, not hidden from a person who can read this repository. Once a solver, candidate author or tuning loop has consumed it, it is no longer a fresh generalization test for that loop. Replace it with a newly authored private case before making another fresh-holdout claim. Do not report performance on one visible case as broad generalization proof.

## Structural checks

From the repository root:

```sh
python3 evaluation/evaluate.py validate
python3 -m unittest discover -s evaluation -p 'test_*.py' -v
```

These check case/rubric links, public-only packet construction, path isolation, hashes, verdict completeness, arithmetic, paired controls and promotion vetoes. They run no agent, model API, external program or behavioral grader. A return code of zero proves only those structural checks passed. The script uses the Python standard library; Python 3.9 or later is required.

## Prepare a public-only solver packet

```sh
python3 evaluation/evaluate.py list
python3 evaluation/evaluate.py prepare arrival-action-verification
```

`prepare` writes a fresh temporary directory and prints its location and content digest. An optional `--dest /absolute/path/to/new-packet` selects a directory that must not already exist and must be outside the evaluation tree. The packet contains only `case.json`, its allowlisted raw artifacts and `packet-manifest.json`. Arbitrary added case fields, rubrics, scores and evaluator notes are not copied. Paths with traversal or symlinks are rejected. The manifest records hashes of every public file; its `packet_sha256` identifies the exact public input used in a paired run.

Run the solver in a fresh context with only:

1. That public packet and an isolated writable working directory.
2. The baseline or candidate skills being evaluated.
3. The same neutral control prompt, tool access, model/effort and resource ceiling for both arms.

The packet builder is a packaging tool, **not a sandbox or an agent launcher**. The operator must restrict the solver's readable files and context. Merely asking an agent not to read the private directory is not an access boundary. Do not give it this repository, rubric files, prior judgments or an inherited conversation that discusses expected misses. If delegating to a native subagent, use a fresh history and enforce the file boundary; if the host cannot do that, use a separate isolated session/environment. The main agent owns synthesis when subagents are used. No particular host or model is required.

Give both arms the same raw brief and artifacts. Retain the full solver transcript, including tool results and failures, the final response and any edited files. Do not repair one arm's answer or give it extra hints. A neutral prompt can simply ask the agent to carry out `case.json`'s brief using the supplied material. Do not include rubric criteria or names of expected failures in that prompt.

The script deliberately does not call a model API, launch a shell or create a solver session. Use the host's normal agent facilities yourself, then return raw artifacts to the evaluator. Record observed wall time, turns, input/output tokens and actual cost when available. Unknown cost is `null`, never zero. Record all solver/subagent usage within the same arm's totals. Keep parallelism, caches and initial environment comparable; note any remaining difference before interpreting the result.

## Judge independently and retain evidence

An evaluator who did not solve the case reads the original brief and raw artifacts, then the private rubric. Judge behavior from what the solver did and delivered. A self-critique by the solver is not an independent verdict. Blind arm labels and randomize reading order where practical. For a material disputed judgment, retain the dissent and have another independent evaluator adjudicate; a numeric average cannot resolve an observed critical failure by itself.

Create incomplete evaluator-only score templates:

```sh
python3 evaluation/evaluate.py template --arm baseline --include-holdout --output /tmp/baseline-verdicts.json
python3 evaluation/evaluate.py template --arm candidate --include-holdout --output /tmp/candidate-verdicts.json
```

These files contain no judged results and fail validation until completed. Keep them outside solver access. Fill the following fields:

- `evaluation_id`: identical for the paired evaluation.
- `configuration`: a label, exact skill revision (or `none`), model, effort, unique tool list, stable environment identifier, SHA-256 of the neutral control prompt, and per-case token/second/turn ceiling. Both arms must use identical controls; only the skill revision and label may differ.
- `judge`: evaluator identifier, a truthful `independent_of_solver: true` declaration and timezone-qualified ISO-8601 timestamp. The tool checks the declaration's structure; it cannot establish actual independence.
- Each case's `artifacts`: retained files with `path`, `sha256` and `role` (`transcript`, `result` or `usage`). At least one transcript is required. Paths are absolute or relative to the verdict file. Register final files and usage records as well when available. The tool checks file existence and hashes.
- `metrics`: actual `wall_seconds`, `solver_turns`, `input_tokens`, `output_tokens` and `cost_usd` (explicit `null` if unavailable).
- Every criterion's `rating`: `met`, `partial` or `missed`. Every critical failure's `occurred`: explicit `true` or `false`.
- `process_assessment.unnecessary_process`: whether the harness imposed procedure that materially delayed or displaced the task. This is the process false-positive count, not a penalty for useful planning on a complex case.

Each criterion, critical-failure verdict and process assessment needs at least one evidence item with `artifact` (matching a registered artifact path), `location` (such as a transcript turn, line range or SVG element) and `observation` (what occurred and why it supports that judgment). For absence, describe what the full trace lacks and cite the relevant trace range; do not invent evidence. An observation's nonempty text satisfies a structure check, not a semantic truth check.

For example, an evidence item has this shape; the placeholders below are not a judgment:

```json
{
  "artifact": "case-a-transcript.txt",
  "location": "turns 3–5 and final response",
  "observation": "Evaluator describes the observed action, omission or unsupported claim here."
}
```

Read each private rubric for its behavioral meaning. Ratings contribute 1, 0.5 or 0 times the criterion weight, normalized to 100 per case. Cases have equal weight in the aggregate. All critical-failure flags are evaluated separately; an impressive average cannot erase one. The grader verifies that criterion/failure identifiers exactly match the frozen rubric and that packet/rubric hashes have not changed since template creation. It never interprets the artifact contents, the evidence prose or the truth of a rating. Keep detailed judgments beside the generated report.

## Compare paired runs

```sh
python3 evaluation/evaluate.py grade \
  --baseline /tmp/baseline-verdicts.json \
  --candidate /tmp/candidate-verdicts.json \
  --output /tmp/paired-report.json
```

Both verdict files must cover exactly the same case set. The report contains per-case baseline/candidate scores, score differences, critical failures, process false positives, actual time/turns/tokens/cost and over-budget flags. It also records configurations, declared judges and interpretive limits. Partial cost observations are shown as a known subtotal while total cost remains unknown. The report does not invent missing run results or claim that deterministic tests measured behavior.

Promotion is **blocked** if any of these applies:

- A candidate critical failure occurred, even if the baseline also had it or the average improved.
- Any case score regressed, or a new process false positive appeared.
- Model, effort, tool set, environment, control prompt or budget differs between arms.
- Either arm exceeded its per-case budget.
- The full frozen suite, including holdout, was not evaluated.
- The independently judged average did not improve.

Otherwise the report says `eligible_for_review`. It never automatically promotes a candidate. Review actual costs and time alongside benefit; an expensive or cumbersome change can still be a poor choice even when the mechanical gate is clear. The schema checks cannot detect a false judge declaration, missing transcript content, inaccurate usage measurement, selection bias or a contaminated holdout.

## Promote small lessons, not universal bureaucracy

Use a bounded cycle:

1. Retain an actual failure's raw brief, output and evidence. Identify the narrow mechanism that failed, not a preferred wording.
2. State a scoped hypothesis and make a small targeted skill/reference change. Avoid adding a mandatory gate, research phase, reviewer or extra file for every task.
3. Add a regression case that would expose that failure without revealing its expected answer in the solver packet. Freeze the candidate and test design.
4. Run baseline and candidate under comparable budgets and environment; test the simple-task case for new process false positives.
5. Have an independent evaluator judge the retained raw artifacts, then run a fresh held-out transfer case that was not used for tuning. Where run variation matters, repeat paired runs in balanced order and retain all trials; do not cherry-pick successes.
6. Inspect critical failures first, then per-case benefits, uncertainty and resource costs. Promote only a supported narrow change; revert or revise a change with critical failures or process regressions. If the holdout informed a revision, author another fresh holdout.

Improvement means better task outcomes with appropriate effort. Producing more records, more alternatives or more confident prose is not a success measure. Useful conditional adoption is allowed when evidence is incomplete; verified outcome claims require evidence from the actual relevant scope and environment. This small suite supplies regression pressure, not a guarantee of completeness, optimality or formal engineering compliance.
