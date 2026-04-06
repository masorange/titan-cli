"""
Version States - Definitions and helpers for App Store version states.

Provides clear categorization of version states and helper functions
to determine what operations are allowed.
"""

from enum import StrEnum
from typing import Set


class VersionState(StrEnum):
    """App Store Connect version states."""

    # Editable states
    PREPARE_FOR_SUBMISSION = "PREPARE_FOR_SUBMISSION"  # Initial state - can edit everything
    DEVELOPER_REJECTED = "DEVELOPER_REJECTED"          # Developer rejected - can re-edit

    # Locked states (in review or published)
    WAITING_FOR_REVIEW = "WAITING_FOR_REVIEW"                 # Submitted, waiting for review
    IN_REVIEW = "IN_REVIEW"                                   # Apple is reviewing
    PENDING_DEVELOPER_RELEASE = "PENDING_DEVELOPER_RELEASE"   # Approved, waiting for release
    READY_FOR_SALE = "READY_FOR_SALE"                         # Published and live (PRODUCTION)
    PROCESSING_FOR_APP_STORE = "PROCESSING_FOR_APP_STORE"     # Apple is processing

    # Rejected states
    REJECTED = "REJECTED"                                     # Rejected by Apple
    METADATA_REJECTED = "METADATA_REJECTED"                   # Only metadata rejected
    DEVELOPER_REMOVED_FROM_SALE = "DEVELOPER_REMOVED_FROM_SALE"  # Removed by developer


# States that allow full editing (metadata, builds, release notes, submission)
EDITABLE_STATES: Set[VersionState] = {
    VersionState.PREPARE_FOR_SUBMISSION,
    VersionState.DEVELOPER_REJECTED,
}

# States that are locked (already submitted or in review process)
LOCKED_STATES: Set[VersionState] = {
    VersionState.WAITING_FOR_REVIEW,
    VersionState.IN_REVIEW,
    VersionState.PENDING_DEVELOPER_RELEASE,
    VersionState.READY_FOR_SALE,
    VersionState.PROCESSING_FOR_APP_STORE,
}

# States that indicate rejection (might need new version)
REJECTED_STATES: Set[VersionState] = {
    VersionState.REJECTED,
    VersionState.METADATA_REJECTED,
    VersionState.DEVELOPER_REMOVED_FROM_SALE,
}

# All non-editable states combined
NON_EDITABLE_STATES: Set[VersionState] = LOCKED_STATES | REJECTED_STATES


def is_editable(state: str | VersionState) -> bool:
    """
    Check if a version state allows editing.

    Args:
        state: Version state (string or enum)

    Returns:
        True if version can be edited (metadata, builds, release notes)
    """
    if isinstance(state, str):
        state = VersionState(state)
    return state in EDITABLE_STATES


def is_locked(state: str | VersionState) -> bool:
    """
    Check if a version state is locked (in review or published).

    Args:
        state: Version state (string or enum)

    Returns:
        True if version is locked and cannot be modified
    """
    if isinstance(state, str):
        state = VersionState(state)
    return state in LOCKED_STATES


def is_rejected(state: str | VersionState) -> bool:
    """
    Check if a version was rejected.

    Args:
        state: Version state (string or enum)

    Returns:
        True if version was rejected by Apple or developer
    """
    if isinstance(state, str):
        state = VersionState(state)
    return state in REJECTED_STATES


def can_submit(state: str | VersionState) -> bool:
    """
    Check if a version can be submitted for review.

    Args:
        state: Version state (string or enum)

    Returns:
        True if version can be submitted (only PREPARE_FOR_SUBMISSION)
    """
    if isinstance(state, str):
        state = VersionState(state)
    return state == VersionState.PREPARE_FOR_SUBMISSION


def can_update_metadata(state: str | VersionState) -> bool:
    """
    Check if version metadata can be updated.

    Args:
        state: Version state (string or enum)

    Returns:
        True if metadata (What's New, etc.) can be updated
    """
    if isinstance(state, str):
        state = VersionState(state)
    return state in EDITABLE_STATES or state == VersionState.METADATA_REJECTED


def get_state_description(state: str | VersionState) -> str:
    """
    Get a human-readable description of the state.

    Args:
        state: Version state (string or enum)

    Returns:
        User-friendly description with emoji
    """
    if isinstance(state, str):
        try:
            state = VersionState(state)
        except ValueError:
            return f"❓ Unknown state: {state}"

    descriptions = {
        VersionState.PREPARE_FOR_SUBMISSION: "⚪ Ready to configure and submit",
        VersionState.DEVELOPER_REJECTED: "🔄 Developer rejected - can edit and resubmit",
        VersionState.WAITING_FOR_REVIEW: "🟡 Waiting for Apple review",
        VersionState.IN_REVIEW: "🔵 Being reviewed by Apple",
        VersionState.PENDING_DEVELOPER_RELEASE: "🟢 Approved - pending release",
        VersionState.READY_FOR_SALE: "✅ Published and live",
        VersionState.PROCESSING_FOR_APP_STORE: "⏳ Processing in App Store",
        VersionState.REJECTED: "🔴 Rejected by Apple",
        VersionState.METADATA_REJECTED: "🟠 Metadata rejected - can fix and resubmit",
        VersionState.DEVELOPER_REMOVED_FROM_SALE: "⚫ Removed from sale by developer",
    }
    return descriptions.get(state, f"❓ Unknown state: {state}")


def get_state_category(state: str | VersionState) -> str:
    """
    Get the category of a state.

    Args:
        state: Version state (string or enum)

    Returns:
        Category: "editable", "locked", "rejected", or "unknown"
    """
    if isinstance(state, str):
        try:
            state = VersionState(state)
        except ValueError:
            return "unknown"

    if state in EDITABLE_STATES:
        return "editable"
    elif state in LOCKED_STATES:
        return "locked"
    elif state in REJECTED_STATES:
        return "rejected"
    else:
        return "unknown"


__all__ = [
    "VersionState",
    "EDITABLE_STATES",
    "LOCKED_STATES",
    "REJECTED_STATES",
    "NON_EDITABLE_STATES",
    "is_editable",
    "is_locked",
    "is_rejected",
    "can_submit",
    "can_update_metadata",
    "get_state_description",
    "get_state_category",
]
