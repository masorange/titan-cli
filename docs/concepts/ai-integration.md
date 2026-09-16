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
(Claude Code, Gemini CLI, Codex, OpenCode, Antigravity, Grok). Which one it runs is a
single global choice, and each CLI can be pinned to a specific model:

```toml
[ai]
default_cli = "opencode"

[ai.cli_models]
# One entry per CLI: an identifier only means something to the CLI that accepts it,
# so switching CLIs never carries the previous one's model over.
opencode = "anthropic/claude-sonnet-5"
claude = "opus"
```

Both are editable from the TUI without leaving the screen you are on:

| Key | Changes |
|---|---|
| `F2` | Which CLI Titan runs. `M` on a highlighted CLI sets that CLI's model instead |
| `F3` | The model of the default connection, listed from the gateway |

The status bar shows both, labelled with the key that changes them:

```text
 feat/my-branch   F2 opencode / claude-sonnet-5   F3 work-gateway / gpt-5   my-project
```

Choosing a model for a CLI does **not** switch to it — pinning a model on a CLI you are
not using is a normal thing to do, and switching silently would change what runs your
next workflow. The CLI section of AI Configuration offers the same two actions.

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

1. A model the step asks for explicitly — it needs that model for its prompt
2. The model pinned for the resolved CLI
3. Nothing: the CLI uses its own default

Pinned models apply to both uses of a CLI: unattended runs (generating a commit message)
and interactive sessions Titan launches for you.
