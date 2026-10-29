# Audit checklist (judgment pass)

Run `scripts/check_docs.py` first; this covers what a script cannot. Scope: the files the
change touched plus their neighbours in the same layer. For a full audit, all layers.

## 1. Misplaced content (per doc-map placement tests)

- Root `AGENTS.md`: any paragraph a single task needs? Code block longer than 3 lines?
  A rule with a "why" paragraph? -> move the depth to the guide, leave the one-liner.
- A guide containing "step 1, step 2..." procedure for a recurring task -> candidate skill.
- A skill restating a guide's rules or API signatures -> replace with a link.
- A guide written for users (tutorial voice, "your first...") -> `docs/`.
- A user doc with internal-only conventions -> `.claude/docs/`.
- Session/progress text in AGENTS.md or guides -> `harness/`.
- A plugin `AGENTS.md` repeating a root rule -> delete, link.

## 2. Duplication and contradiction

- Pick 5 distinctive terms from the changed text and `grep -rn` them across
  `AGENTS.md`, `plugins/*/AGENTS.md`, `.claude/`, `docs/`. Two full statements of one rule
  = duplication; two different statements = contradiction (report which is right by checking
  the code).
- The `titan-architecture-reviewer` checklist vs `workflow-step-rules.md` /
  `plugin-architecture.md`: same rules, guide wins.

## 3. Staleness

- Every named function, flag, file, command, workflow name: does it exist? (`grep`, `ls`.)
- Counts and lists ("official plugins: git, github, jira") vs `pyproject.toml` entry points
  and `plugins/`.
- Commands in `Commands` section run as written (Makefile targets exist).

## 4. Load-path fit

For three realistic tasks (e.g. "add a step to the github plugin", "build a mod pane",
"fix a logging bug"), walk what an agent loads: root -> table row -> guide. Does it reach
every rule it needs, without reading unrelated 1000-line files? If a task needs a rule that
no table row leads to, or a guide mixes two unrelated tasks, fix the routing or split.

- A guide's first lines state when to read it.
- A guide over budget has natural task seams -> propose the split.
- Skill `description` fields name triggers precisely and do not overlap with a sibling.

## 5. Report format

```
<file>:<line> - <violation> - <move to / fix>
```

Group by severity: contradictions and stale claims in always-loaded files first, then
misplacements, then duplication, then size. End with the proposed edits; apply only what the
user asked for.
