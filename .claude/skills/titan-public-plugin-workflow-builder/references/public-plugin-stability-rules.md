# Public Plugin Stability Rules

For distributed plugins, prefer:

1. stable workflow names
2. stable exposed step names
3. clear category-based organization
4. reusable client APIs where justified
5. minimal breaking changes to plugin consumers

## Host contract

1. `titan-cli` is the host, never an install dependency: declare it `optional = true` with
   a real range and a `host` extra. Don't delete the declaration — Titan reads it to decide
   whether the running version may load the plugin.
2. Libraries Titan also ships (`requests`) resolve to Titan's version; pin compatible ranges.
3. Import only public `titan_cli.*` APIs. Never `keyring` or `titan_cli.core.security._vault`
   (the loader's static scan flags them).
4. Credentials come from the broker passed to `initialize(config, broker)`; AI steps use
   `declare_ai_usage` + `ctx.ai_router` (`titan-workflow-architecture` →
   `references/step-contracts.md`).

Full rules: `.claude/docs/community-plugins.md` in titan-cli.
