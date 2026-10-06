"""
The per-task AI picker: which kind of AI serves a task, then which instance and model.

One flow, two callers: the "AI per task" rows of the AI configuration screen and
any mod that pins its own task (`m.ai.configure`). Both open the same widgets -
`SelectProviderTypeModal`, then the `QuickInstanceModal` F2 and F3 use, minus the
session scope - and both write through the same config CRUD, so a task pinned from
a mod's pane is exactly the pin the AI screen would have written.

Callers pass `on_done(notice)`: it runs after a successful write, with the line to
tell the user. Failures are reported here, through `app.notify`.
"""
from typing import Callable, Optional

from titan_cli.ai.router.enums import AIProviderType
from titan_cli.ai.router.models import AIRouteDecision

from .ai_routing import (
    QuickInstanceModal,
    SelectProviderTypeModal,
    TaskRouting,
    cli_choices,
    connection_choices,
    installed_clis,
    provider_type_label,
)

OnDone = Callable[[str], None]


def pick_task_provider(app, config, routing: TaskRouting, on_done: OnDone) -> None:
    """Pick which kind of AI serves a task."""
    task = routing.task

    def on_selected(provider: Optional[str]) -> None:
        if provider is None:
            return
        try:
            # Merges rather than replaces: re-picking the same kind, or moving
            # between the two CLI kinds, must not silently drop the task's pins.
            dropped = config.set_task_ai_provider(task, provider)
        except Exception as e:
            app.notify(f"Failed to save preference: {e}", severity="error")
            return
        notice = f"{routing.label}: {provider_type_label(AIProviderType(provider))}"
        if dropped:
            notice += f" - the pinned {dropped} model no longer applies."
        on_done(notice)

    app.push_screen(SelectProviderTypeModal(f"AI for {routing.label}", routing.executes), on_selected)


def pin_task_instance(
    app,
    config,
    routing: TaskRouting,
    availability,
    on_done: OnDone,
    *,
    pick_model: bool = False,
) -> None:
    """Compose this task's instance and model in one form, then write both at once.

    The same widget F2 and F3 open, minus the session scope - a per-task pin is
    persistent by definition - plus a "follow the default" row, which is the only way
    to undo a pin without the row's Clear taking the provider kind with it.

    One handler for both transports: which one a task takes is decided by what
    currently resolves (D-006).
    """
    from .model_picker import open_model_picker_for_cli, open_model_picker_for_connection

    if not routing.can_pin_instance:
        return
    task = routing.task
    ai_config = config.config.ai if config.config else None
    remote = routing.pins_a_connection

    if remote:
        choices = connection_choices(ai_config.connections if ai_config else {})
        noun = "connection"
        default_instance = ai_config.default_connection if ai_config else None
        empty_message = "No AI connection is configured. Add one and reopen this picker."
        set_instance = config.set_task_ai_connection
        clear_instance = config.clear_task_ai_connection
    else:
        choices = cli_choices(
            installed_clis(
                availability.available_headless_clis(), availability.available_interactive_clis()
            ),
            ai_config.cli_models if ai_config else None,
        )
        noun = "CLI"
        default_instance = ai_config.default_cli if ai_config else None
        empty_message = "No supported CLI is installed. Install one and reopen this picker."
        set_instance = config.set_task_ai_cli
        clear_instance = config.clear_task_ai_cli

    def open_picker(instance, current_model, on_picked) -> None:
        title = f"Which model should run {routing.label}?"
        if remote:
            open_model_picker_for_connection(
                app,
                config,
                instance,
                title=title,
                current=current_model,
                on_picked=on_picked,
                allow_clear=True,
            )
        else:
            open_model_picker_for_cli(
                app, instance, title=title, current=current_model,
                on_picked=on_picked, allow_clear=True,
            )

    def on_composed(result) -> None:
        if result is None or not result.changes_anything:
            return
        provider = provider_for_pin(routing)
        dropped = None
        try:
            if result.clear_instance:
                dropped = clear_instance(task)
            elif result.instance:
                dropped = set_instance(task, result.instance, provider=provider)
            if result.clear_model:
                config.clear_task_ai_model(task)
            elif result.model:
                # D-010: a model pin carries its instance, so pin that too when the
                # task was following the default.
                if not result.instance and not routing.pinned_instance:
                    set_instance(task, effective_instance(config, routing), provider=provider)
                config.set_task_ai_model(task, result.model, provider=provider)
        except ValueError as e:
            app.notify(str(e), severity="warning")
            return
        except Exception as e:
            app.notify(f"Failed to save: {e}", severity="error")
            return
        on_done(pin_notice(routing, result, noun, dropped=dropped))

    modal = QuickInstanceModal(
        f"Which {noun} should run {routing.label}?",
        choices,
        noun=noun,
        remote=remote,
        current=routing.pinned_instance,
        current_model=routing.pinned_model,
        open_model_picker=open_picker,
        empty_message=empty_message,
        allow_session=False,
        inherit_label=(
            "Follow the default"
            + (f" ({default_instance})" if default_instance else "")
        ),
    )
    app.push_screen(modal, on_composed)
    if pick_model and routing.pinned_instance or pick_model and default_instance:
        app.call_after_refresh(modal.action_pick_model)


def pin_notice(routing, result, noun: str, *, dropped: Optional[str] = None) -> str:
    """What happened, including a model pin the instance change invalidated.

    The setters return that precisely so it can be said out loud; swallowing it made
    the notice read "will run on codex" while the user's pinned model quietly went.
    """
    if result.clear_instance:
        notice = f"{routing.label} follows the default {noun} again."
    else:
        parts = [p for p in (result.instance, result.model) if p]
        if result.clear_model and not parts:
            notice = f"{routing.label} uses its {noun}'s own model again."
        else:
            notice = f"{routing.label} will run on {' / '.join(parts)}."
    if dropped and not result.model:
        notice += f" The pinned {dropped} model no longer applies."
    return notice


def effective_instance(config, routing) -> Optional[str]:
    """The CLI or connection this task runs on today: its own pin, else the default."""
    if routing.pinned_instance:
        return routing.pinned_instance
    resolution = routing.resolution
    if isinstance(resolution, AIRouteDecision):
        instance = resolution.connection_id if routing.pins_a_connection else resolution.cli
        if instance:
            return instance
    ai_config = config.config.ai if config.config else None
    if not ai_config:
        return None
    return ai_config.default_connection if routing.pins_a_connection else ai_config.default_cli


def provider_for_pin(routing) -> Optional[str]:
    """
    The provider kind to create a preference with, when a pin is the first thing set.

    Taken from what currently resolves, so pinning a CLI on an unconfigured task
    records the kind that was already in effect rather than inventing one. None when
    nothing resolves - the CRUD then refuses and the user is told to pick a kind first.
    """
    resolution = routing.resolution
    if isinstance(resolution, AIRouteDecision):
        return str(resolution.provider)
    return None
