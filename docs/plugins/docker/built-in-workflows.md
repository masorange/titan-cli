# Docker Built-in Workflows

The Docker plugin currently ships three workflows: two for the compose lifecycle, one for building/pushing images.

## `docker-up`

Starts Docker Compose services (all services, or a project-configured `service_groups` entry) and shows their status.

**Source workflow:** `plugins/titan-plugin-docker/titan_plugin_docker/workflows/docker-up.yaml`

### Default flow

1. `docker.select_service_group`
2. `docker.compose_up`
3. `docker.compose_status`

### Related public steps

- `select_service_group`
- `compose_up`
- `compose_status`

## `docker-down`

Stops Docker Compose services. Presents every service as a checked-by-default
checklist - unchecking a service keeps it running. Leaving everything checked
runs a full `docker compose down`; unchecking some services stops only the
rest. Unchecking everything exits without stopping anything.

**Source workflow:** `plugins/titan-plugin-docker/titan_plugin_docker/workflows/docker-down.yaml`

### Default flow

1. `docker.select_services_to_stop`
2. `docker.compose_down`
3. `docker.compose_status`

### Related public steps

- `select_services_to_stop`
- `compose_down`
- `compose_status`

## `docker-build-push`

Builds (and pushes, per target config) every Docker image configured for the project.

**Source workflow:** `plugins/titan-plugin-docker/titan_plugin_docker/workflows/docker-build-push.yaml`

### Default flow

1. `docker.build_push_images`

### Related public steps

- `build_push_images`
