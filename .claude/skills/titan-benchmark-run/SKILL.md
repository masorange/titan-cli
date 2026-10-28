---
name: titan-benchmark-run
description: Judge a change to Review PR or Respond to PR Comments against the harness benchmarks - provenance checks (real model and code), one variable and two runs, scoring. Use when a run needs scoring or when asking whether a change helped.
disable-model-invocation: false
---

# Titan Benchmark Run

A run of an AI workflow is evidence only if it ran the code and model you think it did,
changed one thing, and is scored against a known reference. Every step below exists because
skipping it has already produced a wrong conclusion in this repo.

## The benchmarks

| Workflow | Domain / lab | Unit | Reference set |
|---|---|---|---|
| Review PR | `harness/review_coverage/benchmark/` | a PR | `references.md` (defect IDs per PR), `README.md` (lab `ab_pipeline.py`, measured runs) |
| Respond to PR Comments | `harness/respond_comments/benchmark/` | a review comment | `references.md` (39 comments of #276), `cases.json`, `score_runs.py` |

Read the benchmark's `README.md` before anything else. It holds the current yardstick and the
re-calibrations, which this skill does not repeat.

## 1. Before launching a variant

1. **One variable.** Name it. If the change touches two things (prompt + model, prompt +
   pipeline), split it: two variables at once has already cost two wrong diagnoses.
2. **Plan at least two runs** on the same input. Run-to-run variance (the same prompt has
   given 0, 4 and 5 findings) is larger than most prompt tweaks.
3. Prefer structural changes over more prompt rules; six single-run prompt tweaks moved
   results less than the noise.
4. Tell the user to **restart `titan-dev` from a fresh terminal** after the change. A running
   TUI keeps the code it imported at launch, and a terminal with `ANTHROPIC_DEFAULT_*_MODEL`
   set silently swaps the model behind an alias.
5. Inputs: a worktree of the PR at the right head, publish nothing.

## 2. Provenance — check before reading any result

Find the run in `~/.local/state/titan/logs/titan.log*` (delegate to the
`titan-log-analyzer` agent with the run id or time when the log is large). Report both:

1. **Model.** `ai_call_cost.model_reported`, not `model_requested`. If `model_reported` is
   empty and `model_costs` lists several models, subagents ran on another model: say which
   share of the cost each took.
2. **Code.** `ai_prompt_built.prompt_last_chars` (or another logged artifact of the change)
   matches the current code. For a review, the deep prompt's tail must end with the
   `{findings, dismissed}` object.

If either does not match, the run does not count. Say so and stop; don't score it "as a
hint".

## 3. Score

**Review PR** — against the PR's section in `review_coverage/benchmark/references.md`:

- important defect IDs found / total, each checked against the reference head, not the prose;
- false positives, verified by reading the code at that head;
- cost (triage + deep) and wall time from `ai_call_cost`;
- compare with the free-form review row as the yardstick.

**Respond to PR Comments** — per comment: `fixed` / `broke` / `wrong` / `replied` /
`nothing`, plus cost and wall time.

```bash
poetry run python harness/respond_comments/benchmark/score_runs.py ~/git/titan-cli \
    [--findings <review findings json> --rev <reviewed head>]
```

Without `--findings` the `broke` column stays blank; that is all that is knowable until a
later review exists.

## 4. Record and conclude

1. Add one row per run to the benchmark's table (`references.md` or the README's measured
   runs), with model, code version (commit or "working tree + <change>"), cost and score.
2. Conclude only from ≥2 valid runs. With one, say plainly "one run is not enough" and what
   the next run is.
3. A result that moves less than the spread already recorded for that input is noise.
4. If the change is kept, record the decision in the domain's `decisions.md` and follow the
   domain `rules.md` for harness state.

## Output

Report, in this order: provenance (model + code, per run), the score rows, the comparison to
the yardstick, and the conclusion or the next run needed.
