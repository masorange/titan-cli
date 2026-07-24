# Docker Workflow Steps

The Docker plugin exposes reusable public workflow steps through `DockerPlugin.get_steps()`.

## Summary

| Step | Group | Used by built-in workflows |
|------|-------|-----------------------------|
| `select_service_group` | Compose | `docker-up` |
| `select_services_to_stop` | Compose | `docker-down` |
| `compose_up` | Compose | `docker-up` |
| `compose_down` | Compose | `docker-down` |
| `compose_status` | Compose | `docker-up`, `docker-down` |
| `build_push_images` | Build | `docker-build-push` |

## Compose

Use these steps to resolve which services to operate on and drive the compose lifecycle.

- `select_service_group`: let the user pick a project-configured `service_groups` entry (or "All services"), saving `docker_services` to the workflow context
- `select_services_to_stop`: checkbox list of every compose service, all checked by default; unchecking one keeps it running. If everything stays checked, resolves to a full `docker compose down`; otherwise stops just the checked subset. Exits early (nothing to do) if the user unchecks everything.
- `compose_up`: start the services in `docker_services` (all services if absent/empty)
- `compose_down`: stop the services in `docker_services` (the whole project if absent/empty)
- `compose_status`: show a table of service state/status/health for `docker_services` (all services if absent/empty), saving `docker_compose_status` to the workflow context

## Build

Use this step to build (and push, per target config) configured Docker images.

- `build_push_images`: build every configured `build_targets` entry, or a single one when `build_target_name` is set in the workflow context, saving `docker_build_results` to the workflow context
