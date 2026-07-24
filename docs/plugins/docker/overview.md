# Docker Plugin

The Docker plugin provides Titan's Docker Compose lifecycle and image build/push
surface. It exposes:

- a high-level `DockerClient` for direct use from Titan code
- reusable workflow `steps` such as `compose_up`, `compose_status`, and `build_push_images`
- the built-in `docker-up` and `docker-build-push` workflows

The plugin has no built-in notion of any specific project's services or
images: `service_groups` (named groups of compose service names) and
`build_targets` (buildable images) are entirely defined by each project's
`.titan/config.toml`.

## Requirements

To use the Docker plugin in a project:

- Enable the `docker` plugin in `.titan/config.toml`
- Install Docker (with the `compose` and `buildx` CLI plugins) and make sure it is available in `PATH`

Example project configuration:

```toml
[plugins.docker]
enabled = true

[plugins.docker.config]
compose_file = "docker-compose.yml"

[plugins.docker.config.service_groups]
infra = ["db", "cache"]

[[plugins.docker.config.build_targets]]
name = "backend"
dockerfile = "packages/backend/Dockerfile"
context = "."
image = "ghcr.io/org/app-backend"
target = "production"
push = true
```

## Public surfaces

- [Client API](./client-api.md): direct Python methods exposed by `DockerClient`
- [Workflow Steps](./workflow-steps.md): public reusable workflow steps grouped by functionality
- [Built-in Workflows](./built-in-workflows.md): workflows shipped by the plugin

## Accessing the client

In Titan code, the public entry point is the Docker plugin client:

```python
docker_plugin = config.registry.get_plugin("docker")
client = docker_plugin.get_client()
```

The client returns `ClientResult[...]` values. In practice, this means each call can succeed with data or return an error result.

## Public workflow steps

The Docker plugin exposes these reusable public steps through `get_steps()`:

- `select_service_group`
- `select_services_to_stop`
- `compose_up`
- `compose_down`
- `compose_status`
- `build_push_images`
- `disk_usage`
- `select_prune_targets`
- `prune_resources`
- `select_containers_to_remove`
- `remove_containers`
