# AGENTS.md - Titan GitHub Plugin

Rules specific to `titan-plugin-github`. The repo-wide rules and guides are in the root
[`AGENTS.md`](../../AGENTS.md); user-facing docs in [`docs/plugins/github/`](../../docs/plugins/github/).

## What it is

GitHub integration: PRs, issues, releases, reviews and review threads, merge queues. Depends
on the `git` plugin (repo owner/name are auto-detected from its remote when not configured).

## Layout

5-layer: `steps/ → operations/ → clients/github_client.py → clients/services/ →
clients/network/` (`gh_network.py` for the gh CLI/REST, `graphql_network.py` +
`graphql_queries.py` for GraphQL). `models/network/{rest,graphql}` mirror each API
separately. Also: `agents/` (PR and issue generators, configured by `config/pr_agent.toml`),
`widgets/` (comment views), the `github` mod (`mods/github/`), `messages.py`.

## Plugin-specific rules

- No PyGithub: everything goes through `gh` or GraphQL/REST over the network layer.
- Auth is the user's `gh` login; the plugin holds no token.
- Review PR and Respond to PR Comments are measured, not eyeballed: any change to their
  prompts or pipeline is judged against the harness benchmarks (`titan-benchmark-run` skill).
- A review session runs in a worktree of an untrusted PR: keep `--setting-sources user`
  and the tool restrictions; the prompt points the session at the PR's `AGENTS.md` files.
- Config: `GitHubPluginConfig` in `titan_cli/core/plugins/models.py`.
- Tests: `tests/{services,operations,unit}`.
