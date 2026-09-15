"""Pure business logic for the Firebase plugin."""

from .target_operations import (
    TargetResolutionError,
    available_brands,
    available_environments,
    project_id_for_brand,
    resolve_target,
    resolve_targets,
)

__all__ = [
    "TargetResolutionError",
    "available_brands",
    "available_environments",
    "project_id_for_brand",
    "resolve_target",
    "resolve_targets",
]
