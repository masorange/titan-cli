---
name: titan-docs-keeper
description: Keep Titan's agent documentation system coherent - decide where a piece of documentation belongs (root AGENTS.md, plugin AGENTS.md, .claude/docs, a skill, an agent, docs/, harness) and audit for misplaced, duplicated, stale or oversized docs. Use when adding or editing AGENTS.md, anything in .claude/docs/, a skill or agent definition, when a rule needs a home, when a doc grew too long, or when asked to review or tidy the documentation.
disable-model-invocation: false
---

# Titan Docs Keeper

The documentation is a loading system: each agent loads the **smallest set** that lets it do
the task. Every piece of text has exactly one home; everything else links to it. This skill
decides the home and finds violations. The map is in
[references/doc-map.md](references/doc-map.md) - read it first, it is the source of truth.

## Modes

Load this skill **before** the first edit to `AGENTS.md`, `.claude/` or `docs/`, not after:
the Stop hook only reviews what is already written.

**Place** - "where does this go?" / you are about to write docs:
1. Ask of the text, in order: Is it loaded by every task and a one-line rule? -> root
   `AGENTS.md`. Specific to one plugin? -> that plugin's `AGENTS.md`. A deep pattern, rule
   rationale or reference an agent reads only for some tasks? -> `.claude/docs/`. An ordered
   procedure to follow? -> a skill. A read-only check? -> an agent. Meant for users or
   public contributors? -> `docs/`. Session state? -> `harness/`. (Full table: doc-map.)
2. **Duplicate test, reported before writing.** `grep -rn` three distinctive terms of the
   fact across `AGENTS.md`, `plugins/*/AGENTS.md`, `.claude/`, `docs/` and say which files
   already state it. One: extend it there. Several: fix that first. None: it has no home yet,
   pick one (doc-map). Elsewhere you only link ([what counts as a copy](references/when-to-write.md)).
3. If it is a **rule** that belongs in a guide but must never be missed, add a one-line
   version to root `AGENTS.md` Non-Negotiable Rules **and** link to the guide section. Root
   holds the rule, the guide holds the why and the examples.

**Review** - after a task (the Stop hook `docs-review-stop-hook.sh` triggers this):
1. Follow [references/when-to-write.md](references/when-to-write.md). Truth check is
   mandatory (fix or delete what the task made false); adding anything must pass its
   write-test and size-test. **"docs: no change" is the normal result.**
2. **Duplicate check:** did the task add a statement another file already makes? Same grep
   as Place step 2; delete or turn into a link whichever is not the home.
3. If any doc file was edited, run the checker (below) and fix errors.
4. Report one line: `docs: no change` / `docs: fixed ...` / `docs: added ... (<test>)`.

**Audit** - "review the docs" / after any edit to the layers above:
1. Run `python3 -I .claude/skills/titan-docs-keeper/scripts/check_docs.py` (mechanical:
   budgets, dead links, unindexed guides/skills, unlisted files, harness refs).
2. Then the judgment pass in [references/audit-checklist.md](references/audit-checklist.md)
   (misplaced content, duplication, contradictions, stale claims, load-path fit).
3. Report findings as `file:line - violation - move to <home>`. Fix only what the user
   asked; propose moves for the rest. Do not commit.

## Rules for the edits themselves

- Root `AGENTS.md` stays within its budget (doc-map): routing tables and one-line rules, no
  tutorials, no code samples beyond a command or a 3-line contract.
- Adding a file to `.claude/docs/` or `.claude/skills/` means adding its row to the matching
  `AGENTS.md` table in the same change. Deleting means removing the row and fixing links.
- Docs describe current behaviour only: no "previously", no dates as freshness claims, no
  deprecation shims (the repo is pre-release: delete, don't deprecate).
- Never cite harness IDs (`D-XXX`, feature IDs) in docs or code comments.
- Generic over project-specific: guides describe Titan; one repo's tuning lives in `.titan/`.
- A doc says **when to read it** in its first lines, so an agent can decide to skip it.
- Splitting beats growing: a guide over its budget is split by task, each part linked from
  the Guides table, rather than trimmed of substance.
- Verify against the code before writing a claim (`grep` the function, flag or path). A stale
  claim in an always-loaded file is worse than a missing one.
