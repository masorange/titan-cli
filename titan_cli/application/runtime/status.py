"""Internal run session state enums."""

from enum import StrEnum


class RunSessionStatus(StrEnum):
    """Lifecycle states for the in-process run session."""

    CREATED = "created"
    PENDING = "pending"
    RUNNING = "running"
    WAITING_FOR_INPUT = "waiting_for_input"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
