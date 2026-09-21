"""Plan creating a new Remote Config key across selected projects."""

from __future__ import annotations

from contextlib import nullcontext
from typing import Any, Mapping

from titan_cli.core.result import ClientError, ClientSuccess
from titan_cli.engine import Error, Exit, Success, WorkflowContext, WorkflowResult
from titan_cli.ui.tui.widgets import ChoiceOption, SelectionOption

from ..models.values import RemoteConfigValueType, normalize_value_type
from ..models.view import UIRemoteConfigKeyCreatePlanEntry
from ..operations.create_key_operations import (
    build_create_request,
    common_condition_names,
    create_plan_summary,
    describe_create_plan,
    parse_condition_value_map,
    select_create_entries,
    select_create_targets,
    targets_missing_key,
)
from ..operations.target_operations import parse_project_ids
from .prompts import ask_value, blank_to_none


def execute_firebase_remoteconfig_create_key_plan_step(
    ctx: WorkflowContext,
) -> WorkflowResult:
    """
    Build and validate a plan to create one Remote Config key.

    The step uses the previous multi-project inventory to create the key only
    where it is missing, then validates the typed payload against each target
    template with Firebase before anything is published.
    Targets may span several configured environments when the selection step
    has explicitly included them; publishing remains per project.

    Requires:
        ctx.firebase: An initialized FirebaseClient.

    Inputs (from ctx.data):
        firebase_targets (list[FirebaseProjectTarget]): From firebase_select_targets.
        firebase_remoteconfig_key_profiles (dict[str, dict], optional): From firebase_remoteconfig_fanout_list_keys.
        firebase_remoteconfig_project_conditions (dict[str, list[dict]], optional): From firebase_remoteconfig_fanout_list_keys.
        firebase_remoteconfig_failed_projects (dict[str, str], optional): From firebase_remoteconfig_fanout_list_keys.
        key (str, optional): New parameter key.
        value_type (str, optional): New parameter type: BOOLEAN, JSON, NUMBER or STRING.
        default_value (str, optional): Default value to store.
        conditional_values (dict | str, optional): Condition values as a mapping, JSON object, or condition=value list.
        description (str, optional): Parameter description.
        target_project_ids (str | list[str], optional): Projects where the key should be created.

    Outputs (saved to ctx.data):
        firebase_create_key_plan (list[UIRemoteConfigKeyCreatePlanEntry]): Entries chosen for publishing.
        firebase_create_key_rejected (list[UIRemoteConfigKeyCreatePlanEntry]): Entries left out.
        firebase_key (str): Key selected for creation.
        firebase_value_type (str): Declared value type.

    Returns:
        Success: If at least one project is selected for publishing.
        Exit: If the key already exists everywhere, no target validates, or the user selects none.
        Error: If inputs are missing or invalid.
    """
    if ctx.textual:
        ctx.textual.begin_step("Planificar creación de clave")

    if not ctx.firebase:
        return _fail(ctx, "El plugin de Firebase no está disponible")

    targets = ctx.get("firebase_targets")
    if not targets:
        return _fail(
            ctx,
            "Faltan los proyectos. Ejecuta firebase_select_targets antes de este paso.",
        )

    inventory_error = _inventory_error(ctx)
    if inventory_error is not None:
        return _fail(ctx, inventory_error)

    key = _resolve_key(ctx)
    if key is None:
        return _fail(ctx, "Falta key. Pásala como parámetro del workflow.")

    profiles = _profiles(ctx)
    missing_targets = targets_missing_key(targets, profiles, key)
    if not missing_targets:
        return _exit(ctx, f"La clave '{key}' ya existe en todos los proyectos.")

    requested_ids = _requested_target_ids(ctx)
    if requested_ids:
        selected_targets = select_create_targets(missing_targets, requested_ids)
        selected_ids = {target.project_id for target in selected_targets}
        invalid_ids = sorted(set(requested_ids) - selected_ids)
        if invalid_ids:
            return _fail(
                ctx,
                "Los proyectos destino no son proyectos donde falte la clave: "
                f"{', '.join(invalid_ids)}.",
            )
    else:
        selected_targets = missing_targets

    request = _resolve_request(ctx, key, selected_targets)
    if isinstance(request, (Error, Exit)):
        return request

    entries = _validate_everywhere(ctx, selected_targets, request)

    if ctx.textual:
        ctx.textual.table(
            headers=[
                "Proyecto",
                "Estado",
                "Tipo",
                "Valor por defecto",
                "Entornos/condiciones",
                "Detalle",
            ],
            rows=describe_create_plan(entries),
            title=f"Plan para crear {key}",
            flex_column=4,
        )
        counts = create_plan_summary(entries)
        ctx.textual.dim_text(
            f"{counts['ready']} listo(s) · {counts['error']} con error"
        )

    ready = [entry for entry in entries if entry.is_publishable]
    if not ready:
        return _exit(ctx, f"Ningún proyecto puede crear la clave '{key}'.")

    chosen = ready if requested_ids else _confirm_projects(ctx, ready)
    if not chosen:
        return _exit(ctx, "No se seleccionó ningún proyecto para publicar.")

    rejected = [entry for entry in entries if entry not in chosen]
    if ctx.textual:
        ctx.textual.end_step("success")

    return Success(
        f"{len(chosen)} proyectos listos para crear {key}",
        metadata={
            "firebase_create_key_plan": chosen,
            "firebase_create_key_rejected": rejected,
            "firebase_key": request.key,
            "firebase_value_type": request.value_type.value,
        },
    )


