"""Operations layer - pure business logic."""

from .project_operations import calculate_overall_progress, find_project_by_name

__all__ = [
    "find_project_by_name",
    "calculate_overall_progress",
]
