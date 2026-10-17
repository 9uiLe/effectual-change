# Maintaining the harness

- Preserve the original outcome and human constraints. Decompositions and mechanisms are hypotheses, not new user goals.
- Skill behavior, structural checks, installer behavior and empirical quality are different contracts. Do not describe deterministic checks as proof of better decisions.
- Keep the entry skill small. Put conditional instructions in the relevant focused skill or reference, and maintain sibling links with the installer.
- A runtime record change needs behavioral tests at the CLI or record-check boundary and an update to `references/record-format.md`.
- A skill change that claims better decisions needs paired behavioral evidence described in `docs/evaluation.md`. Evaluation fixtures are synthetic; never publish test-generated judgments as real results.
- Keep evaluator rubrics out of solver packets. Do not tune against a holdout and continue calling it fresh.
- Validate with the three commands in README. Preserve LICENSE and existing Git history.
