"""
The one modal that asks "which model?", wherever that question comes up.

Two very different sources answer it - a gateway's `/models` endpoint and a CLI's own
idea of what it can run - so the modal takes a loader instead of a source: a callable
returning the choices, run off the UI thread because both can block on the network.

Typing an identifier is always available, never a fallback for failure alone. No source
here is authoritative: a gateway lists what it proxies today, a CLI lists what it knew
when it shipped, and some CLIs list nothing at all. A model this modal has never heard
of still has to be reachable, so the free-text entry is a first-class option.
"""

from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Input, LoadingIndicator, OptionList, Static

from titan_cli.ui.tui.icons import Icons
from titan_cli.ui.tui.widgets import (
    Button,
    DimText,
    ErrorText,
    StyledOption,
    StyledOptionList,
)

# Sentinel option ids. Neither is a model identifier any source can return, so they
# cannot collide with a real choice.
CUSTOM_OPTION_ID = "__custom__"
# "stop pinning a model; let the CLI or connection use its own". Until this existed there
# was no way anywhere in the UI to undo a model pin: an emptied text field means "leave it
# alone" on purpose, so clearing needed an action of its own.
DEFAULT_OPTION_ID = "__default__"


@dataclass(frozen=True)
class ModelChoice:
    """One model on offer. `identifier` is saved verbatim; `description` is for display."""

    identifier: str
    description: str = ""


ModelLoader = Callable[[], Sequence[ModelChoice]]


