"""
Resolving which Firebase project a workflow acts on.

Ragnarok runs one Firebase project per brand, so a target is a brand (and
optionally an environment) resolved to a project ID. Three sources are
supported, in this order of specificity:

1. `brand_projects` — an explicit mapping, when project IDs follow no rule.
2. `project_id_pattern` + `brand_project_overrides` — a naming convention with
   exceptions, which is how the Android brands are actually named.
3. `default_project` — the single-project case.

Pure functions: no context, no UI, no network.
"""

from __future__ import annotations

from typing import Optional

from ..config import FirebasePluginConfig
from ..models.targets import FirebaseProjectTarget


class TargetResolutionError(ValueError):
    """Raised when configuration cannot produce a project for a request."""


def _mapping_for_environment(
    config: FirebasePluginConfig,
    environment: Optional[str],
) -> dict[str, str]:
    """Flatten `brand_projects` into brand -> project_id for one environment."""
    if not config.brand_projects:
        return {}

    if config.brand_projects_layout == "environment_brand":
        environments = {
            str(name): value
            for name, value in config.brand_projects.items()
            if isinstance(value, dict)
        }
        if not environments:
            return {}
        selected = environment or config.default_environment
        if selected is None and len(environments) == 1:
            selected = next(iter(environments))
        if selected is None:
            raise TargetResolutionError(
                "brand_projects declara varios entornos "
                f"({', '.join(sorted(environments))}). Indica environment o "
                "configura default_environment."
            )
        brands = environments.get(selected)
        if brands is None:
            raise TargetResolutionError(
                f"El entorno '{selected}' no existe en brand_projects. "
                f"Disponibles: {', '.join(sorted(environments))}."
            )
        return {str(brand): str(project) for brand, project in brands.items()}

    mapping: dict[str, str] = {}
    for brand, value in config.brand_projects.items():
        if isinstance(value, dict):
            selected = environment or config.default_environment
            if selected is None and len(value) == 1:
                selected = next(iter(value))
            if selected is not None and selected in value:
                mapping[str(brand)] = str(value[selected])
        elif isinstance(value, str):
            mapping[str(brand)] = value
    return mapping


def available_environments(config: FirebasePluginConfig) -> list[str]:
    """Return the environments declared in `brand_projects`, if any."""
    if not config.brand_projects:
        return []
    if config.brand_projects_layout == "environment_brand":
        return sorted(
            str(name)
            for name, value in config.brand_projects.items()
            if isinstance(value, dict)
        )
    environments: set[str] = set()
    for value in config.brand_projects.values():
        if isinstance(value, dict):
            environments.update(str(name) for name in value)
    return sorted(environments)


def available_brands(
    config: FirebasePluginConfig,
    environment: Optional[str] = None,
) -> list[str]:
    """
    Return the brands that can be targeted.

    `brands` fixes the display order when it is configured; otherwise the
    brands come from whichever mapping is available.
    """
    mapping = _mapping_for_environment(config, environment)
    known = set(mapping) | set(config.brand_project_overrides)
    if config.brands:
        ordered = [brand for brand in config.brands]
        ordered.extend(sorted(brand for brand in known if brand not in config.brands))
        return ordered
    if known:
        return sorted(known)
    return []


def project_id_for_brand(
    config: FirebasePluginConfig,
    brand: str,
    environment: Optional[str] = None,
) -> str:
    """
    Resolve one brand to a project ID.

    Raises:
        TargetResolutionError: If no source can name a project for the brand.
    """
    normalized_brand = (brand or "").strip()
    if not normalized_brand:
        raise TargetResolutionError("La marca es obligatoria.")

    mapping = _mapping_for_environment(config, environment)
    if normalized_brand in mapping:
        return mapping[normalized_brand]

    override = config.brand_project_overrides.get(normalized_brand)
    if override and override.strip():
        return override.strip()

    if config.project_id_pattern:
        return config.project_id_pattern.format(
            brand=normalized_brand,
            environment=(environment or config.default_environment or ""),
        ).strip("-")

    raise TargetResolutionError(
        f"No hay proyecto Firebase configurado para la marca "
        f"'{normalized_brand}'. Define brand_projects, "
        f"project_id_pattern o brand_project_overrides."
    )


def resolve_target(
    config: FirebasePluginConfig,
    *,
    project_id: Optional[str] = None,
    brand: Optional[str] = None,
    environment: Optional[str] = None,
) -> FirebaseProjectTarget:
    """
    Resolve one target from an explicit project, a brand, or the default.

    Raises:
        TargetResolutionError: If nothing in the request or the config names a
            project.
    """
    selected_environment = environment or config.default_environment

    if project_id and project_id.strip():
        return FirebaseProjectTarget(
            project_id=project_id.strip(),
            brand=brand,
            environment=selected_environment,
        )

    if brand and brand.strip():
        return FirebaseProjectTarget(
            project_id=project_id_for_brand(config, brand, selected_environment),
            brand=brand.strip(),
            environment=selected_environment,
        )

    if config.default_project:
        return FirebaseProjectTarget(
            project_id=config.default_project,
            brand=None,
            environment=selected_environment,
        )

    raise TargetResolutionError(
        "No hay proyecto Firebase que usar. Pasa project_id o brand, o "
        "configura plugins.firebase.config.default_project."
    )


def resolve_targets(
    config: FirebasePluginConfig,
    brands: list[str],
    environment: Optional[str] = None,
) -> tuple[list[FirebaseProjectTarget], dict[str, str]]:
    """
    Resolve several brands at once, for multi-brand workflows.

    Returns:
        The resolved targets and, for the brands that could not be resolved,
        a brand -> reason mapping. Nothing raises: a workflow writing to nine
        brands should report the tenth rather than abort.
    """
    targets: list[FirebaseProjectTarget] = []
    failures: dict[str, str] = {}
    for brand in brands:
        try:
            targets.append(
                resolve_target(config, brand=brand, environment=environment)
            )
        except TargetResolutionError as exc:
            failures[brand] = str(exc)
    return targets, failures
