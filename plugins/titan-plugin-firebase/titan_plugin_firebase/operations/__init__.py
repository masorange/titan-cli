"""Pure business logic for the Firebase plugin."""

from .fanout_operations import (
    describe_outcomes,
    describe_plan,
    outcome_summary,
    plan_summary,
    publishable_entries,
    select_entries,
)
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
    "describe_outcomes",
    "describe_plan",
    "available_brands",
    "available_environments",
    "build_change",
    "condition_names",
    "current_raw_value",
    "effective_value_type_for",
    "outcome_summary",
    "plan_summary",
    "project_id_for_brand",
    "publishable_entries",
    "resolve_target",
    "resolve_targets",
    "select_entries",
]
