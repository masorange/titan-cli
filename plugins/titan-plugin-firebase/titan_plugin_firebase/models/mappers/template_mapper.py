"""Pure mappers: network template payloads to UI models."""

from __future__ import annotations

from typing import Optional

from ..network.rest import (
    NetworkCondition,
    NetworkParameter,
    NetworkParameterValue,
    NetworkRemoteConfigTemplate,
    NetworkVersion,
)
from ..values import (
    RemoteConfigValueType,
    format_value_for_display,
    infer_value_type,
    normalize_value_type,
    parse_value,
)
from ..view import (
    UIRemoteConfigCondition,
    UIRemoteConfigParameter,
    UIRemoteConfigTemplate,
    UIRemoteConfigValue,
    UIRemoteConfigVersion,
)


def effective_value_type(parameter: NetworkParameter) -> RemoteConfigValueType:
    """
    Resolve the type to use for a parameter.

    The declared `valueType` wins when Firebase sends one; parameters created
    before it existed have none, so the type is inferred from the first raw
    value that yields one.
    """
    declared = normalize_value_type(parameter.value_type)
    if declared != RemoteConfigValueType.UNKNOWN:
        return declared

    for raw_value in parameter.raw_values():
        inferred = infer_value_type(raw_value)
        if inferred != RemoteConfigValueType.UNKNOWN:
            return inferred
    return RemoteConfigValueType.UNKNOWN


def map_value(
    value: NetworkParameterValue,
    value_type: RemoteConfigValueType,
) -> UIRemoteConfigValue:
    """Map one network value payload to its UI model."""
    use_in_app_default = bool(value.use_in_app_default)
    source = value.value_source
    if not source.is_titan_editable:
        display = f"({source.display_label})"
    elif source.is_titan_editable and use_in_app_default and value.value is None:
        display = "(in-app default)"
    else:
        display = format_value_for_display(value.value, value_type)
    return UIRemoteConfigValue(
        raw_value=value.value,
        parsed_value=parse_value(value.value, value_type),
        value_type=value_type,
        use_in_app_default=use_in_app_default,
        display_value=display,
        source=source,
    )


def map_parameter(key: str, parameter: NetworkParameter) -> UIRemoteConfigParameter:
    """Map one network parameter to its UI model."""
    value_type = effective_value_type(parameter)
    return UIRemoteConfigParameter(
        key=key,
        description=parameter.description,
        value_type=value_type,
        declared_value_type=normalize_value_type(parameter.value_type),
        default_value=(
            map_value(parameter.default_value, value_type)
            if parameter.default_value is not None
            else None
        ),
        conditional_values={
            condition_name: map_value(raw_value, value_type)
            for condition_name, raw_value in parameter.conditional_values.items()
        },
    )


def map_condition(condition: NetworkCondition) -> UIRemoteConfigCondition:
    """Map one network condition to its UI model."""
    return UIRemoteConfigCondition(
        name=condition.name,
        expression=condition.expression,
        tag_color=condition.tag_color,
    )


def map_version(version: Optional[NetworkVersion]) -> Optional[UIRemoteConfigVersion]:
    """Map version metadata to its UI model."""
    if version is None:
        return None
    return UIRemoteConfigVersion(
        version_number=version.version_number,
        update_time=version.update_time,
        update_user_email=(
            version.update_user.email if version.update_user is not None else None
        ),
        update_origin=version.update_origin,
        update_type=version.update_type,
        description=version.description,
    )


def map_template(
    project_id: str,
    template: NetworkRemoteConfigTemplate,
    etag: Optional[str],
) -> UIRemoteConfigTemplate:
    """Map a whole network template to its UI model, parameters sorted by key."""
    return UIRemoteConfigTemplate(
        project_id=project_id,
        etag=etag,
        parameters=[
            map_parameter(key, parameter)
            for key, parameter in sorted(template.parameters.items())
        ],
        conditions=[map_condition(condition) for condition in template.conditions],
        version=map_version(template.version),
        parameter_group_names=sorted(template.parameter_groups),
    )
