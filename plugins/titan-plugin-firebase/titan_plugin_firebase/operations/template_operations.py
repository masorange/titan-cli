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
from typing import Any, Iterable, Optional

from ..models.values import (
    RemoteConfigValueError,
    RemoteConfigValueSource,
    RemoteConfigValueType,
    infer_value_type,
    normalize_value_type,
    serialize_value,
)
from ..models.view import UIRemoteConfigChange


class TemplateEditError(ValueError):
    """Raised when a requested edit cannot be applied to a template."""


_EDITABLE_VALUE_FIELDS = {"useInAppDefault", "value"}
_MANAGED_VALUE_FIELDS = {
    "experimentValue": RemoteConfigValueSource.EXPERIMENT,
    "personalizationValue": RemoteConfigValueSource.PERSONALIZATION,
    "rolloutValue": RemoteConfigValueSource.ROLLOUT,
}
_VALUE_SOURCE_ORDER = {
    source: index for index, source in enumerate(RemoteConfigValueSource)
}


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

    _ensure_value_slot_is_editable(payload, key, condition)
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
    _ensure_value_slot_is_editable(updated, change.key, change.condition)

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
                f"La condición '{change.condition}' ya no existe en la plantilla."
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


def parameter_payload(payload: dict[str, Any], key: str) -> dict[str, Any]:
    """Return a copy of one raw parameter payload."""
    return copy.deepcopy(_parameter(payload, key))


def add_parameter_to_payload(
    payload: dict[str, Any],
    key: str,
    source_parameter: dict[str, Any],
    *,
    version_description: Optional[str] = None,
) -> dict[str, Any]:
    """
    Return a copy of a template with one missing parameter added.

    Existing keys are never overwritten. Conditional values are copied only
    when the target template already declares every referenced condition; this
    keeps Firebase from rejecting the full-template publish later with a less
    precise 400.

    Raises:
        TemplateEditError: If the key already exists, the parameter payload is
            malformed, or a copied conditional value references a missing
            condition in the target template, or the source has Firebase-managed
            value payloads.
    """
    if not key or not key.strip():
        raise TemplateEditError("La clave de Remote Config es obligatoria.")
    if not isinstance(source_parameter, dict):
        raise TemplateEditError(f"El parámetro '{key}' no tiene un formato válido.")
    blocked_sources = blocked_value_sources_for_parameter(source_parameter)
    if blocked_sources:
        raise TemplateEditError(
            f"El parámetro '{key}' contiene valores gestionados por Firebase "
            f"({_format_sources(blocked_sources)}) y Titan no los copia "
            "hasta que exista soporte explícito para ese origen."
        )

    updated = copy.deepcopy(payload)
    parameters = updated.get("parameters")
    if parameters is None:
        parameters = {}
    if not isinstance(parameters, dict):
        raise TemplateEditError("La plantilla tiene un bloque parameters inválido.")
    if key in parameters:
        raise TemplateEditError(
            f"El parámetro '{key}' ya existe en la plantilla destino."
        )

    missing_conditions = _missing_conditions_for_parameter(updated, source_parameter)
    if missing_conditions:
        names = ", ".join(missing_conditions)
        raise TemplateEditError(
            f"El parámetro '{key}' referencia condiciones que no existen en "
            f"la plantilla destino: {names}."
        )

    parameters[key] = copy.deepcopy(source_parameter)
    updated["parameters"] = parameters
    updated["version"] = {
        "description": version_description or f"Titan: copied Remote Config key {key}"
    }
    return updated


def build_parameter_payload(
    value_type: RemoteConfigValueType,
    default_value: str,
    *,
    conditional_values: Optional[dict[str, str]] = None,
    description: Optional[str] = None,
) -> dict[str, Any]:
    """
    Build a new Remote Config parameter payload from typed user input.

    Raises:
        TemplateEditError: If the value type is unknown or a condition name is blank.
        RemoteConfigValueError: If any value does not match the declared type.
    """
    normalized_type = normalize_value_type(value_type)
    if not normalized_type.is_known:
        raise TemplateEditError("El tipo de la nueva clave debe ser conocido.")

    parameter: dict[str, Any] = {
        "defaultValue": {"value": serialize_value(default_value, normalized_type)},
        "valueType": normalized_type.value,
    }
    if description and description.strip():
        parameter["description"] = description.strip()

    condition_payload: dict[str, dict[str, str]] = {}
    for condition_name, raw_value in sorted((conditional_values or {}).items()):
        condition_key = str(condition_name).strip()
        if not condition_key:
            raise TemplateEditError(
                "Los valores por condición necesitan un nombre de condición."
            )
        condition_payload[condition_key] = {
            "value": serialize_value(raw_value, normalized_type)
        }
    if condition_payload:
        parameter["conditionalValues"] = condition_payload

    return parameter


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


