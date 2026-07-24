"""Firebase plugin operations."""

from .remoteconfig_inventory import (
    build_remote_config_inventory,
    resolve_project_targets,
)

__all__ = [
    "build_remote_config_inventory",
    "resolve_project_targets",
]