def _resolve_key(ctx: WorkflowContext) -> str | None:
    """Read or ask for the key to create."""
    key = blank_to_none(ctx.get("key")) or blank_to_none(ctx.get("firebase_key"))
    if key is not None:
        return key
    if not ctx.textual:
        return None
    value = ctx.textual.ask_text("Nombre de la nueva key:", default="")
    return blank_to_none(value)


def _resolve_request(ctx: WorkflowContext, key: str, targets):
    """Read or ask for the new parameter shape and values."""
    value_type = _resolve_value_type(ctx)
    if isinstance(value_type, (Error, Exit)):
        return value_type

    default_value = _resolve_default_value(ctx, key, value_type)
    if isinstance(default_value, (Error, Exit)):
        return default_value

    description = _resolve_description(ctx)
    try:
        conditional_values = _resolve_condition_values(ctx, key, value_type, targets)
        return build_create_request(
            key=key,
            value_type=value_type,
            default_value=default_value,
            conditional_values=conditional_values,
            description=description,
        )
    except ValueError as exc:
        return _fail(ctx, str(exc))


def _resolve_value_type(ctx: WorkflowContext) -> RemoteConfigValueType | WorkflowResult:
    """Read or ask for the new key's value type."""
    raw = blank_to_none(ctx.get("value_type")) or blank_to_none(
        ctx.get("firebase_value_type")
    )
    if raw is not None:
        value_type = normalize_value_type(raw)
        if value_type == RemoteConfigValueType.UNKNOWN:
            return _fail(ctx, "El tipo de la nueva clave debe ser conocido.")
        return value_type

    if not ctx.textual:
        return _fail(ctx, "Falta value_type. Usa BOOLEAN, JSON, NUMBER o STRING.")

    selected = ctx.textual.ask_choice(
        "Tipo de la nueva key:",
        options=[
            ChoiceOption(value=T.value, label=T.display_label)
            for T in (
                RemoteConfigValueType.BOOLEAN,
                RemoteConfigValueType.JSON,
                RemoteConfigValueType.NUMBER,
                RemoteConfigValueType.STRING,
            )
        ],
    )
    if selected is None:
        return _fail(ctx, "No se seleccionó ningún tipo.")
    return RemoteConfigValueType(str(selected))


def _resolve_default_value(
    ctx: WorkflowContext,
    key: str,
    value_type: RemoteConfigValueType,
) -> str | WorkflowResult:
    """Read or ask for the new default value."""
    raw = ctx.get("default_value")
    if raw is None:
        raw = ctx.get("firebase_default_value")
    if raw is None:
        raw = ctx.get("value")
    if raw is not None and blank_to_none(raw) is not None:
        return str(raw)

    if not ctx.textual:
        return _fail(ctx, "Falta default_value para crear la clave.")

    value = ask_value(ctx, key, value_type, None, None)
    if value is None:
        return _fail(ctx, "No se introdujo ningún valor por defecto.")
    return value


def _resolve_description(ctx: WorkflowContext) -> str | None:
    """Read or ask for an optional parameter description."""
    raw = ctx.get("description")
    if raw is None:
        raw = ctx.get("firebase_description")
    if raw is not None:
        return blank_to_none(raw)
    if not ctx.textual:
        return None
    return blank_to_none(ctx.textual.ask_text("Descripción opcional:", default=""))


def _resolve_condition_values(
    ctx: WorkflowContext,
    key: str,
    value_type: RemoteConfigValueType,
    targets,
) -> dict[str, str]:
    """Read or ask for optional condition values shared by selected targets."""
    raw = ctx.get("conditional_values")
    if raw is None:
        raw = ctx.get("firebase_conditional_values")
    if raw is not None:
        values = parse_condition_value_map(raw)
        _validate_requested_conditions(ctx, values, targets)
        return values

    if not ctx.textual:
        return {}

    condition_names = common_condition_names(_project_conditions(ctx), targets)
    if not condition_names:
        ctx.textual.dim_text(
            "No hay condiciones comunes en los proyectos seleccionados; "
            "se creará solo el valor por defecto."
        )
        return {}

    selected = ctx.textual.ask_multiselect(
        "¿Qué condiciones tendrán valor propio?",
        [
            SelectionOption(
                value=condition_name,
                label=condition_name,
                selected=False,
            )
            for condition_name in condition_names
        ],
    )
    values: dict[str, str] = {}
    for condition_name in selected or []:
        value = ask_value(ctx, key, value_type, None, str(condition_name))
        if value is None:
            raise ValueError(f"No se introdujo valor para {condition_name}.")
        values[str(condition_name)] = value
    return values


