# AI Integration

!!! note "Coming soon"
    Detailed AI integration documentation is being written.

---

## Overview

Titan supports two AI providers:

- **Anthropic Claude** (Sonnet, Opus, Haiku)
- **Google Gemini** (Pro, Flash)

Configure your provider in `~/.titan/config.toml`:

```toml
[ai.providers.default]
name = "Claude"
type = "individual"
provider = "anthropic"
model = "claude-sonnet-4-5"

[ai]
default = "default"
```

Titan stores your API key securely in the OS keyring — you'll be prompted for it on first use.

AI is **optional**. All built-in workflows work without it; AI steps are simply skipped if no provider is configured.
