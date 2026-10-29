# Documentation map

Principle: **progressive disclosure with one home per fact.** Always-loaded files route and
state invariants; on-demand files hold depth; nothing is stated twice.

## Layers

| Layer | Loaded | Audience | Holds | Never holds | Budget |
|---|---|---|---|---|---|
| `AGENTS.md` (root) | Every session, automatically | Any agent | Bootstrap pointer, 1-paragraph project overview, skill routing table, guide routing table, **Non-Negotiable Rules as one-liners**, config model, commands | Tutorials, code samples, rationale, per-plugin detail, state, anything only some tasks need | ~130 lines (check_docs warns at 140) |
| `plugins/<p>/AGENTS.md` | When working inside that plugin | Agent in that plugin | What the plugin is, layout deviations, plugin-specific rules, pointer to root and `docs/plugins/<p>/` | Repo-wide rules (link to root), user docs | ~40 lines |
| `.claude/docs/*.md` | On demand, picked from the root Guides table | Agent doing that task | Deep patterns, rule rationale, full API/step references, worked code, pitfalls. One topic per file, starts with "read this when..." | Procedures with ordered steps (-> skill), user-facing walkthroughs (-> `docs/`), session state | ~600 lines; above that, split by task |
| `.claude/skills/<s>/SKILL.md` | When the task matches the description | Agent executing a procedure | The ordered procedure, decision tables, the final checklist; `references/` for detail, `assets/` for templates | Restating guide content (link it), rules that apply outside the procedure | SKILL.md ~120 lines |
| `.claude/agents/*.md` | When invoked | Subagent (read-only reviewers/analyzers) | Role, scope rule, checklist condensed from the guides, report format | The authoritative rules (it reads the guide first; the guide wins on conflict) | ~100 lines |
| `docs/` (mkdocs) | Never by agents by default; read when documenting for users | Users, public contributors | Concepts, getting-started, `docs/plugins/<p>/` (overview, workflow-steps, client-api, built-in-workflows), `docs/plugins/generated/` | Agent-only rules, internal conventions | n/a |
| `harness/` | Session start (root README + focus domain README only) | Agent resuming work | Focus, pending list, current decisions per domain. Rules in `harness/rules.md` | Permanent conventions (-> AGENTS/guides), history (-> git) | Slots per harness-creator |
| `README.md`, `DEVELOPMENT.md` | Humans | Users / human contributors | Install, usage, contributor onboarding | Agent rules | n/a |
| `~/.claude/.../memory/` | Every session (index) | The one user | Personal preferences and corrections | Anything the repo can record (put it in AGENTS.md / guides) | One line per entry |

## Placement tests

1. **Every task needs it, and it is one sentence** -> root `AGENTS.md`.
2. **Only one plugin needs it** -> `plugins/<p>/AGENTS.md`.
3. **Needs examples, rationale or more than ~5 lines** -> `.claude/docs/<topic>.md`; root
   keeps a one-line rule plus link if violating it is costly (see security, scrolling).
4. **It is "do A, then B, then C"** -> skill. The skill links the guides it relies on.
5. **It is "check X and report"** -> agent.
6. **A user would read it** -> `docs/`. A client-API change also requires
   `docs/plugins/<p>/` (AGENTS.md Plugin docs rule).
7. **It changes every session or records what is being done** -> `harness/`, not docs.
8. **It is a personal preference of the user** -> memory, not the repo.

## Single source of truth

| Fact | Home | Others |
|---|---|---|
| Layer rules (Steps -> ... -> Network) | `.claude/docs/plugin-architecture.md` | root: one-line summary; reviewer agent: checklist, guide wins |
| Step conventions | `.claude/docs/workflow-step-rules.md` | root one-liners; skills link |
| `ctx.textual` API | `.claude/docs/textual-api.md` | skills link; no copies of signatures |
| Secrets | `.claude/docs/security.md` | root: 4 invariants only |
| Mod system internals | `.claude/docs/mods.md` | mod authoring in `docs/concepts/writing-mods.md` |
| Workflow YAML | `.claude/docs/workflows.md` (agents), `docs/concepts/workflows.md` (users) | each states its audience; no overlap in prose |
| Dev setup | `.claude/docs/development-setup.md` and `docs/contributing/development-setup.md` | pick one canonical; the other links |

## Coherence invariants (what the audit enforces)

- Every `.claude/docs/*.md` is in the root Guides table; every skill is in the Skills table;
  every table row points at a file that exists.
- Every relative link and backticked repo path resolves.
- Root and plugin `AGENTS.md` are within budget; plugin ones link to the root.
- An always-loaded file contains no content a single task needs.
- A rule appears in full in exactly one place.
- Skills and agents reference guides instead of copying them; when they must condense
  (agents), the guide is declared authoritative.
- No harness IDs, no dated freshness claims, no deprecation narrative.