class SelectModelModal(ModalScreen[Optional[str]]):
    """
    Picks a model identifier, from a loaded list or typed by hand.

    Dismisses with the chosen identifier, or `None` if cancelled.
    """

    DEFAULT_CSS = """
    SelectModelModal {
        align: center middle;
    }

    #select-model-container {
        width: 80;
        height: auto;
        background: $surface-lighten-1;
        border: solid $primary;
        padding: 2;
    }

    #select-model-content {
        height: auto;
        max-height: 20;
        margin-top: 1;
    }

    #select-model-buttons {
        height: auto;
        align: center middle;
        margin-top: 2;
    }
    """

    BINDINGS = [("escape", "dismiss_modal", "Cancel")]

    def __init__(
        self,
        title: str,
        subtitle: str,
        loader: ModelLoader,
        *,
        current: Optional[str] = None,
        loading_message: str = "Loading models...",
        empty_message: str = "This source does not publish a model list.",
        instance_noun: str = "CLI",
        allow_clear: bool = False,
        **kwargs,
    ):
        """
        Args:
            title: Heading for the modal.
            subtitle: What the choice applies to, e.g. a connection or CLI name.
            loader: Returns the available models. Called off the UI thread; raising is
                treated as "could not load", which still leaves the typed entry usable.
            current: The identifier in force now, highlighted in the list and prefilled
                in the text entry.
            loading_message: Shown while the loader runs.
            empty_message: Shown when the loader returns nothing.
            instance_noun: What owns the model here - "CLI" or "connection" - used only
                in the wording of the unpin option.
            allow_clear: Offer "use its own default", which dismisses with
                `DEFAULT_OPTION_ID`. Opt-in rather than inferred from `current`, because
                it is not always meaningful: a CLI with no model picks one itself, but a
                remote connection REQUIRES a default_model (create_ai_provider refuses
                without it), so clearing one globally would break it. A task's pin can
                always be cleared - it falls back to the instance's own setting.
        """
        super().__init__(**kwargs)
        self.modal_title = title
        self.subtitle = subtitle
        self.loader = loader
        self.current = current
        self.loading_message = loading_message
        self.empty_message = empty_message
        self.instance_noun = instance_noun
        self.allow_clear = allow_clear

    def compose(self) -> ComposeResult:
        with Container(id="select-model-container"):
            yield Static(f"{Icons.AI_CONFIG} {self.modal_title}")
            yield DimText(self.subtitle)
            yield Container(id="select-model-content")
            with Horizontal(id="select-model-buttons"):
                yield Button("Close", variant="default", id="close-select-model")

    def on_mount(self) -> None:
        content = self.query_one("#select-model-content", Container)
        content.mount(LoadingIndicator())
        content.mount(DimText(self.loading_message))
        self.call_after_refresh(self._start_loading)

    def _start_loading(self) -> None:
        self.run_worker(self._load_models(), exclusive=True)

    async def _load_models(self) -> None:
        import asyncio

        content = self.query_one("#select-model-content", Container)

        error: Optional[str] = None
        try:
            models = list(await asyncio.to_thread(self.loader))
        except Exception as e:
            models, error = [], str(e)

        content.remove_children()

        if error:
            content.mount(ErrorText("Could not load the model list."))
            content.mount(DimText(error))
        elif not models:
            content.mount(DimText(self.empty_message))

        if not models:
            self._mount_custom_entry(content, keep=True)
            return

        content.mount(DimText("Select a model:"))
        option_list = StyledOptionList(*self._options(models), id="model-list")
        content.mount(option_list)

        current_index = next(
            (idx for idx, model in enumerate(models) if model.identifier == self.current),
            0,
        )
        option_list.highlighted = current_index
        self.call_after_refresh(option_list.focus)

    def _options(self, models: Sequence[ModelChoice]) -> List[StyledOption]:
        options: List[StyledOption] = [
            StyledOption(
                id=model.identifier,
                title=(
                    f"{model.identifier} {Icons.CHECK}"
                    if model.identifier == self.current
                    else model.identifier
                ),
                description=model.description,
            )
            for model in models
        ]
        # Both meta-actions go AFTER the models, and the order matters for more than
        # taste: the highlight is computed as an index into `models`, so anything
        # prepended here would silently point it at the wrong row.
        if self.allow_clear and self.current:
            options.append(
                StyledOption(
                    id=DEFAULT_OPTION_ID,
                    title=f"Use the {self.instance_noun}'s own default",
                    description=f"Stop pinning {self.current}",
                )
            )
        options.append(
            StyledOption(
                id=CUSTOM_OPTION_ID,
                title="Type a model identifier...",
                description="For a model this list does not know about",
            )
        )
        return options

    def _mount_custom_entry(self, content: Container, *, keep: bool = False) -> None:
        """Mount the text entry, prefilled with what is in force now.

        `keep` leaves whatever is already on screen in place. The no-list path mounts an
        explanation first - "could not load", or the source's empty message - and clearing
        the content here wiped it before it was ever rendered, leaving a bare input with
        no hint that discovery had failed.
        """
        if not keep:
            content.remove_children()
        content.mount(DimText("Model identifier (Enter to save):"))
        entry = Input(value=self.current or "", id="model-input")
        content.mount(entry)
        self.call_after_refresh(entry.focus)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if getattr(event.option_list, "id", None) != "model-list":
            return
        if event.option.id == CUSTOM_OPTION_ID:
            self._mount_custom_entry(self.query_one("#select-model-content", Container))
            return
        self.dismiss(event.option.id)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        # An emptied field is "leave it alone", not "set the model to nothing": clearing a
        # pinned model is its own action, and guessing which one was meant here would
        # silently change the setting the user came to look at.
        self.dismiss(value or None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close-select-model":
            self.dismiss(None)

    def action_dismiss_modal(self) -> None:
        self.dismiss(None)


def cli_model_loader(cli_name: str) -> ModelLoader:
    """Loader backed by the CLI's own answer to "what can you run?".

    Each adapter decides how to answer - shelling out to a listing subcommand, returning
    the aliases its help publishes, or returning nothing - so this only has to translate
    the result. A CLI with no adapter is not an error here: it simply offers nothing, and
    the modal falls through to the typed entry.
    """

    def load() -> List[ModelChoice]:
        from titan_cli.external_cli.adapters import get_headless_adapter

        try:
            adapter = get_headless_adapter(cli_name)
        except ValueError:
            return []
        return [
            ModelChoice(model.identifier, model.label)
            for model in adapter.list_models()
        ]

    return load


def gateway_model_loader(gateway_client) -> ModelLoader:
    """Loader backed by a gateway's `/models` endpoint.

    Takes an already-authenticated client: the key is the broker's business, and this
    layer never sees one.
    """

    def load() -> List[ModelChoice]:
        if gateway_client is None:
            return []
        return [
            ModelChoice(model.id, model.owned_by or "")
            for model in gateway_client.list_models()
        ]

    return load


def open_model_picker_for_connection(
    app,
    config,
    connection_id: str,
    *,
    on_picked,
    current: Optional[str] = None,
    title: Optional[str] = None,
    allow_clear: bool = False,
) -> None:
    """Ask which model a gateway connection can run, and hand the answer to the caller.

    The connection counterpart of `open_model_picker_for_cli`: asking is all it does, so
    the same picker serves the connection's saved default, a task's pin and a session
    override. Everything before the modal - resolve the connection, refuse a non-gateway,
    authenticate a client through the broker - is shared, which is the reason this is one
    function rather than a copy per caller.

    Args:
        app: The running app, for pushing the modal and notifying.
        config: TitanConfig, reloaded here so the list reflects what is on disk.
        connection_id: The connection whose models are offered.
        on_picked: Called with the chosen identifier, or None when cancelled/unchanged.
        current: The model to prefill and mark as current.
        title: Overrides the default question, for callers pinning something narrower
            than "what this connection defaults to".
    """
    from titan_cli.ai.litellm_client import LiteLLMClient
    from titan_cli.core.models import AIConnectionType
    from titan_cli.core.security import create_broker_factory

    config.load()

    connections = config.config.ai.connections if config.config and config.config.ai else {}
    if connection_id not in connections:
        app.notify("Connection not found", severity="error")
        return

    connection_cfg = connections[connection_id]
    if connection_cfg.connection_type != AIConnectionType.GATEWAY:
        app.notify(
            "Only gateway connections publish a model list. "
            "Set this connection's model in AI Configuration.",
            severity="warning",
        )
        return

    if not connection_cfg.base_url:
        app.notify("Gateway base URL is missing", severity="error")
        return

    # The gateway key crosses into the client constructor inside the broker call; the
    # modal only ever receives the authenticated client. A gateway may legitimately have
    # no key (e.g. a local proxy).
    broker = create_broker_factory(config.project_root).for_plugin("core")
    gateway_client = broker.create_client(
        f"{connection_id}_api_key",
        lambda api_key: LiteLLMClient(
            base_url=connection_cfg.base_url,
            api_key=api_key,
        ),
        required=False,
    )

    app.push_screen(
        SelectModelModal(
            title or "Select gateway model",
            f"Connection: {connection_cfg.name}",
            gateway_model_loader(gateway_client),
            current=current if current is not None else (connection_cfg.default_model or None),
            loading_message="Loading models from gateway...",
            empty_message="This gateway published no models.",
            instance_noun="connection",
            allow_clear=allow_clear,
        ),
        on_picked,
    )


def open_connection_model_picker(app, config, connection_id: str, on_saved=None) -> None:
    """Ask which model a gateway connection should default to, and SAVE the answer.

    Args:
        app: The running app, for pushing the modal and notifying.
        config: TitanConfig, reloaded here so the modal reflects what is on disk.
        connection_id: The connection whose default model is being set.
        on_saved: Called after a successful save, for callers that repaint something.
    """
    # Loaded here as well as inside the shared opener: the value this compares against
    # has to be the one on disk, or an unchanged pick could read as a change.
    config.load()

    connections = config.config.ai.connections if config.config and config.config.ai else {}
    connection_cfg = connections.get(connection_id)
    previous = connection_cfg.default_model if connection_cfg else None
    name = connection_cfg.name if connection_cfg else connection_id

    def on_picked(model: Optional[str]) -> None:
        if not model or model == previous:
            return
        try:
            config.update_ai_connection(connection_id, {"default_model": model})
        except Exception as e:
            app.notify(f"Failed to update model: {e}", severity="error")
            return
        app.notify(f"'{name}' will use {model}.", severity="information")
        if on_saved:
            on_saved()

    open_model_picker_for_connection(app, config, connection_id, on_picked=on_picked)


def _saved_notice(config, cli_name: str, model: str) -> str:
    """What to say after pinning a model, given whether that CLI is the one Titan runs.

    Choosing a model does not switch the default CLI - that is a separate, deliberate
    act. But the status bar reports the default and its model, so pinning a model on any
    other CLI looks like nothing happened. The notice has to close that gap itself, by
    saying both what was saved and why the bar did not move.
    """
    ai_config = config.config.ai if config.config else None
    default_cli = ai_config.default_cli if ai_config else None
    if default_cli == cli_name:
        return f"{cli_name} will run {model}."
    return (
        f"{cli_name} will run {model} - but Titan still runs "
        f"{default_cli or 'no CLI'}. Press Enter on {cli_name} to switch to it."
    )


def open_model_picker_for_cli(
    app,
    cli_name: str,
    *,
    on_picked,
    current: Optional[str] = None,
    title: Optional[str] = None,
    allow_clear: bool = True,
) -> None:
    """Ask which model a CLI should run with, and hand the answer to the caller.

    Asking is all this does - where the answer is stored is the caller's business, which
    is what lets the same picker serve the global pin and a single task's pin. The modal
    itself is already source-agnostic (a loader callable plus free text); only the
    destination ever differed.

    Args:
        app: The running app, for pushing the modal.
        cli_name: The CLI whose model list is offered.
        on_picked: Called with the chosen identifier, or None when cancelled or unchanged.
        current: The model to prefill and mark as current.
        title: Overrides the default question, for callers pinning something narrower
            than "what this CLI runs".
    """
    from titan_cli.external_cli.configs import CLI_REGISTRY

    display_name = CLI_REGISTRY.get(cli_name, {}).get("display_name", cli_name)

    app.push_screen(
        SelectModelModal(
            title or f"Which model should {display_name} run?",
            f"command: {cli_name}",
            cli_model_loader(cli_name),
            current=current,
            loading_message=f"Asking {cli_name} which models it offers...",
            empty_message=(
                f"{display_name} does not publish a model list - type the identifier it "
                "expects."
            ),
            instance_noun="CLI",
            allow_clear=allow_clear,
        ),
        on_picked,
    )


def open_cli_model_picker(app, config, cli_name: str, on_saved=None) -> None:
    """Ask which model a CLI should run with GLOBALLY, and save the answer.

    Args:
        app: The running app, for pushing the modal and notifying.
        config: TitanConfig.
        cli_name: The CLI command name the model is pinned to.
        on_saved: Called after a successful save, for callers that repaint something.
    """
    current = config.get_cli_model(cli_name)

    def on_picked(model: Optional[str]) -> None:
        if not model or model == current:
            return
        # DEFAULT_OPTION_ID is an instruction, not an identifier. Passing it through
        # would pin the literal "__default__" and then hand it to the CLI as
        # `--model __default__`.
        clearing = model == DEFAULT_OPTION_ID
        try:
            if clearing:
                config.clear_cli_model(cli_name)
            else:
                config.set_cli_model(cli_name, model)
        except Exception as e:
            app.notify(f"Failed to set the model: {e}", severity="error")
            return
        app.notify(
            f"{cli_name} will use its own default model."
            if clearing
            else _saved_notice(config, cli_name, model),
            severity="information",
        )
        if on_saved:
            on_saved()

    open_model_picker_for_cli(app, cli_name, on_picked=on_picked, current=current)


__all__ = [
    "DEFAULT_OPTION_ID",
    "ModelChoice",
    "SelectModelModal",
    "open_model_picker_for_cli",
    "open_model_picker_for_connection",
    "CUSTOM_OPTION_ID",
    "cli_model_loader",
    "gateway_model_loader",
    "open_cli_model_picker",
    "open_connection_model_picker",
]
