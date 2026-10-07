# Titan CLI - Claude Development Guide

## Session Bootstrap

Before doing any work in this repo, read [`harness/README.md`](harness/README.md) and follow
its Session Start section — it says which domain has focus and what else to read. Don't ask
which task we're on; that file answers it.

## Project Overview

Titan CLI is a Textual TUI that runs YAML-declared workflows over Git, GitHub, Jira, Slack
and other services, with AI integration. Python 3.11+, Textual, gh CLI + GraphQL/REST over
Requests (no PyGithub), Anthropic / OpenAI / Google GenAI SDKs (OpenAI SDK also serves
LiteLLM/OpenAI-compatible gateways).

```
titan_cli/
├── engine/                # Workflow engine
├── core/                  # Config, plugins, workflows, logging, mods
│   └── security/          # THE secrets trust boundary (vault, broker, redaction)
├── ai/                    # Providers, agents, LLM tools
├── ui/tui/                # screens/, widgets/, textual_components.py (step API),
│                          #   textual_workflow_executor.py
└── external_cli/
plugins/
├── titan-plugin-{git,github,jira}/   # Official, 5-layer architecture
├── titan-plugin-slack/               # Official, simplified layout (no models/)
├── titan-plugin-docker/              # Shipped (pyproject entry point); docker_plugin harness domain
└── titan-plugin-{firebase,poeditor}/ # Exist but NOT registered
```

## Guides — read the one that matches the task

| Task | Guide |
|---|---|
| Plugin code (layers, models, mappers, services, ClientResult) | [plugin-architecture.md](.claude/docs/plugin-architecture.md) |
| Business logic in `operations/` | [operations.md](.claude/docs/operations.md) |
| Writing a step (`ctx.textual` API, widgets, scroll rules) | [textual.md](.claude/docs/textual.md) |
| Step conventions (outputs, AI, secrets, no low-level calls) | [workflow-step-rules.md](.claude/docs/workflow-step-rules.md) |
| Workflow YAML, `extends`/hooks, Success/Skip/Error/Exit | [workflows.md](.claude/docs/workflows.md) |
| Secrets | [security.md](.claude/docs/security.md) |
| AI agents | [ai-agents.md](.claude/docs/ai-agents.md) |
| Community plugin installer & dependency rules | [community-plugins.md](.claude/docs/community-plugins.md) |
| Logging | [logging.md](.claude/docs/logging.md) |
| Dev setup, `titan-dev` vs `titan` | [development-setup.md](.claude/docs/development-setup.md), [development-vs-production.md](.claude/docs/development-vs-production.md) |

## Non-Negotiable Rules

**Plugin architecture (official plugins only):** `Steps → Operations → Client → Services → Network`.
- Services return `ClientResult[UIModel]` (`ClientSuccess`/`ClientError`); callers use
  pattern matching, never try/except in steps.
- `Network*` models are faithful to the API (`models/network/rest/` vs `graphql/`);
  `UI*` models are pre-formatted for display; mappers are pure functions between them.
- Operations are pure, UI-agnostic, work with UI models (never dicts), and get unit tests.
  Steps only orchestrate UI: extract all business logic to `operations/`.
- Steps never call low-level client methods (`run_in_worktree`, `run_command`); add a
  service method or operation instead.
- Custom user steps can use any pattern — only `WorkflowContext → WorkflowResult` is required.

**Secrets:** no Titan API ever returns a secret string. Raw secret handling lives only in
`titan_cli/core/security/` (CI-enforced import boundary).
- Steps use `ctx.secret_broker`; plugins get a broker in `initialize(config, broker)`.
  There is no `get()` — use `create_client()`, a session factory, or
  `run_with_secret_stdin` / `run_with_secret_env` / `with_secret_tempfile`.
- Never put a raw secret in `ctx.data` or result metadata (`Success`/`Skip`/`Exit` raise
  `SecretLeakError`). Wrap derived material in `SensitiveValue`, `reveal()` it late.
- Never pass a credential on argv or via the inherited environment.

**Steps:**
- Publish outputs via `Success(metadata={...})`, not by mutating `ctx.data` at return.
- Project/user steps (`.titan/steps/`, `~/.titan/steps/`): the function name must equal
  the YAML `step:` name, no `_step` suffix. Plugin steps map names in `get_steps()`.
- Don't scroll manually; the screen scrolls on step completion. `ctx.textual.scroll_to_end()`
  only for content larger than the screen followed by an interactive widget. Widgets never scroll.
- Docstrings: no doctest examples — tests go in `tests/`.

**Plugin docs:** when you add, remove or change a public client function of an official
plugin (or add a workflow exposing a new capability), update `docs/plugins/<plugin>/`
(`overview.md`, `workflow-steps.md`, `client-api.md`, `built-in-workflows.md`): what it
does, how it's called, required and optional parameters. Generated step references live in
`docs/plugins/generated/` (`sync-plugin-docs` / `validate-plugin-docs` in `.titan/workflows/`).

## Configuration

- Global `~/.titan/config.toml`: AI connections (`[ai]`, `[ai.connections.*]`) and preferences.
- Project `.titan/config.toml`: `[project]` name, `[plugins.<name>] enabled` + plugin config.
- The project root is the **git root** (`git rev-parse --show-toplevel`), falling back to
  cwd. `.titan/config.toml` always lives there, also in monorepos.

## Commands

```bash
make dev-install      # one-time: Poetry venv + ~/.local/bin/titan-dev (runs local code)
titan-dev             # run local codebase; logs: ~/.local/state/titan/logs/titan.log
titan-dev --devtools  # + `textual console` in another terminal for live inspection
make test             # or: poetry run pytest
```

`titan` is the PyPI build; `titan-dev` is for contributors and reflects local changes.
