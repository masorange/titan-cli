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
    parse_project_ids,
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
    "build_change",
    "condition_names",
    "current_raw_value",
    "describe_outcomes",
    "describe_plan",
    "effective_value_type_for",
    "outcome_summary",
    "parse_project_ids",
    "plan_summary",
    "publishable_entries",
    "resolve_target",
    "resolve_targets",
    "select_entries",
]
