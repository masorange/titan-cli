# AI Integration

## Overview

Titan supports AI through configurable **connections**:

- **Direct Provider** connections for:
  - Anthropic
  - OpenAI
  - Gemini
- **LLM Gateway** connections for OpenAI-compatible endpoints such as LiteLLM

Configure AI in `~/.titan/config.toml`:

```toml
[ai]
default_connection = "default"

[ai.connections.default]
name = "My Anthropic"
kind = "direct_provider"
provider = "anthropic"
default_model = "claude-sonnet-4-5"
```

Titan stores your API key securely in the OS keyring — you'll be prompted for it on first use.

AI is **optional**. All built-in workflows work without it; AI steps are skipped if no AI connection is configured.

Workflow authors can reuse AI-powered behavior through built-in core steps such as `plugin: core` / `ai_code_assistant`. See [Workflow Steps](workflow-steps.md#built-in-core-steps).

## Connection Types

### Direct Provider

Use this when Titan talks directly to the vendor API.

```toml
[ai.connections.personal-openai]
name = "Personal OpenAI"
kind = "direct_provider"
provider = "openai"
default_model = "gpt-5"
```

### LLM Gateway

Use this when a single endpoint exposes one or more models through an OpenAI-compatible API.

```toml
[ai.connections.work-gateway]
name = "Work Gateway"
kind = "gateway"
gateway_type = "openai_compatible"
base_url = "https://llm.company.com"
default_model = "claude-sonnet-4-5"
```

## AI CLIs

Besides connections, Titan can route work to an AI CLI already installed on your machine
(Claude Code, Gemini CLI, Codex, OpenCode, Antigravity, Grok). One is the global default,
and each CLI can be pinned to a specific model:

```toml
[ai]
default_cli = "opencode"

[ai.cli_models]
# One entry per CLI: an identifier only means something to the CLI that accepts it,
# so switching CLIs never carries the previous one's model over.
opencode = "anthropic/claude-sonnet-5"
claude = "opus"
```

Both are editable from the TUI without leaving the screen you are on: `F2` opens the
picker loaded with CLIs, `F3` with connections. It is the same picker — they are the same
question asked of different transports — so the keys are the same in both.

It is a **form**: choosing a row selects it, and **nothing is written until you accept**.

| Key | Does |
|---|---|
| `Enter` | Select the highlighted row. The modal stays open and focus moves to **Save** |
| `M` | Choose that row's model, then come back here with it pending |
| `Save` | Apply what you composed — the instance, the model, or both |
| `S` | Apply the same, **for this session only**, writing nothing |
| `C` | Clear an active session override |
| `Esc` | Cancel. Nothing is written, the model included |

The line above the buttons says what accepting would do, and for how long:

```text
Will apply: codex / gpt-5.6-terra  —  Save to keep it, S for this session only
```

Because the model is part of the composition, you can set a CLI **and** its model in one
pass — and apply both to the session only, which is the one way to try a model without
writing it down. Choosing another row forgets a model you had picked for the previous
one: a model identifier only means something to the instance it was chosen for.

The status bar shows both, labelled with the key that changes them:

```text
 feat/my-branch   F2: opencode / claude-sonnet-5   F3: work-gateway / gpt-5   my-project
```

A `*` after a cell means a **session override** is in force there: something you chose
with `S` for now only, which outranks your saved settings and is forgotten when Titan
exits. Nothing was written to your config. Each key reports and clears only its own
half — `F3` will not tell you about a CLI override, because you could not act on it
from there.

Each picker also tells you how many tasks pin their own CLI or connection and so will not
follow a **Save** — though `S` still reaches them, because a session override outranks a
pin. A task that deliberately ignores `F2` is otherwise indistinguishable from a key that
did not work.

To change a CLI's model without switching to that CLI, use the CLI section of **AI
Configuration**: `F2` answers "what runs now", and accepting there applies the row you
selected.

## Per-task overrides

A task ("commit messages", "code review findings") chooses which KIND of AI serves it —
a remote connection, an automatic CLI, an interactive CLI, or off — in the **AI per task**
section of AI Configuration. Each row can also pin the instance and the model that serve
that one task:

```toml
[ai.preferences.tasks.code_review_findings]
provider = "cli_headless"
cli = "claude"           # instead of default_cli
model = "opus"           # instead of cli_models.claude

[ai.preferences.tasks.commit_message]
provider = "cli_headless"
# no cli, no model: follows the global default, including changes made with F2
```

A remote task pins `connection` instead of `cli`, and its `model` overrides that
connection's `default_model`. Pins are **sparse**: anything you leave out is inherited, so
one edit to the global default still moves every task that has not opted out.

The row's **CLI**/**Connection** and **Model** buttons open the same form `F2` and `F3`
use, minus the session scope — a task pin is permanent by definition — plus a **Follow the
default** row, which is how you undo a pin without the row's **Clear** taking the provider
kind with it. Pinning a model also pins the instance it was chosen for, because the list
you were offered was that instance's.

A pin is not a guarantee that something exists. A pinned CLI that is not installed, or a
connection that was renamed, is reported by name — Titan never quietly runs a different
one.

**Changing a task's CLI or connection forgets its pinned model**, and says so. A model
identifier only means something to the instance it was chosen for: `opus` is a Claude
alias, and carrying it over to Codex would hand it a flag it rejects.

### Where the model list comes from

Each CLI answers "what can you run?" its own way, and some do not answer at all:
`opencode`, `agy` and `grok` have a listing command Titan shells out to; `claude`
publishes stable aliases (`opus`, `sonnet`, `haiku`); `gemini` and `codex` publish
nothing. Typing an identifier by hand is always available, so a model newer than Titan
knows about is never out of reach. A listing that fails — not logged in, offline — falls
back to that same entry rather than blocking.

The identifier is stored and passed through verbatim, after whatever model flag that CLI
uses (`--model`, `-m`). Titan does not validate it: only the CLI knows what it accepts,
and one it rejects is its own error message.

### Precedence

Highest wins, for both which instance runs and which model it runs:

1. **What the step asks for explicitly** — a step passing a model needs that model for its
   prompt (a code review explores on a cheap model and synthesises on an expensive one),
   so it outranks even a key you just pressed
2. **A session override** — what you chose with `S` from `F2`/`F3`, for now only
3. **The task's own pin** — the CLI, connection or model set on its row
4. **The global default** — `default_cli` / `default_connection`, and the model that
   belongs to the resolved instance (`cli_models[cli]`, or the connection's
   `default_model`)
5. **Nothing**: the CLI or connection uses its own default

If a step you expected to follow `F3` does not, rung 1 is the usual reason. Every AI step
shows which AI answered it, model included, so you can see which rung won.

Pinned models apply to both uses of a CLI: unattended runs (generating a commit message)
and interactive sessions Titan launches for you.
