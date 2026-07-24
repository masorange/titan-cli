# Docker Client API

The Docker plugin adds Docker Compose lifecycle management and image build/push
operations to Titan through a high-level client and reusable workflows.

This page documents the plugin from a functional point of view, while also
showing how each capability is called and which parameters it needs.

---

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

---

## Accessing the client

In Titan code, the public entry point is the Docker plugin client:

```python
docker_plugin = config.registry.get_plugin("docker")
client = docker_plugin.get_client()
```

The client returns `ClientResult[...]` values. In practice, this means each call can succeed with data or return an error result.

The client also carries the project's configured `service_groups` and
`build_targets` as plain attributes (`client.service_groups`,
`client.build_targets`), so steps and operations can resolve them without a
separate config lookup.

---

## Compose operations

### Start services

Starts compose services in the background.

**Call:**

```python
client.compose_up(services=["db", "cache"])
```

**Parameters:**

- `services` (list of str, optional): Service names to start. Omit or pass an empty list to start every service in the compose file.
- `detach` (bool, optional): Run containers in the background. Defaults to `True`.

### Stop services

Stops compose services.

**Call:**

```python
client.compose_down(services=["db", "cache"])
```

**Parameters:**

- `services` (list of str, optional): Service names to stop. Omit or pass an empty list to stop (`down`) the whole project; a non-empty list runs `stop` on just those services.

### Get compose status

Returns the state of compose services (running/exited, health, status text).

**Call:**

```python
client.compose_status(services=["db"])
```

**Parameters:**

- `services` (list of str, optional): Service names to inspect. Omit or pass an empty list to inspect every service.

---

## Build operations

### Build (and optionally push) an image

Builds a single configured image with `docker buildx build`, covering both
single-platform and multi-platform builds through the same code path.

**Call:**

```python
from titan_cli.core.plugins.models import DockerBuildTargetConfig

target = DockerBuildTargetConfig(
    name="backend",
    dockerfile="packages/backend/Dockerfile",
    context=".",
    image="ghcr.io/org/app-backend",
    target="production",
    platforms="linux/amd64,linux/arm64",
    tag="latest",
    push=True,
)
client.build_target(target)
```

**Parameters:**

- `target` (`DockerBuildTargetConfig`, required): the build target to build. Typically resolved from `client.build_targets` (project configuration) rather than constructed by hand.
