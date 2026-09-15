"""
Building the template a publish sends.

Remote Config replaces the whole template on every publish, so a change to one
parameter is a read-modify-write over the entire payload: anything dropped
here is deleted from the project. These functions take the raw payload the API
returned and return a new one, touching exactly the value being changed.

Pure functions: no context, no UI, no network.
"""

from __future__ import annotations

import copy
from typing import Any, Optional

from ..models.values import (
    RemoteConfigValueError,
    RemoteConfigValueType,
    infer_value_type,
    normalize_value_type,
    serialize_value,
)
from ..models.view import UIRemoteConfigChange


class TemplateEditError(ValueError):
    """Raised when a requested edit cannot be applied to a template."""


def condition_names(payload: dict[str, Any]) -> list[str]:
    """Return the condition names declared by a raw template payload."""
    conditions = payload.get("conditions")
    if not isinstance(conditions, list):
        return []
    return [
        str(condition["name"])
        for condition in conditions
        if isinstance(condition, dict) and condition.get("name")
    ]


def effective_value_type_for(
    payload: dict[str, Any],
    key: str,
) -> RemoteConfigValueType:
    """
    Resolve the type of a parameter in a raw payload.

    The declared `valueType` wins; otherwise it is inferred from the values
    present, the same way the read path does it.
    """
    parameter = _parameter(payload, key)
    declared = normalize_value_type(parameter.get("valueType"))
    if declared != RemoteConfigValueType.UNKNOWN:
        return declared

    for raw_value in _raw_values(parameter):
        inferred = infer_value_type(raw_value)
        if inferred != RemoteConfigValueType.UNKNOWN:
            return inferred
    return RemoteConfigValueType.UNKNOWN


def current_raw_value(
    payload: dict[str, Any],
    key: str,
    condition: Optional[str] = None,
) -> tuple[Optional[str], bool]:
    """
    Return the value stored for one target.

    Returns:
        The raw value and whether it was inherited from the default because the
        condition has no value of its own.
    """
    parameter = _parameter(payload, key)
    if condition is None:
        return _value_of(parameter.get("defaultValue")), False

    conditional = parameter.get("conditionalValues")
    if isinstance(conditional, dict) and condition in conditional:
        return _value_of(conditional[condition]), False
    return _value_of(parameter.get("defaultValue")), True


def build_change(
    payload: dict[str, Any],
    key: str,
    new_value: str,
    condition: Optional[str] = None,
) -> UIRemoteConfigChange:
    """
    Validate a requested edit and describe it, without applying it.

    Raises:
        TemplateEditError: If the parameter or condition does not exist.
        RemoteConfigValueError: If the value does not match the parameter type.
    """
    _parameter(payload, key)
    if condition is not None and condition not in condition_names(payload):
        raise TemplateEditError(
            f"La condición '{condition}' no existe en la plantilla. "
            "Créala en la consola de Firebase antes de escribir sobre ella."
        )

    value_type = effective_value_type_for(payload, key)
    serialized = serialize_value(new_value, value_type)
    old_value, inherited = current_raw_value(payload, key, condition)

    return UIRemoteConfigChange(
        key=key,
        condition=condition,
        value_type=value_type,
        old_raw_value=None if inherited else old_value,
        new_raw_value=serialized,
        inherited_from_default=inherited,
    )


def apply_change(
    payload: dict[str, Any],
    change: UIRemoteConfigChange,
    *,
    version_description: Optional[str] = None,
) -> dict[str, Any]:
    """
    Return a copy of the template with one value replaced.

    Everything else — other parameters, conditions, parameter groups, and
    fields Titan does not model — is carried over untouched, because the
    publish replaces the whole template.

    The outgoing `version` block carries only the description: the rest of the
    version metadata is assigned by Firebase, and echoing a stale version
    number back would be meaningless.

    Raises:
        TemplateEditError: If the parameter or condition is gone from the
            payload (a concurrent edit deleted it).
    """
    updated = copy.deepcopy(payload)
    parameter = _parameter(updated, change.key)

    if change.condition is None:
        default_value = parameter.get("defaultValue")
        if not isinstance(default_value, dict):
            default_value = {}
        # A parameter set to its in-app default has no explicit value; writing
        # one has to clear that flag or Firebase keeps ignoring the value.
        default_value.pop("useInAppDefault", None)
        default_value["value"] = change.new_raw_value
        parameter["defaultValue"] = default_value
    else:
        if change.condition not in condition_names(updated):
            raise TemplateEditError(
                f"La condición '{change.condition}' ya no existe en la "
                "plantilla."
            )
        conditional = parameter.get("conditionalValues")
        if not isinstance(conditional, dict):
            conditional = {}
        entry = conditional.get(change.condition)
        if not isinstance(entry, dict):
            entry = {}
        entry.pop("useInAppDefault", None)
        entry["value"] = change.new_raw_value
        conditional[change.condition] = entry
        parameter["conditionalValues"] = conditional

    description = version_description or change.describe()
    updated["version"] = {"description": description}
    return updated


def _parameter(payload: dict[str, Any], key: str) -> dict[str, Any]:
    """Return one parameter dict, or explain that it is not there."""
    parameters = payload.get("parameters")
    if not isinstance(parameters, dict) or key not in parameters:
        raise TemplateEditError(
            f"El parámetro '{key}' no existe en la plantilla. Créalo en la "
            "consola de Firebase antes de escribir sobre él."
        )
    parameter = parameters[key]
    if not isinstance(parameter, dict):
        raise TemplateEditError(
            f"El parámetro '{key}' tiene un formato inesperado en la plantilla."
        )
    return parameter


def _value_of(entry: Any) -> Optional[str]:
    """Extract the raw string from a value payload."""
    if isinstance(entry, dict):
        value = entry.get("value")
        if isinstance(value, str):
            return value
    return None


def _raw_values(parameter: dict[str, Any]) -> list[Optional[str]]:
    """Every raw value a parameter declares."""
    values = [_value_of(parameter.get("defaultValue"))]
    conditional = parameter.get("conditionalValues")
    if isinstance(conditional, dict):
        values.extend(_value_of(entry) for entry in conditional.values())
    return values


__all__ = [
    "RemoteConfigValueError",
    "TemplateEditError",
    "apply_change",
    "build_change",
    "condition_names",
    "current_raw_value",
    "effective_value_type_for",
]