def _validate_requested_conditions(ctx, values: Mapping[str, str], targets) -> None:
    """Reject condition values that are not present in every selected target."""
    if not values:
        return
    project_conditions = _project_conditions(ctx)
    if not project_conditions:
        return
    common = set(common_condition_names(project_conditions, targets))
    invalid = sorted(set(values) - common)
    if invalid:
        raise ValueError(
            "Estas condiciones no existen en todos los proyectos destino: "
            f"{', '.join(invalid)}."
        )


def _validate_everywhere(
    ctx: WorkflowContext,
    targets,
    request,
) -> list[UIRemoteConfigKeyCreatePlanEntry]:
    """Validate the new key against each target project."""
    entries: list[UIRemoteConfigKeyCreatePlanEntry] = []
    for target in targets:
        loading = (
            ctx.textual.loading(f"Validando creación en {target.project_id}...")
            if ctx.textual
            else nullcontext()
        )
        with loading:
            result = ctx.firebase.create_remote_config_key(
                target.project_id,
                request,
                validate_only=True,
            )

        match result:
            case ClientSuccess():
                entries.append(
                    UIRemoteConfigKeyCreatePlanEntry(
                        target=target,
                        request=request,
                    )
                )
            case ClientError(error_message=error_message):
                entries.append(
                    UIRemoteConfigKeyCreatePlanEntry(
                        target=target,
                        request=request,
                        error=error_message,
                    )
                )
            case _:
                entries.append(
                    UIRemoteConfigKeyCreatePlanEntry(
                        target=target,
                        request=request,
                        error="Respuesta inesperada al validar la creación.",
                    )
                )
    return entries


def _confirm_projects(
    ctx: WorkflowContext,
    ready: list[UIRemoteConfigKeyCreatePlanEntry],
) -> list[UIRemoteConfigKeyCreatePlanEntry]:
    """Ask which validated projects should be published."""
    if not ctx.textual:
        return []
    selected = ctx.textual.ask_multiselect(
        "¿En qué proyectos publicas la nueva key?",
        [
            SelectionOption(
                value=entry.target.project_id,
                label=f"{entry.target.reference()} · {entry.detail}",
                selected=False,
            )
            for entry in ready
        ],
    )
    return select_create_entries(ready, [str(value) for value in selected or []])


def _requested_target_ids(ctx: WorkflowContext) -> list[str]:
    """Read optional explicit target IDs."""
    raw = ctx.get("target_project_ids")
    if raw is None:
        raw = ctx.get("firebase_target_project_ids")
    return parse_project_ids(raw)


def _profiles(ctx: WorkflowContext) -> Mapping[str, Any] | None:
    """Read key profiles from a previous inventory step."""
    profiles = ctx.get("firebase_remoteconfig_key_profiles")
    return profiles if isinstance(profiles, Mapping) else None


def _project_conditions(ctx: WorkflowContext) -> Mapping[str, Any]:
    """Read condition metadata from a previous inventory step."""
    conditions = ctx.get("firebase_remoteconfig_project_conditions")
    return conditions if isinstance(conditions, Mapping) else {}


def _inventory_error(ctx: WorkflowContext) -> str | None:
    """Reject create planning when the inventory missed a project."""
    if ctx.get("firebase_remoteconfig_key_profiles") is None:
        return None
    failed_projects = ctx.get("firebase_remoteconfig_failed_projects") or {}
    if not failed_projects:
        return None
    failed_ids = ", ".join(str(project_id) for project_id in sorted(failed_projects))
    return (
        "No se puede crear una clave porque el inventario no pudo leer todos "
        f"los proyectos: {failed_ids}."
    )


def _fail(ctx: WorkflowContext, message: str) -> WorkflowResult:
    """Report an error through the UI and the result."""
    if ctx.textual:
        ctx.textual.error_text(message)
        ctx.textual.end_step("error")
    return Error(message)


def _exit(ctx: WorkflowContext, message: str) -> WorkflowResult:
    """Report a controlled workflow exit."""
    if ctx.textual:
        ctx.textual.warning_text(message)
        ctx.textual.end_step("skipped")
    return Exit(message)
