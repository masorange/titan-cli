"""Operations for building Firebase Remote Config inventories."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import TYPE_CHECKING, Any, Optional

from pydantic import ValidationError

from ..exceptions import FirebaseAuthRejectedError, FirebaseClientError
from ..models import (
    FirebaseProjectTarget,
    RemoteConfigInventory,
    RemoteConfigInventoryFailure,
    RemoteConfigKeyInventory,
    RemoteConfigKeyOccurrence,
    RemoteConfigProjectInventory,
    RemoteConfigValueType,
    build_parameter_inventory,
)

if TYPE_CHECKING:
    from ..client import FirebaseClient
    from ..config import FirebasePluginConfig


def resolve_project_targets(
    config: FirebasePluginConfig,
    *,
    project_targets: Any = None,
    projects: Any = None,
    brand_projects: Optional[Mapping[str, Any]] = None,
    brands: Any = None,
    environments: Any = None,
) -> list[FirebaseProjectTarget]:
    """Resolve Firebase project targets from workflow inputs and plugin config."""
    default_environment = config.default_environment
    targets: list[FirebaseProjectTarget] = []

    explicit_targets = project_targets if project_targets is not None else projects
    if explicit_targets is None:
        explicit_targets = config.projects
    targets.extend(_targets_from_sequence(explicit_targets, default_environment))

    raw_brand_projects = (
        brand_projects if brand_projects is not None else config.brand_projects
    )
    targets.extend(
        _targets_from_brand_mapping(
            raw_brand_projects,
            default_environment=default_environment,
            layout=config.brand_projects_layout,
        )
    )

    if not targets and config.default_project:
        targets.append(
            FirebaseProjectTarget(
                project_id=config.default_project,
                brand=config.default_project,
                environment=default_environment,
            )
        )

    environment_aliases = _environment_alias_map(config.environments)
    return _filter_targets(
        _dedupe_targets(_normalize_target_environments(targets, environment_aliases)),
        brands=_as_filter_set(brands),
        environments=_as_filter_set(
            environments,
            aliases=environment_aliases,
        ),
    )


def build_remote_config_inventory(
    client: FirebaseClient,
    targets: Sequence[FirebaseProjectTarget],
    *,
    continue_on_error: bool = True,
) -> RemoteConfigInventory:
    """Read Remote Config templates and build an aggregated key inventory."""
    if not targets:
        raise FirebaseClientError("No Firebase project targets are configured.")

    project_inventories: list[RemoteConfigProjectInventory] = []
    failures: list[RemoteConfigInventoryFailure] = []

    for target in targets:
        try:
            remote_config = client.get_remote_config(target.project_id)
            project_inventory = build_project_inventory(
                target=target,
                template=remote_config.template,
                etag=remote_config.etag,
            )
        except FirebaseAuthRejectedError:
            raise
        except FirebaseClientError as exc:
            if not continue_on_error:
                raise
            failures.append(
                RemoteConfigInventoryFailure(
                    target=target,
                    message=str(exc),
                )
            )
            continue

        project_inventories.append(project_inventory)

    return RemoteConfigInventory(
        targets=list(targets),
        projects=project_inventories,
        keys=build_key_inventory(project_inventories),
        failures=failures,
    )


def build_project_inventory(
    *,
    target: FirebaseProjectTarget,
    template: dict[str, Any],
    etag: Optional[str],
) -> RemoteConfigProjectInventory:
    """Build normalized inventory for one Remote Config template."""
    if not isinstance(template, dict):
        raise FirebaseClientError(
            f"Remote Config template for {target.reference()} could not be "
            "normalized: template must be a JSON object."
        )

    raw_parameters = template.get("parameters")
    if raw_parameters is None:
        parameters_payload = {}
    elif isinstance(raw_parameters, dict):
        parameters_payload = raw_parameters
    else:
        raise FirebaseClientError(
            f"Remote Config template for {target.reference()} could not be "
            "normalized: parameters must be a JSON object when present."
        )

    parameters = {}
    for key, payload in sorted(parameters_payload.items()):
        if not isinstance(payload, dict):
            raise FirebaseClientError(
                f"Remote Config parameter '{key}' for {target.reference()} "
                "could not be normalized: parameter payload must be a JSON object."
            )
        try:
            parameters[key] = build_parameter_inventory(
                key,
                payload,
            )
        except ValidationError as exc:
            raise FirebaseClientError(
                f"Remote Config parameter '{key}' for {target.reference()} "
                f"could not be normalized: {_validation_error_summary(exc)}"
            ) from exc

    version = template.get("version")
    if version is None:
        version_payload = None
    elif isinstance(version, dict):
        version_payload = version
    else:
        raise FirebaseClientError(
            f"Remote Config template for {target.reference()} could not be "
            "normalized: version must be a JSON object when present."
        )
    version_number = None
    if version_payload and version_payload.get("versionNumber") is not None:
        raw_version_number = version_payload["versionNumber"]
        if isinstance(raw_version_number, bool) or not isinstance(
            raw_version_number,
            (int, str),
        ):
            raise FirebaseClientError(
                f"Remote Config template for {target.reference()} could not be "
                "normalized: version.versionNumber must be a string or integer "
                "when present."
            )
        version_number = str(raw_version_number)

    return RemoteConfigProjectInventory(
        target=target,
        etag=etag,
        version=version_payload,
        version_number=version_number,
        parameter_count=len(parameters),
        parameters=parameters,
    )


def _validation_error_summary(exc: ValidationError) -> str:
    """Return a compact Pydantic validation error summary."""
    errors = exc.errors()
    if not errors:
        return str(exc)
    first_error = errors[0]
    location = ".".join(str(part) for part in first_error.get("loc", ()))
    message = str(first_error.get("msg") or exc)
    return f"{location}: {message}" if location else message


def build_key_inventory(
    projects: Sequence[RemoteConfigProjectInventory],
) -> list[RemoteConfigKeyInventory]:
    """Build unique key inventory across successful project reads."""
    project_refs = [project.target.reference() for project in projects]
    all_keys = sorted(
        {
            key
            for project in projects
            for key in project.parameters
        }
    )
    inventories: list[RemoteConfigKeyInventory] = []

    for key in all_keys:
        occurrences: list[RemoteConfigKeyOccurrence] = []
        present_refs: list[str] = []

        for project in projects:
            parameter = project.parameters.get(key)
            if parameter is None:
                continue

            target = project.target
            occurrences.append(
                RemoteConfigKeyOccurrence(
                    key=key,
                    project_id=target.project_id,
                    brand=target.brand,
                    environment=target.environment,
                    platform=target.platform,
                    target_label=target.label,
                    value_type=parameter.value_type,
                    declared_value_type=parameter.declared_value_type,
                    inferred_value_type=parameter.inferred_value_type,
                    default_value=parameter.default_value,
                    conditional_value_names=parameter.conditional_value_names,
                    description=parameter.description,
                )
            )
            present_refs.append(target.reference())

        observed_types = _sort_value_types(
            {occurrence.value_type for occurrence in occurrences}
        )
        inventories.append(
            RemoteConfigKeyInventory(
                key=key,
                occurrences=occurrences,
                projects_present=present_refs,
                projects_missing=[
                    project_ref
                    for project_ref in project_refs
                    if project_ref not in present_refs
                ],
                observed_types=observed_types,
                has_type_mismatch=len(observed_types) > 1,
            )
        )

    return inventories


def _targets_from_sequence(
    values: Any,
    default_environment: Optional[str],
) -> list[FirebaseProjectTarget]:
    """Coerce a sequence of target declarations into project targets."""
    if values is None:
        return []
    if isinstance(values, (str, Mapping, FirebaseProjectTarget)):
        values = [values]
    if not isinstance(values, Iterable):
        return []

    targets: list[FirebaseProjectTarget] = []
    for item in values:
        target = _target_from_value(item, default_environment=default_environment)
        if target is not None:
            targets.append(target)
    return targets


def _target_from_value(
    value: Any,
    *,
    default_environment: Optional[str],
    brand: Optional[str] = None,
    environment: Optional[str] = None,
) -> Optional[FirebaseProjectTarget]:
    """Coerce one target declaration into a project target."""
    if isinstance(value, FirebaseProjectTarget):
        return _with_defaults(
            value,
            brand=brand,
            environment=environment or default_environment,
        )

    if isinstance(value, str):
        return FirebaseProjectTarget(
            project_id=value,
            brand=brand or value,
            environment=environment or default_environment,
        )

    if not isinstance(value, Mapping):
        return None

    data = dict(value)
    if "project" in data and "project_id" not in data:
        data["project_id"] = data.pop("project")
    if "env" in data and "environment" not in data:
        data["environment"] = data.pop("env")
    if "name" in data and "label" not in data:
        data["label"] = data.pop("name")

    if brand and "brand" not in data:
        data["brand"] = brand
    if environment and "environment" not in data:
        data["environment"] = environment
    if default_environment and "environment" not in data:
        data["environment"] = default_environment

    if "project_id" not in data:
        return None

    return FirebaseProjectTarget.model_validate(data)


def _targets_from_brand_mapping(
    values: Optional[Mapping[str, Any]],
    *,
    default_environment: Optional[str],
    layout: str,
) -> list[FirebaseProjectTarget]:
    """Coerce a brand/environment mapping into project targets."""
    if not values:
        return []

    targets: list[FirebaseProjectTarget] = []
    for outer_key, outer_value in values.items():
        target = _target_from_value(
            outer_value,
            default_environment=default_environment,
            brand=outer_key,
        )
        if target is not None:
            targets.append(target)
            continue

        if not isinstance(outer_value, Mapping):
            continue

        for inner_key, inner_value in outer_value.items():
            if layout == "brand_environment":
                brand = outer_key
                environment = inner_key
            else:
                environment = outer_key
                brand = inner_key

            target = _target_from_value(
                inner_value,
                default_environment=default_environment,
                brand=brand,
                environment=environment,
            )
            if target is not None:
                targets.append(target)

    return targets


def _with_defaults(
    target: FirebaseProjectTarget,
    *,
    brand: Optional[str],
    environment: Optional[str],
) -> FirebaseProjectTarget:
    """Return a target with optional defaults applied."""
    data = target.model_dump()
    if brand and not data.get("brand"):
        data["brand"] = brand
    if environment and not data.get("environment"):
        data["environment"] = environment
        data["label"] = None
    return FirebaseProjectTarget.model_validate(data)


def _dedupe_targets(
    targets: Sequence[FirebaseProjectTarget],
) -> list[FirebaseProjectTarget]:
    """Remove duplicate project targets while preserving order."""
    seen: set[tuple[Optional[str], Optional[str], Optional[str], str]] = set()
    deduped: list[FirebaseProjectTarget] = []
    for target in targets:
        key = (
            target.environment,
            target.brand,
            target.platform,
            target.project_id,
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(target)
    return deduped


def _filter_targets(
    targets: Sequence[FirebaseProjectTarget],
    *,
    brands: Optional[set[str]],
    environments: Optional[set[str]],
) -> list[FirebaseProjectTarget]:
    """Filter project targets by brand and environment names."""
    filtered: list[FirebaseProjectTarget] = []
    for target in targets:
        if brands and (target.brand or "") not in brands:
            continue
        if environments and (target.environment or "") not in environments:
            continue
        filtered.append(target)
    return filtered


def _environment_alias_map(environments: Sequence[Any]) -> dict[str, str]:
    """Build a lookup from configured environment aliases to canonical names."""
    aliases: dict[str, str] = {}
    for environment in environments:
        name = getattr(environment, "name", None)
        if not isinstance(name, str) or not name.strip():
            continue
        canonical = name.strip()
        for value in [canonical, *getattr(environment, "aliases", [])]:
            if isinstance(value, str) and value.strip():
                aliases[value.strip()] = canonical
    return aliases


def _normalize_target_environments(
    targets: Sequence[FirebaseProjectTarget],
    aliases: Mapping[str, str],
) -> list[FirebaseProjectTarget]:
    """Normalize target environments through configured aliases."""
    if not aliases:
        return list(targets)

    normalized_targets: list[FirebaseProjectTarget] = []
    for target in targets:
        environment = target.environment
        canonical = aliases.get(environment or "")
        if not canonical or canonical == environment:
            normalized_targets.append(target)
            continue

        data = target.model_dump()
        data["environment"] = canonical
        data["label"] = None
        normalized_targets.append(FirebaseProjectTarget.model_validate(data))
    return normalized_targets


def _as_filter_set(
    value: Any,
    *,
    aliases: Optional[Mapping[str, str]] = None,
) -> Optional[set[str]]:
    """Normalize workflow filter values into a set."""
    if value is None:
        return None
    if isinstance(value, str):
        values = [part.strip() for part in value.split(",")]
    elif isinstance(value, Iterable):
        values = [str(part).strip() for part in value]
    else:
        values = [str(value).strip()]

    alias_map = aliases or {}
    normalized = {
        alias_map.get(part, part)
        for part in values
        if part
    }
    return normalized or None


def _sort_value_types(
    value_types: set[RemoteConfigValueType],
) -> list[RemoteConfigValueType]:
    """Sort value types for deterministic inventories."""
    order = {
        RemoteConfigValueType.BOOLEAN: 0,
        RemoteConfigValueType.JSON: 1,
        RemoteConfigValueType.NUMBER: 2,
        RemoteConfigValueType.STRING: 3,
        RemoteConfigValueType.UNKNOWN: 4,
    }
    return sorted(value_types, key=lambda value_type: order[value_type])