def blocked_value_sources_for_parameter(
    parameter: dict[str, Any],
) -> list[RemoteConfigValueSource]:
    """Return unsupported value sources present anywhere in a parameter."""
    if not isinstance(parameter, dict):
        return [RemoteConfigValueSource.UNKNOWN]
    return _unique_sources(
        source for _location, source in _blocked_value_locations(parameter)
    )


def _ensure_value_slot_is_editable(
    payload: dict[str, Any],
    key: str,
    condition: Optional[str],
) -> None:
    """Reject writes that would overwrite Firebase-managed value payloads."""
    parameter = _parameter(payload, key)
    target = "valor por defecto"
    entry = parameter.get("defaultValue")
    if condition is not None:
        target = f"condición '{condition}'"
        conditional = parameter.get("conditionalValues")
        entry = (
            conditional.get(condition)
            if isinstance(conditional, dict) and condition in conditional
            else None
        )

    blocked_sources = _blocked_value_sources(entry)
    if not blocked_sources:
        return

    raise TemplateEditError(
        f"No se puede modificar {target} de '{key}': Firebase lo gestiona "
        f"como {_format_sources(blocked_sources)}. Revísalo en Firebase o "
        "añade soporte explícito antes de publicarlo desde Titan."
    )


def _blocked_value_locations(
    parameter: dict[str, Any],
) -> list[tuple[str, RemoteConfigValueSource]]:
    """Return unsupported value sources with their parameter location."""
    locations: list[tuple[str, RemoteConfigValueSource]] = []
    locations.extend(
        ("defaultValue", source)
        for source in _blocked_value_sources(parameter.get("defaultValue"))
    )
    conditional = parameter.get("conditionalValues")
    if isinstance(conditional, dict):
        for condition_name, entry in conditional.items():
            locations.extend(
                (f"conditionalValues.{condition_name}", source)
                for source in _blocked_value_sources(entry)
            )
    return locations


def _blocked_value_sources(entry: Any) -> list[RemoteConfigValueSource]:
    """Return value sources that Titan's literal write path must not replace."""
    if not isinstance(entry, dict) or not entry:
        return []

    sources = [
        source
        for field, source in _MANAGED_VALUE_FIELDS.items()
        if entry.get(field) is not None
    ]
    known_fields = _EDITABLE_VALUE_FIELDS | set(_MANAGED_VALUE_FIELDS)
    unknown_fields = set(entry) - known_fields
    if unknown_fields:
        sources.append(RemoteConfigValueSource.UNKNOWN)
    return _unique_sources(sources)


def _missing_conditions_for_parameter(
    payload: dict[str, Any],
    parameter: dict[str, Any],
) -> list[str]:
    """Return copied conditional names the target template does not declare."""
    conditional = parameter.get("conditionalValues")
    if not isinstance(conditional, dict):
        return []
    declared = set(condition_names(payload))
    return sorted(str(name) for name in conditional if str(name) not in declared)


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


def _unique_sources(
    sources: Iterable[RemoteConfigValueSource],
) -> list[RemoteConfigValueSource]:
    """Deduplicate value sources in enum order."""
    return sorted(set(sources), key=lambda source: _VALUE_SOURCE_ORDER[source])


def _format_sources(sources: Iterable[RemoteConfigValueSource]) -> str:
    """Return source labels for user-facing errors."""
    return ", ".join(source.display_label for source in _unique_sources(sources))


__all__ = [
    "RemoteConfigValueError",
    "TemplateEditError",
    "add_parameter_to_payload",
    "apply_change",
    "blocked_value_sources_for_parameter",
    "build_parameter_payload",
    "build_change",
    "condition_names",
    "current_raw_value",
    "effective_value_type_for",
    "parameter_payload",
]
