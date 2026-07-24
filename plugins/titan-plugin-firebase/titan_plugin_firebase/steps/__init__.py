"""Public Firebase workflow steps."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_STEP_EXPORTS = {
    "execute_firebase_login_step": ".login_step",
    "execute_firebase_status_step": ".login_step",
    "execute_firebase_remoteconfig_get_step": ".remoteconfig_get_step",
    "execute_firebase_remoteconfig_inventory_step": ".remoteconfig_inventory_step",
}

__all__ = list(_STEP_EXPORTS)


def __getattr__(name: str) -> Any:
    """Lazily expose public step functions without eager cross-step imports."""
    module_name = _STEP_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    value = getattr(import_module(module_name, __name__), name)
    globals()[name] = value
    return value
