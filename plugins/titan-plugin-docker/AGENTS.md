# AGENTS.md - Titan Docker Plugin

Rules specific to `titan-plugin-docker`. The repo-wide rules and guides are in the root
[`AGENTS.md`](../../AGENTS.md); user-facing docs in [`docs/plugins/docker/`](../../docs/plugins/docker/).

## What it is

Docker Compose lifecycle (`up` / `down` / `status`), image build and push with
`docker buildx` per configured `build_targets`, and cleanup (containers, prune, disk usage).

## Layout

5-layer: `steps/ → operations/ → clients/docker_client.py → clients/services/ →
clients/network/docker_network.py`, with `models/{network,view,mappers}`. Workflows:
`docker-up`, `docker-down`, `docker-status`, `docker-build-push`, `docker-clean-containers`,
`docker-prune`.

## Plugin-specific rules

- Generic by design: no project's service or image names anywhere in this package. They
  always come from `DockerPluginConfig` (`service_groups`, `build_targets`) in
  `titan_cli/core/plugins/models.py`. `service_groups` is an open dictionary with no
  reserved names.
- No `messages.py`: user-facing strings are written at their call site.
- Steps never call `subprocess` or `DockerNetwork`; they go through `ctx.docker` and
  `operations/`.
- Tests: `tests/{clients,models,operations}`, `test_plugin.py`.
