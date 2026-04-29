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
