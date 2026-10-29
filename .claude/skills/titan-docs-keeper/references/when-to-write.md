# When to write documentation (and when not to)

Documentation has a cost: every line is read by agents, can go stale, and competes for
attention with the lines that matter. Default to **no change**. Write only when a test below
passes, and write the least that satisfies it.

## Review: after a task

1. **Truth check (always).** For what the task changed, find docs that mention it
   (`grep -rn` the renamed/removed/changed function, flag, path, step or workflow name across
   `AGENTS.md`, `plugins/*/AGENTS.md`, `.claude/`, `docs/`). Anything now false is **fixed or
   deleted**, in the same place it lives. This is the only mandatory outcome.
2. **Write-test (only if it passes).** Add or extend a doc only if at least one holds:
   - **Costly to rediscover:** a future agent would likely get it wrong, or need several tool
     calls to find it, and the code does not say it (hidden constraint, ordering trap,
     non-obvious why, a gotcha that already bit someone).
   - **New public surface:** a new/changed public client function, workflow step, mod API,
     config key or CLI flag that others call (also required by AGENTS.md Plugin docs rule).
   - **New rule the user stated** for how the repo works from now on.
   - **A pattern now repeated** (3rd occurrence) that deserves a recipe.
3. **Size-test (before writing).** Prefer, in order: edit an existing line > replace a
   paragraph with a tighter one > add a line to an existing section > add a section > add a
   file. Adding a file or a root `AGENTS.md` line needs a reason the placement tests in
   [doc-map.md](doc-map.md) force it. If the target is over budget, make room (tighten or
   split) in the same change.

## Never write

- What the code or its names already say; signatures copied from source.
- What the diff or git history records: what changed, why this PR, fix narratives.
- Task progress, plans, "currently", dates as freshness claims (-> `harness/`).
- Internal refactors, bug fixes and tests that leave behaviour and public surface unchanged.
- A second copy of a rule that has a home (link instead).
- Speculative or "might be useful" content; examples that restate prose already there.
- Personal user preferences (-> memory).

## Outcome report

One line: `docs: no change` (most tasks), or `docs: fixed <file> (stale <thing>)`, or
`docs: added <what> to <file> (<which write-test>)`. Never a silent edit.
