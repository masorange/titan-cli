"""Choose several brands at once for a multi-brand change."""

from __future__ import annotations

from titan_cli.engine import Error, Success, WorkflowContext, WorkflowResult
from titan_cli.ui.tui.widgets import SelectionOption

from ..operations.target_operations import (
    TargetResolutionError,
    available_brands,
    available_environments,
    project_id_for_brand,
    resolve_targets,
)


def execute_firebase_select_targets_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Resolve several Firebase projects, one per brand.

    Inputs (from ctx.data):
        brands (list[str] | str, optional): Brands to target; a comma-separated string is accepted.
        environment (str, optional): Environment for multi-environment configs.

    Outputs (saved to ctx.data):
        firebase_targets (list[FirebaseProjectTarget]): Resolved targets.
        firebase_environment (Optional[str]): Environment in use.
        firebase_target_failures (dict[str, str]): Unresolved brands and reasons.

    Returns:
        Success: If at least one target resolved.
        Error: If nothing is configured, the user cancels, or no brand resolved.
    """
    if ctx.textual:
        ctx.textual.begin_step("Seleccionar marcas")

    if not ctx.firebase:
        return _fail(ctx, "El plugin de Firebase no está disponible")

    config = ctx.firebase.config
    environment = ctx.get("environment") or ctx.get("firebase_environment")
    if environment is None:
        environment = _ask_environment(ctx, config)

    brands = _requested_brands(ctx)
    if brands is None:
        brands = _ask_brands(ctx, config, environment)
    if not brands:
        return _fail(ctx, "No se seleccionó ninguna marca")

    targets, failures = resolve_targets(config, brands, environment)
    if not targets:
        detail = "; ".join(f"{brand}: {reason}" for brand, reason in failures.items())
        return _fail(ctx, f"Ninguna marca se pudo resolver. {detail}")

    if ctx.textual:
        ctx.textual.table(
            headers=["Marca", "Proyecto"],
            rows=[[target.brand or "—", target.project_id] for target in targets],
            title=f"{len(targets)} marcas seleccionadas",
            flex_column=1,
        )
        for brand, reason in failures.items():
            # A brand nobody can resolve must be named, not silently dropped:
            # the user asked for it.
            ctx.textual.warning_text(f"{brand}: {reason}")
        ctx.textual.end_step("success")

    return Success(
        f"{len(targets)} marcas seleccionadas",
        metadata={
            "firebase_targets": targets,
            "firebase_environment": environment,
            "firebase_target_failures": failures,
        },
    )


def _requested_brands(ctx: WorkflowContext) -> list[str] | None:
    """Read brands passed as workflow params, if any."""
    requested = ctx.get("brands") or ctx.get("firebase_brands")
    if requested is None:
        return None
    if isinstance(requested, str):
        return [part.strip() for part in requested.split(",") if part.strip()]
    if isinstance(requested, (list, tuple)):
        return [str(brand).strip() for brand in requested if str(brand).strip()]
    return None


def _ask_environment(ctx: WorkflowContext, config) -> str | None:
    """Ask for an environment only when the config declares more than one."""
    environments = available_environments(config)
    if len(environments) <= 1 or not ctx.textual:
        return config.default_environment or (
            environments[0] if environments else None
        )

    from titan_cli.ui.tui.widgets import OptionItem

    return ctx.textual.ask_option(
        "¿Qué entorno?",
        [
            OptionItem(
                value=environment,
                title=environment,
                description="Entorno declarado en brand_projects",
            )
            for environment in environments
        ],
    )


def _ask_brands(ctx: WorkflowContext, config, environment) -> list[str]:
    """Multi-select the brands, showing the project each one resolves to."""
    if not ctx.textual:
        return []

    brands = available_brands(config, environment)
    if not brands:
        return []

    options = []
    for brand in brands:
        try:
            label = f"{brand} → {project_id_for_brand(config, brand, environment)}"
        except TargetResolutionError:
            label = f"{brand} (sin proyecto configurado)"
        options.append(
            # Nothing is preselected: a fan-out writes to production projects.
            SelectionOption(value=brand, label=label, selected=False)
        )

    selected = ctx.textual.ask_multiselect("¿En qué marcas?", options)
    return [str(brand) for brand in selected or []]


def _fail(ctx: WorkflowContext, message: str) -> WorkflowResult:
    """Report an error through the UI and the result."""
    if ctx.textual:
        ctx.textual.error_text(message)
        ctx.textual.end_step("error")
    return Error(message)
