"""Pure business logic for the Firebase plugin."""

from .target_operations import (
    TargetResolutionError,
    available_brands,
    available_environments,
    project_id_for_brand,
    resolve_target,
    resolve_targets,
)
from .template_operations import (
    TemplateEditError,
    apply_change,
    build_change,
    condition_names,
    current_raw_value,
    effective_value_type_for,
)

__all__ = [
    "TargetResolutionError",
    "TemplateEditError",
    "apply_change",
    "available_brands",
    "available_environments",
    "build_change",
    "condition_names",
    "current_raw_value",
    "effective_value_type_for",
    "project_id_for_brand",
    "resolve_target",
    "resolve_targets",
]
