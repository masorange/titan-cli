"""Firebase Remote Config inventory workflow step."""

from __future__ import annotations

from contextlib import AbstractContextManager, nullcontext
from typing import Any

from pydantic import ValidationError

from titan_cli.engine import Error, Success, WorkflowContext, WorkflowResult

from ..exceptions import FirebaseAuthRejectedError, FirebaseClientError
from ..operations.remoteconfig_inventory import resolve_project_targets
from .auth_retry import reauthenticate_after_rejected_token


def execute_firebase_remoteconfig_inventory_step(
    ctx: WorkflowContext,
) -> WorkflowResult:
    """
    Build a key inventory across configured Firebase Remote Config projects.

    Requires:
        ctx.firebase: An initialized FirebaseClient.

    Inputs (from ctx.data):
        project_targets (list[dict], optional): Explicit Firebase project targets.
        firebase_project_targets (list[dict], optional): Alternate explicit target key.
        projects (list[dict|str], optional): Firebase project targets or project IDs.
        brand_projects (dict, optional): Brand/environment project mapping override.
        brand (str, optional): Single brand filter.
        brands (list[str]|str, optional): Brand filter list or comma-separated string.
        environment (str, optional): Single environment filter.
        environments (list[str]|str, optional): Environment filter list or comma-separated string.
        continue_on_error (bool, optional): Continue when one project read fails. Defaults to True.

    Outputs (saved to ctx.data):
        firebase_remoteconfig_inventory (dict): Aggregated inventory payload.
        firebase_remoteconfig_keys (list[dict]): Unique key inventory rows.
        firebase_remoteconfig_targets (list[dict]): Project targets that were requested.
        firebase_remoteconfig_project_count (int): Number of projects read successfully.
        firebase_remoteconfig_key_count (int): Number of unique keys found.
        firebase_remoteconfig_failures (list[dict]): Project read failures, when any.

    Returns:
        Success: If at least one project is read and key inventory is built.
        Error: If Firebase is unavailable, no targets are configured, or all project reads fail.
    """
    if ctx.textual:
        ctx.textual.begin_step("Inventory Firebase Remote Config Keys")

    if not ctx.firebase:
        message = "Firebase client not available"
        if ctx.textual:
            ctx.textual.error_text(message)
            ctx.textual.end_step("error")
        return Error(message)

    try:
        targets = resolve_project_targets(
            ctx.firebase.config,
            project_targets=(
                ctx.get("project_targets") or ctx.get("firebase_project_targets")
            ),
            projects=ctx.get("projects"),
            brand_projects=ctx.get("brand_projects"),
            brands=ctx.get("brands") or ctx.get("brand"),
            environments=ctx.get("environments") or ctx.get("environment"),
        )
    except (FirebaseClientError, TypeError, ValueError, ValidationError) as exc:
        message = f"Invalid Firebase project targets: {exc}"
        if ctx.textual:
            ctx.textual.error_text(message)
            ctx.textual.end_step("error")
        return Error(message, exception=exc, recoverable=True)
    if not targets:
        message = (
            "No Firebase project targets configured. Configure "
            "plugins.firebase.config.projects or brand_projects."
        )
        if ctx.textual:
            ctx.textual.error_text(message)
            ctx.textual.end_step("error")
        return Error(message)

    continue_on_error = _as_bool(ctx.get("continue_on_error"), default=True)
    loading_message = f"Reading Remote Config keys from {len(targets)} project(s)..."

    try:
        with _loading(ctx, loading_message):
            inventory = ctx.firebase.get_remote_config_inventory(
                targets,
                continue_on_error=continue_on_error,
            )
    except FirebaseAuthRejectedError as exc:
        retry_error = reauthenticate_after_rejected_token(ctx, exc)
        if retry_error:
            if ctx.textual:
                ctx.textual.error_text(retry_error.message)
                ctx.textual.end_step("error")
            return retry_error

        try:
            with _loading(ctx, loading_message):
                inventory = ctx.firebase.get_remote_config_inventory(
                    targets,
                    continue_on_error=continue_on_error,
                )
        except FirebaseClientError as retry_exc:
            message = str(retry_exc)
            if ctx.textual:
                ctx.textual.error_text(message)
                ctx.textual.end_step("error")
            return Error(message, exception=retry_exc)
    except FirebaseClientError as exc:
        message = str(exc)
        if ctx.textual:
            ctx.textual.error_text(message)
            ctx.textual.end_step("error")
        return Error(message, exception=exc)

    if inventory.project_count == 0:
        message = "No Firebase Remote Config project could be read."
        if inventory.failures:
            message = f"{message} First failure: {inventory.failures[0].message}"
        if ctx.textual:
            ctx.textual.error_text(message)
            ctx.textual.end_step("error")
        return Error(message)

    payload = inventory.model_dump(mode="json")
    if ctx.textual:
        ctx.textual.success_text(
            "Remote Config inventory loaded: "
            f"{inventory.key_count} key(s) across {inventory.project_count} project(s)"
        )
        _render_inventory_table(ctx, inventory)
        if inventory.failures:
            ctx.textual.warning_text(
                f"{len(inventory.failures)} project(s) could not be read"
            )
        ctx.textual.end_step("success")

    return Success(
        "Firebase Remote Config inventory loaded",
        metadata={
            "firebase_remoteconfig_inventory": payload,
            "firebase_remoteconfig_keys": payload["keys"],
            "firebase_remoteconfig_targets": payload["targets"],
            "firebase_remoteconfig_project_count": inventory.project_count,
            "firebase_remoteconfig_key_count": inventory.key_count,
            "firebase_remoteconfig_failures": payload["failures"],
        },
    )


def _loading(ctx: WorkflowContext, message: str) -> AbstractContextManager[object]:
    """Return a fresh loading context for each request attempt."""
    if ctx.textual:
        return ctx.textual.loading(message)
    return nullcontext()


def _as_bool(value: Any, *, default: bool) -> bool:
    """Coerce workflow values into a boolean."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off"}:
            return False
    return bool(value)


def _render_inventory_table(ctx: WorkflowContext, inventory: Any) -> None:
    """Render a compact Remote Config keys table in the TUI."""
    if not ctx.textual or not inventory.keys:
        return

    project_count = inventory.project_count
    rows = []
    for key_inventory in inventory.keys:
        observed_types = ", ".join(
            value_type.value for value_type in key_inventory.observed_types
        )
        missing = (
            ", ".join(key_inventory.projects_missing)
            if key_inventory.projects_missing
            else "-"
        )
        rows.append(
            [
                key_inventory.key,
                observed_types or "UNKNOWN",
                f"{len(key_inventory.projects_present)}/{project_count}",
                missing,
            ]
        )

    ctx.textual.table(
        headers=["Key", "Type(s)", "Projects", "Missing in"],
        rows=rows,
        title="Remote Config Keys",
        full_width=True,
        zebra_stripes=True,
        show_cursor=False,
        cursor_type="none",
    )
