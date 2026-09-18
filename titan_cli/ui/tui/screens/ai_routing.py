"""
Per-task AI routing: the widgets and the pure logic behind the "AI per task" and "CLI"
sections of the AI Configuration screen.

The unit a user configures is the TASK ("for commit messages, use X"), not the step, the
workflow or the plugin - those are how the setting is discovered, not how it is chosen. So
discovery output is aggregated by task here, and each row offers only KINDS of provider.
Which connection or CLI serves a kind is one global setting, set once in the CLI section and
in the connections grid.
"""

import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Mapping, Optional, Sequence

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.css.query import NoMatches
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import OptionList, Static

from titan_cli.ai.router.availability import AIProviderAvailability
from titan_cli.ai.router.enums import (
    AIProviderType,
    AIRouteOrigin,
    provider_description,
    provider_label,
)
from titan_cli.ai.router.models import AIRouteDecision, AIRoutePolicy
from titan_cli.ai.router.resolver import AIRouteNeedsInput, AIRouteResolution, AIRouteResolver
from titan_cli.core.models import AIProviderPreference
from titan_cli.core.workflows.ai_usage_discovery import (
    DiscoveredAIStep,
    DiscoveredWorkflowAIUsage,
)
from titan_cli.ui.tui.icons import Icons
from titan_cli.ui.tui.screens.model_picker import DEFAULT_OPTION_ID
from titan_cli.ui.tui.widgets import (
    Button,
    DimText,
    ErrorText,
    StyledOption,
    StyledOptionList,
    SuccessText,
    WarningText,
)

# Human labels for the task keys official plugins use. A task not listed here - a community
# plugin's own key - falls back to its humanized raw value, so the row is still readable.
TASK_LABELS: Dict[str, str] = {
    "commit_message": "Commit messages",
    "pr_description": "PR descriptions",
    "issue_generation": "Issue generation",
    "jira_analysis": "Jira issue analysis",
    "jira_issue_enhancement": "Jira issue descriptions",
    "code_review_plan": "Code review plan",
    "code_review_findings": "Code review findings",
    "thread_resolution": "Review thread resolution",
    "respond_pr_comment": "PR comment replies",
    "fix_test_failures": "Test failure fixes",
    "fix_lint_failures": "Lint failure fixes",
    "generic_assistant": "Code assistant",
    "slack_summary": "Slack summaries",
}


def task_label(task: str) -> str:
    """A readable name for a task key, including ones this module has never seen."""
    return TASK_LABELS.get(task, task.replace("_", " ").capitalize())


def provider_type_label(provider: AIProviderType) -> str:
    """Kept as the UI's entry point to the router's own vocabulary."""
    return provider_label(provider)


def widget_key(task: str) -> str:
    """A widget-id-safe form of a task key."""
    return re.sub(r"[^a-zA-Z0-9_-]", "-", task)


@dataclass
class TaskRouting:
    """Everything one row of the "AI per task" section needs to render itself."""

    task: str
    label: str
    workflows: List[str] = field(default_factory=list)
    executes: List[AIProviderType] = field(default_factory=list)
    resolution: Optional[AIRouteResolution] = None
    has_preference: bool = False
    unenforced_steps: List[str] = field(default_factory=list)
    pinned_cli: Optional[str] = None
    pinned_connection: Optional[str] = None
    pinned_model: Optional[str] = None

    @property
    def configurable(self) -> bool:
        """Whether there is anything honest to offer the user for this task."""
        return bool(self.executes)

    @property
    def resolved_provider(self) -> Optional[AIProviderType]:
        """The kind actually serving this task right now, if it resolves at all."""
        if isinstance(self.resolution, AIRouteDecision):
            return self.resolution.provider
        return None

    @property
    def can_pin_instance(self) -> bool:
        """
        Whether it makes sense to offer this task an instance and a model of its own.

        Keyed on the kind that RESOLVES, not on everything the task could run: a pin
        names a CLI or a connection, and which of those is meaningful depends on what is
        serving the task today. A task set to `off`, or one that does not resolve, gets
        nothing - the same rule as `configurable`, one level down.
        """
        return self.resolved_provider in (
            AIProviderType.REMOTE,
            AIProviderType.CLI_HEADLESS,
            AIProviderType.CLI_INTERACTIVE,
        )

    @property
    def pins_a_connection(self) -> bool:
        """Whether the instance in effect is a remote connection rather than a CLI."""
        return self.resolved_provider == AIProviderType.REMOTE

    @property
    def pinned_instance(self) -> Optional[str]:
        """The pinned instance for the kind in effect, if there is one."""
        return self.pinned_connection if self.pins_a_connection else self.pinned_cli

    @property
    def needs_setup(self) -> bool:
        """
        Whether this row is asking the user for something.

        Either nothing can run the task, or resolution could not pick a provider - a missing
        default, an uninstalled one, or a stored preference the step cannot execute. Both are
        "you have to do something here", which is what the row's warning border marks.
        """
        return not self.configurable or isinstance(self.resolution, AIRouteNeedsInput)


def executable_types(steps: Sequence[DiscoveredAIStep]) -> List[AIProviderType]:
    """
    The provider types EVERY step behind a task can run.

    An intersection, not a union: one setting drives all of them, so offering a type only
    some can execute would configure a guaranteed failure for the rest. Steps that declare
    nothing contribute no constraint - they are unrouted anyway, and treating their silence
    as "supports nothing" would empty the intersection for everyone sharing the task.
    """
    declared = [set(step.policy.executes) for step in steps if step.policy.executes]
    if not declared:
        return []
    return [
        provider
        for provider in AIProviderType
        if provider != AIProviderType.OFF and all(provider in d for d in declared)
    ]


def _merged_policy(task: str, steps: Sequence[DiscoveredAIStep]) -> AIRoutePolicy:
    """
    One policy standing in for every step behind a task, used to preview resolution.

    `executes` is what they can all run; `preferred` keeps the first step's order, minus
    anything the others can't run, so the preview matches what the majority case - a single
    declaring step - would actually do.
    """
    executes = executable_types(steps)
    preferred = [p for p in (steps[0].policy.preferred if steps else []) if p in executes]
    return AIRoutePolicy(task=task, executes=executes, preferred=preferred)


def build_task_routings(
    usages: Sequence[DiscoveredWorkflowAIUsage],
    resolver: AIRouteResolver,
    preferences: Optional[Mapping[str, AIProviderPreference]] = None,
) -> List[TaskRouting]:
    """
    Aggregate discovered steps into one entry per task, resolved and ready to render.

    `preferences` is the persisted `AIPreferences.tasks` mapping. The rows need the whole
    preference, not just which tasks have one, because a pinned CLI or model is part of
    what a row has to state - and a row that shows an instance without saying whether it
    was pinned or inherited is exactly the staleness confusion pins can cause.
    """
    persisted = dict(preferences or {})
    steps_by_task: Dict[str, List[DiscoveredAIStep]] = {}
    workflows_by_task: Dict[str, List[str]] = {}

    for usage in usages:
        for step in usage.steps:
            steps_by_task.setdefault(step.policy.task, []).append(step)
            workflows = workflows_by_task.setdefault(step.policy.task, [])
            if usage.workflow_name not in workflows:
                workflows.append(usage.workflow_name)

    routings = []
    for task, steps in steps_by_task.items():
        policy = _merged_policy(task, steps)
        routings.append(
            TaskRouting(
                task=task,
                label=task_label(task),
                workflows=workflows_by_task.get(task, []),
                executes=policy.executes,
                resolution=resolver.resolve(task=task, policy=policy),
                has_preference=task in persisted,
                unenforced_steps=[s.step_name for s in steps if not s.enforces],
                pinned_cli=getattr(persisted.get(task), "cli", None),
                pinned_connection=getattr(persisted.get(task), "connection", None),
                pinned_model=getattr(persisted.get(task), "model", None),
            )
        )

    return sorted(routings, key=lambda r: r.label.lower())


def installed_clis(
    headless: Sequence[AIProviderAvailability],
    interactive: Sequence[AIProviderAvailability],
) -> List[str]:
    """
    Every CLI usable in either mode, in a stable order.

    One CLI serves both modes - the same binary, invoked differently - so the two lists are
    merged into the single choice the user actually makes.
    """
    names: List[str] = []
    for candidate in list(headless) + list(interactive):
        if candidate.identifier not in names:
            names.append(candidate.identifier)
    return names


def cli_option_description(cli_name: str, model: Optional[str]) -> str:
    """The second line of a CLI's row: how it is invoked, and with which model.

    The model is shown even when nothing is pinned, because "CLI default" is itself the
    answer to the question the row raises - otherwise a blank reads as "unknown" and the
    user has to open the picker to find out nothing is set.
    """
    return f"command: {cli_name} · model: {model or 'CLI default'}"


def tasks_pinning(preferences, *, remote: bool) -> List[str]:
    """
    Human labels of the tasks that pin their own instance, so a quick picker can say so.

    This is what stops F2/F3 from looking broken. A pinned task deliberately ignores the
    key, and a user who set one pin weeks ago has no way to remember that - they just see
    a CLI change that did not take.

    Args:
        preferences: The persisted `AIPreferences.tasks` mapping, or None.
        remote: True for connection pins (F3), False for CLI pins (F2). Each key only
            reports the pins it is actually unable to move.
    """
    if not preferences:
        return []
    field = "connection" if remote else "cli"
    return sorted(
        task_label(task)
        for task, preference in preferences.items()
        if getattr(preference, field, None)
    )


def suggested_cli(installed: Sequence[str], current_default: Optional[str]) -> Optional[str]:
    """
    The CLI to highlight when no default is set yet.

    Only when there is exactly one installed: with one candidate there is nothing to get
    wrong, while picking among several would be choosing for the user. Highlighting is not
    saving - the user still confirms.
    """
    if current_default or len(installed) != 1:
        return None
    return installed[0]


class SelectProviderTypeModal(ModalScreen[Optional[str]]):
    """
    Modal for choosing which KIND of AI runs a task.

    Dismisses with an `AIProviderType` value, or `None` if cancelled.
    """

    DEFAULT_CSS = """
    SelectProviderTypeModal {
        align: center middle;
    }

    #select-type-container {
        width: 74;
        height: auto;
        max-height: 26;
        background: $surface-lighten-1;
        border: solid $primary;
        padding: 2;
    }

    #select-type-list {
        height: auto;
        max-height: 16;
        margin-top: 1;
    }

    #select-type-buttons {
        height: auto;
        align: right middle;
        margin-top: 2;
    }
    """

    BINDINGS = [("escape", "dismiss_modal", "Cancel")]

    def __init__(self, title: str, choices: Sequence[AIProviderType], **kwargs):
        super().__init__(**kwargs)
        self.title_text = title
        self.choices = list(choices)

    def compose(self) -> ComposeResult:
        with Container(id="select-type-container"):
            yield Static(f"{Icons.AI_CONFIG} {self.title_text}")
            options = [
                StyledOption(
                    id=str(choice),
                    title=provider_type_label(choice),
                    description=provider_description(choice),
                )
                for choice in self.choices
            ]
            options.append(
                StyledOption(
                    id=str(AIProviderType.OFF),
                    title=provider_type_label(AIProviderType.OFF),
                    description=provider_description(AIProviderType.OFF),
                )
            )
            yield StyledOptionList(*options, id="select-type-list")
            with Horizontal(id="select-type-buttons"):
                yield Button("Cancel", variant="default", id="cancel-select-type")

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_list.id != "select-type-list":
            return
        self.dismiss(event.option.id)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-select-type":
            self.dismiss(None)

    def action_dismiss_modal(self) -> None:
        self.dismiss(None)


# Sentinel option id meaning "stop pinning; follow whatever the global default is".
# A pin is an override, so removing one has to be expressible in the same picker that
# sets it - otherwise the only way back is the row's Clear, which also drops the
# provider kind the user chose.
TASK_CLI_INHERIT_OPTION = "__inherit__"


@dataclass(frozen=True)
class InstanceChoice:
    """One selectable instance - a CLI or a remote connection - and how it reads.

    `model` is the one that instance runs today. It rides along because a picker showing
    "codex / haiku" after you highlight codex - haiku being claude's model - is the same
    class of mistake the routing layer spent D-007 and D-008 removing, and it cannot be
    avoided by a widget that only knows the CURRENT instance's model.
    """

    identifier: str
    title: str
    description: str = ""
    model: Optional[str] = None


def cli_choices(
    installed: Sequence[str], models: Optional[Dict[str, str]] = None
) -> List[InstanceChoice]:
    """Installed CLIs, described the way the global CLI section describes them."""
    from titan_cli.external_cli.configs import CLI_REGISTRY

    pinned_models = dict(models or {})
    return [
        InstanceChoice(
            identifier=name,
            title=CLI_REGISTRY.get(name, {}).get("display_name", name),
            description=cli_option_description(name, pinned_models.get(name)),
            model=pinned_models.get(name),
        )
        for name in installed
    ]


def connection_choices(connections: Mapping[str, object]) -> List[InstanceChoice]:
    """Configured remote connections, described by what answers and with which model."""
    return [
        InstanceChoice(
            identifier=connection_id,
            title=getattr(cfg, "name", connection_id),
            description=(
                f"model: {getattr(cfg, 'default_model', None) or 'connection default'}"
            ),
            model=getattr(cfg, "default_model", None),
        )
        for connection_id, cfg in connections.items()
    ]


@dataclass(frozen=True)
class QuickPickResult:
    """What the quick picker was composed into, and what scope to apply it at.

    Every field is a change the user actually made: `None` means "leave this alone", so a
    result that changes nothing is possible and means exactly that.
    """

    instance: Optional[str] = None
    model: Optional[str] = None
    clear_instance: bool = False
    clear_model: bool = False
    session_only: bool = False
    clear_session: bool = False

    @property
    def changes_anything(self) -> bool:
        return bool(
            self.instance
            or self.model
            or self.clear_instance
            or self.clear_model
            or self.clear_session
        )


# What the modal calls to ask for a model, given the instance it is composing for. The
# modal knows nothing about config, brokers or gateways; the caller supplies this.
#   (instance, current_model, on_picked) -> None
OpenModelPicker = Callable[[str, Optional[str], Callable[[Optional[str]], None]], None]


class QuickInstanceModal(ModalScreen[Optional["QuickPickResult"]]):
    """
    The quick picker behind F2 and F3: one component, two vocabularies.

    F2 loads it with CLIs and F3 with remote connections. They are the same question asked
    of different transports, so they are the same widget - a change to one IS a change to
    both, which is the only way the two keys stay honest about each other (domain symmetry
    rule, D-006).

    It is a FORM, not a list that acts on the first keystroke. Choosing a row marks a
    pending selection and moves focus to Save; `M` asks for a model and comes back here
    rather than closing and writing; Cancel writes nothing, the model included. The scope
    is the LAST decision rather than the first: Save persists, `S` applies the same
    composition for this session only. That ordering is what makes a session-scoped model
    expressible at all (D-009).
    """

    DEFAULT_CSS = """
    QuickInstanceModal {
        align: center middle;
    }

    #quick-instance-container {
        width: 78;
        height: auto;
        /* Bounded by the viewport, not by a fixed number of rows: the list gives up
           space first, so the pending line and the hint - the only things that explain
           what the keys do - are never what gets clipped. A fixed max-height hid them
           exactly when there was most to say. `vh` rather than `%`, which resolves
           against the centred screen and left dead space below the buttons. */
        max-height: 90vh;
        background: $surface-lighten-1;
        border: solid $primary;
        padding: 2;
    }

    #quick-instance-list {
        height: auto;
        max-height: 55vh;
        margin-top: 1;
    }

    #quick-instance-pending {
        margin-top: 1;
    }

    #quick-instance-pinned {
        margin-top: 1;
    }

    #quick-instance-hint {
        margin-top: 1;
    }

    #quick-instance-buttons {
        height: auto;
        align: right middle;
        margin-top: 1;
    }

    #quick-instance-buttons Button {
        margin-left: 1;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("m", "pick_model", "Model"),
        # Both are no-ops when `allow_session` is False rather than being removed: a
        # binding list cannot vary per instance, and the actions guard themselves.
        ("s", "use_for_session", "This session"),
        ("c", "clear_session", "Clear override"),
    ]

    def __init__(
        self,
        question: str,
        choices: Sequence[InstanceChoice],
        *,
        noun: str = "CLI",
        remote: bool = False,
        current: Optional[str] = None,
        current_model: Optional[str] = None,
        session_override=None,
        pinned_tasks: Optional[Sequence[str]] = None,
        open_model_picker: Optional[OpenModelPicker] = None,
        empty_message: Optional[str] = None,
        allow_session: bool = True,
        inherit_label: Optional[str] = None,
        **kwargs,
    ):
        """
        Args:
            question: The heading, e.g. "Which CLI should Titan run?".
            choices: The instances on offer, already rendered for display.
            noun: "CLI" or "connection". Wording only.
            remote: Which half of the session override this picker owns. A CLI picker
                must not report - or offer to clear - a connection override and vice
                versa: they are set by different keys and shown in different cells, so
                naming the other one here is information the user cannot act on from
                where they are standing.
            current: What is in force now, and where the pending selection starts.
            current_model: The model in force for `current`, shown while nothing is pending.
            session_override: The live `AISessionOverride`, to report and to clear.
            pinned_tasks: Tasks that pin their own instance, named so the key is not
                mistaken for broken when they do not follow a Save.
            open_model_picker: How to ask for a model. Keeps config out of this widget.
            empty_message: Shown instead of the list when nothing is available.
            allow_session: Offer the session scope. False for a per-task pin, which is
                persistent by definition - there is no "just for now" version of it, so
                the form has two actions there instead of three.
            inherit_label: When given, the list opens with an option that means "stop
                pinning; follow the default". Only a per-task pin has something to
                inherit FROM; the global picker is the default.
        """
        super().__init__(**kwargs)
        self.question = question
        self.choices = list(choices)
        self.noun = noun
        self.remote = remote
        self.current = current
        self.current_model = current_model
        self.session_override = session_override
        self.pinned_tasks = list(pinned_tasks or ())
        self.open_model_picker = open_model_picker
        self.empty_message = empty_message
        self.allow_session = allow_session
        self.inherit_label = inherit_label

        self.pending_instance = current
        self.pending_model: Optional[str] = None
        self.model_touched = False

    # --- rendering ---------------------------------------------------------

    def compose(self) -> ComposeResult:
        with Container(id="quick-instance-container"):
            yield Static(f"{Icons.AI_CONFIG} {self.question}")
            if not self.choices:
                yield WarningText(
                    f"{Icons.WARNING} "
                    + (self.empty_message or f"No {self.noun} is available.")
                )
                yield DimText("Esc to close.")
                return

            yield StyledOptionList(*self._options(), id="quick-instance-list")
            yield DimText(self._pending_text(), id="quick-instance-pending")

            override = self.session_override
            if override is not None and override.is_active_for(self.remote):
                yield WarningText(
                    f"{Icons.WARNING} Session override active: "
                    f"{override.describe_for(self.remote)}. C to clear it."
                )

            # Tasks pinning their own instance do not follow a SAVE - but `S` still moves
            # them, because a session override outranks a pin (D-008). Saying "will not
            # change" flatly would be a lie in the one line written to prevent one.
            if self.pinned_tasks:
                count = len(self.pinned_tasks)
                names = ", ".join(self.pinned_tasks[:3])
                more = f" and {count - 3} more" if count > 3 else ""
                yield DimText(
                    f"{count} task{'s' if count != 1 else ''} pin their own {self.noun} and "
                    f"will not follow a save: {names}{more}. S still applies to them.",
                    id="quick-instance-pinned",
                )

            session_hint = " · S for this session only" if self.allow_session else ""
            yield DimText(
                f"Enter to choose · M for its model{session_hint} · "
                "Esc to cancel. Nothing is saved until you accept.",
                id="quick-instance-hint",
            )
            with Horizontal(id="quick-instance-buttons"):
                yield Button("Cancel", variant="default", id="quick-instance-cancel")
                if self.allow_session:
                    yield Button(
                        "This session", variant="default", id="quick-instance-session"
                    )
                yield Button("Save", variant="primary", id="quick-instance-save")

    def _options(self) -> List[StyledOption]:
        """One row per instance, marking what is SAVED and what is PENDING apart.

        Two different facts that a single check mark would blur: the user has to be able
        to see what Save is about to do before pressing it.
        """
        options = []
        if self.inherit_label:
            inherit_marks = ""
            if self.current is None:
                inherit_marks += f" {Icons.CHECK}"
            if self.pending_instance == TASK_CLI_INHERIT_OPTION:
                inherit_marks += " (selected)"
            options.append(
                StyledOption(
                    id=TASK_CLI_INHERIT_OPTION,
                    title=f"{self.inherit_label}{inherit_marks}",
                    description=(
                        f"No pin: this task moves with the {self.noun} you set for Titan."
                    ),
                )
            )
        for choice in self.choices:
            marks = ""
            if choice.identifier == self.current:
                marks += f" {Icons.CHECK}"
            if choice.identifier == self.pending_instance != self.current:
                marks += " (selected)"
            options.append(
                StyledOption(
                    id=choice.identifier,
                    title=f"{choice.title}{marks}",
                    description=choice.description,
                )
            )
        return options

    def _pending_text(self) -> str:
        """One line naming what accepting would do, and for how long.

        The scope has to be here and not only on the buttons: "Will apply: codex / haiku"
        reads the same whether it is about to be written to disk or held until the app
        closes, and those are very different things to do by accident.
        """
        instance = self.pending_instance or self.current
        model = (
            self.pending_model if self.model_touched else self._model_of(instance)
        )
        if not self._has_changes():
            return f"Currently: {instance or '—'} / {model or 'default'}"
        if self.pending_instance == TASK_CLI_INHERIT_OPTION:
            return (
                f"Will apply: follow the default {self.noun}"
                "  —  Save to keep it, S for this session only"
                if self.allow_session
                else f"Will apply: follow the default {self.noun}"
            )
        # No model of its own reads as "its own default", never as "unchanged": the
        # question the line answers is what will run, and that instance running its own
        # default IS the answer.
        scope = (
            "  —  Save to keep it, S for this session only" if self.allow_session else ""
        )
        return f"Will apply: {instance or '—'} / {model or f'{self.noun} default'}{scope}"

    def _model_of(self, instance: Optional[str]) -> Optional[str]:
        """The model that instance runs today, as the list itself reports it."""
        if not instance or instance == TASK_CLI_INHERIT_OPTION:
            return None
        # `current_model` first: in the per-task flow the choices carry each instance's
        # GLOBAL model while current_model is the task's own pin, so letting the loop
        # win showed the global one and pre-selected the wrong row in the picker.
        if instance == self.current and self.current_model:
            return self.current_model
        for choice in self.choices:
            if choice.identifier == instance:
                return choice.model
        return self.current_model if instance == self.current else None

    def _has_changes(self) -> bool:
        return self.pending_instance != self.current or self.model_touched

    def _refresh(self) -> None:
        try:
            option_list = self.query_one("#quick-instance-list", StyledOptionList)
            pending = self.query_one("#quick-instance-pending", DimText)
        except NoMatches:
            return
        # Prompts are replaced IN PLACE rather than the list being rebuilt. A
        # clear_options() + add cycle leaves Textual painting stale lines - rows render
        # with another row's text while their ids stay correct, which is the worst shape
        # for it because nothing downstream disagrees with the screen. CliDefaultPicker
        # already repaints this way for the same reason; the row set never changes here,
        # only its markers, so there is nothing to rebuild.
        for index, option in enumerate(self._options()):
            option_list.replace_option_prompt_at_index(
                index, f"[bold]{option.title}[/bold]\n[dim]{option.description}[/dim]"
            )
        pending.update(self._pending_text())

    def on_mount(self) -> None:
        if self.current is None or not self.choices:
            return
        identifiers = [c.identifier for c in self.choices]
        if self.current in identifiers:
            index = identifiers.index(self.current)
            # The inherit row sits at index 0 when present, so the list index runs one
            # ahead of the choice index. `_highlighted_instance` compensated for that
            # and this did not, which left `M` opening the model picker for the wrong
            # instance on a per-task pin.
            if self.inherit_label:
                index += 1
            self.call_after_refresh(self._highlight, index)

    def _highlight(self, index: int) -> None:
        try:
            self.query_one("#quick-instance-list", StyledOptionList).highlighted = index
        except NoMatches:
            return

    # --- composing ---------------------------------------------------------

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if getattr(event.option_list, "id", None) != "quick-instance-list":
            return
        if event.option.id is None:
            return
        if event.option.id != self.pending_instance:
            # A model belongs to the instance it was chosen for, so choosing another
            # instance forgets it - the same rule the config and the session override
            # both follow (D-007).
            self.pending_model = None
            self.model_touched = False
        self.pending_instance = event.option.id
        self._refresh()
        # Move to Save so the choice is still one Enter away, now with the consequence
        # visible on screen first.
        try:
            self.query_one("#quick-instance-save", Button).focus()
        except NoMatches:
            pass

    def action_pick_model(self) -> None:
        """Ask for a model for the pending instance, and come back here with it."""
        instance = self._highlighted_instance() or self.pending_instance
        if (
            not instance
            or instance == TASK_CLI_INHERIT_OPTION
            or self.open_model_picker is None
        ):
            return
        if instance != self.pending_instance:
            self.pending_instance = instance
            self.pending_model = None
            self.model_touched = False

        current = self.pending_model if self.model_touched else self._model_of(instance)

        def on_picked(model: Optional[str]) -> None:
            if model is None:
                return
            self.pending_model = None if model == DEFAULT_OPTION_ID else model
            self.model_touched = True
            self._refresh()

        self.open_model_picker(instance, current, on_picked)

    def _highlighted_instance(self) -> Optional[str]:
        try:
            option_list = self.query_one("#quick-instance-list", StyledOptionList)
        except NoMatches:
            return None
        index = option_list.highlighted
        if index is None:
            return None
        if self.inherit_label:
            if index == 0:
                return TASK_CLI_INHERIT_OPTION
            index -= 1
        if not (0 <= index < len(self.choices)):
            return None
        return self.choices[index].identifier

    # --- accepting ---------------------------------------------------------

    def _result(self, *, session_only: bool) -> QuickPickResult:
        if self.pending_instance == TASK_CLI_INHERIT_OPTION:
            return QuickPickResult(clear_instance=True, session_only=session_only)
        return QuickPickResult(
            instance=(
                self.pending_instance
                if self.pending_instance != self.current or session_only
                else None
            ),
            model=self.pending_model if self.model_touched else None,
            clear_model=self.model_touched and self.pending_model is None,
            session_only=session_only,
        )

    def action_accept(self) -> None:
        self.dismiss(self._result(session_only=False) if self._has_changes() else None)

    def action_use_for_session(self) -> None:
        """Apply the composition for this session only, writing nothing.

        Refused where there is no session scope: a per-task pin is persistent by
        definition, so "just for now" would have nowhere to live.

        Unlike Save this is worth doing even with nothing changed: "run the current
        default, but only until I close Titan" is not a thing to express, so an untouched
        `S` is treated as choosing what is highlighted.
        """
        if not self.allow_session:
            return
        if not self._has_changes() and self._highlighted_instance():
            self.pending_instance = self._highlighted_instance()
        self.dismiss(self._result(session_only=True))

    def action_clear_session(self) -> None:
        override = self.session_override
        if not self.allow_session or override is None or not override.is_active_for(self.remote):
            return
        self.dismiss(QuickPickResult(clear_session=True))

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "quick-instance-save":
            self.action_accept()
        elif event.button.id == "quick-instance-session":
            self.action_use_for_session()
        elif event.button.id == "quick-instance-cancel":
            self.action_cancel()


def _origin_label(origin: Optional[str], *, noun: Optional[str] = None) -> str:
    """How a row names where a resolved value came from.

    Wordier than the enum on purpose: a row is read at rest, not mid-run, so "pinned
    here" and "this session" say more than "pinned" and "session" would.
    """
    if origin == AIRouteOrigin.PINNED:
        return "pinned here"
    if origin == AIRouteOrigin.SESSION:
        return "this session"
    if origin == AIRouteOrigin.STEP:
        return "asked for by the step"
    return f"default for this {noun.lower()}" if noun else "default"


class TaskRoutingRow(Container):
    """One task, what currently serves it, and how to change that."""

    DEFAULT_CSS = """
    TaskRoutingRow {
        height: auto;
        width: 100%;
        padding: 1 2;
        margin-bottom: 1;
        background: $surface;
        border-left: thick $primary;
    }

    TaskRoutingRow.needs-setup {
        border-left: thick $warning;
    }

    TaskRoutingRow .task-name {
        text-style: bold;
    }

    TaskRoutingRow .task-options-heading {
        margin-top: 1;
    }

    TaskRoutingRow .task-buttons {
        height: auto;
        align: right middle;
        margin-top: 1;
    }

    TaskRoutingRow .task-buttons Button {
        margin-left: 1;
    }
    """

    def __init__(self, routing: TaskRouting, **kwargs):
        super().__init__(**kwargs)
        self.routing = routing

    def compose(self) -> ComposeResult:
        routing = self.routing
        yield Static(routing.label, classes="task-name")

        # A task nothing can execute gets no options and no actions - offering either would
        # be inviting the user to configure something that cannot take effect.
        if not routing.configurable:
            yield DimText(self._usage_summary())
            yield WarningText(
                f"{Icons.WARNING} This one can't be changed yet - these steps pick their own AI."
            )
            # A preference saved while the task was still routable would silently re-apply
            # the moment it becomes routable again - keep the way out visible.
            if routing.has_preference:
                yield DimText(
                    "A saved preference for this task still exists and will apply "
                    "if it becomes configurable again."
                )
                with Horizontal(classes="task-buttons"):
                    yield Button(
                        "Clear",
                        variant="default",
                        id=f"task-clear-{widget_key(routing.task)}",
                    )
            return

        yield from self._resolution_lines()
        yield DimText(self._usage_summary())

        if routing.unenforced_steps:
            yield WarningText(
                f"{Icons.WARNING} May not be honored by: "
                f"{', '.join(routing.unenforced_steps)}"
            )

        # The options are listed here, not just behind the button: knowing whether a task can
        # even run on a CLI is the reason you would open the picker at all.
        yield DimText("Can run on:", classes="task-options-heading")
        for provider in routing.executes:
            yield DimText(
                f"  · {provider_type_label(provider)} — {provider_description(provider)}",
                classes="task-option",
            )

        with Horizontal(classes="task-buttons"):
            yield Button(
                "Change", variant="primary", id=f"task-change-{widget_key(routing.task)}"
            )
            if routing.can_pin_instance:
                yield Button(
                    "Connection" if routing.pins_a_connection else "CLI",
                    variant="default",
                    id=f"task-cli-{widget_key(routing.task)}",
                )
                yield Button(
                    "Model", variant="default", id=f"task-model-{widget_key(routing.task)}"
                )
            if routing.has_preference:
                yield Button(
                    "Clear", variant="default", id=f"task-clear-{widget_key(routing.task)}"
                )

    def _resolution_lines(self) -> ComposeResult:
        resolution = self.routing.resolution
        origin = "your pick" if self.routing.has_preference else "default"

        if isinstance(resolution, AIRouteDecision):
            if resolution.provider == AIProviderType.OFF:
                yield DimText(f"{Icons.CHECK} Off  ({origin})")
                return
            instance = resolution.cli or resolution.connection_id or ""
            suffix = f" · {instance}" if instance else ""
            yield SuccessText(
                f"{Icons.CHECK} {provider_type_label(resolution.provider)}{suffix}  ({origin})"
            )
            yield from self._instance_lines(resolution)
        elif isinstance(resolution, AIRouteNeedsInput):
            if resolution.candidates:
                yield WarningText(f"{Icons.WARNING} Needs setup - {resolution.reason}")
            else:
                yield ErrorText(f"{Icons.ERROR} No AI available - {resolution.reason}")

    def _instance_lines(self, resolution: AIRouteDecision) -> ComposeResult:
        """
        Where the CLI and the model came from: this task, or the global default.

        This is the line that keeps pins honest. The resolution above names the instance
        but not its origin, so without this a user who pinned one task cannot tell why
        pressing F2 moved some rows and not others - which is the whole failure mode a
        per-task override introduces.
        """
        instance = resolution.cli or resolution.connection_id
        if not instance:
            return

        remote = self.routing.pins_a_connection
        noun = "Connection" if remote else "CLI"
        # Read off the DECISION, never re-derived from the stored preference: with a
        # session override active the resolver is serving something the task never
        # pinned, and labelling it "pinned here" claimed a setting the user did not
        # make - while the model, skipped by the rung guard, was labelled the same way.
        yield DimText(f"  {noun}: {instance} ({_origin_label(resolution.instance_origin)})")
        if resolution.model:
            yield DimText(
                f"  Model: {resolution.model} "
                f"({_origin_label(resolution.model_origin, noun=noun)})"
            )
        else:
            yield DimText(f"  Model: {noun} default")

    def _usage_summary(self) -> str:
        count = len(self.routing.workflows)
        if count == 1:
            return f"used by 1 workflow: {self.routing.workflows[0]}"
        return f"used by {count} workflows"


class CliDefaultPicker(Container):
    """
    The one CLI Titan runs, as a single control.

    A vertical option list rather than a segmented switch: segments only fit the raw
    command name and grow the control horizontally with every CLI added, while a list
    scales down the screen, has room for the human-readable name next to the command,
    and matches how every other screen in the app presents a choice.
    """

    class Changed(Message):
        """Sent when the user picks a CLI from the list."""

        def __init__(self, sender: "CliDefaultPicker", value: str):
            super().__init__()
            self.sender = sender
            self.value = value

    class ModelRequested(Message):
        """Sent when the user asks to choose the model for the highlighted CLI."""

        def __init__(self, sender: "CliDefaultPicker", value: str):
            super().__init__()
            self.sender = sender
            self.value = value

    DEFAULT_CSS = """
    CliDefaultPicker {
        height: auto;
        width: 100%;
    }

    CliDefaultPicker StyledOptionList {
        height: auto;
        max-height: 30;
        width: 80;
        margin: 1 0;
        border: round $primary;
        background: transparent;
    }

    CliDefaultPicker StyledOptionList:focus {
        border: round $accent;
    }

    CliDefaultPicker .cli-note {
        margin-top: 1;
    }
    """

    BINDINGS = [("m", "pick_model", "Model")]

    def __init__(
        self,
        installed: Sequence[str],
        *,
        current: Optional[str],
        models: Optional[Dict[str, str]] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.installed = list(installed)
        self.models = dict(models or {})
        # A saved default that is no longer installed must not read as active: the list
        # would mark whatever it falls back to while the status names a CLI that
        # cannot run. Keep the stale name only to explain the warning.
        self.stale_current = current if current and current not in self.installed else None
        self.current = current if current in self.installed else None
        self.suggestion = suggested_cli(self.installed, self.current)

    def compose(self) -> ComposeResult:
        if not self.installed:
            yield WarningText(
                f"{Icons.WARNING} No supported CLI is installed. "
                "Tasks set to use a CLI will say so when they run."
            )
            return

        yield Static("Which CLI should Titan run?")
        yield DimText(
            "One choice for both uses below - it is the same tool, invoked differently. "
            "Press Enter to set it, or M to choose which model it runs."
        )
        yield StyledOptionList(*self._styled_options(), id="cli-default-list")
        yield Static(self._status_text(), id="cli-status")

        yield DimText(
            f"  · {provider_type_label(AIProviderType.CLI_HEADLESS)} — "
            f"{provider_description(AIProviderType.CLI_HEADLESS)}",
            classes="cli-note",
        )
        yield DimText(
            f"  · {provider_type_label(AIProviderType.CLI_INTERACTIVE)} — "
            f"{provider_description(AIProviderType.CLI_INTERACTIVE)}"
        )

    def _styled_options(self) -> List[StyledOption]:
        from titan_cli.external_cli.configs import CLI_REGISTRY

        options = []
        for name in self.installed:
            display_name = CLI_REGISTRY.get(name, {}).get("display_name", name)
            marker = f" {Icons.CHECK}" if name == self.current else ""
            options.append(
                StyledOption(
                    id=name,
                    title=f"{display_name}{marker}",
                    description=cli_option_description(name, self.models.get(name)),
                )
            )
        return options

    def on_mount(self) -> None:
        """Start the highlight on the saved default (or the lone suggestion).

        Deferred a refresh: when the container mounts, the children it composed are
        not queryable yet.
        """
        start = self.current or self.suggestion
        if start is None:
            return
        index = self.installed.index(start)
        self.call_after_refresh(self._highlight, index)

    def _highlight(self, index: int) -> None:
        # The screen repaints its sections by replacing this widget wholesale, so the
        # deferred callback can fire on a picker that was already removed - with no
        # children left to highlight.
        try:
            option_list = self.query_one(StyledOptionList)
        except NoMatches:
            return
        option_list.highlighted = index

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Translate the inner list's selection into this control's own event."""
        if getattr(event.option_list, "id", None) != "cli-default-list":
            return
        event.stop()
        if event.option.id is not None:
            self.post_message(self.Changed(self, event.option.id))

    def action_pick_model(self) -> None:
        """Ask for a model for the highlighted CLI, whether or not it is the default.

        Highlight, not default: pinning a model on a CLI you have not switched to is a
        normal thing to do, and making the highlight the default as a side effect would
        change what runs your next workflow.
        """
        try:
            option_list = self.query_one(StyledOptionList)
        except NoMatches:
            return
        index = option_list.highlighted
        if index is None or not (0 <= index < len(self.installed)):
            return
        self.post_message(self.ModelRequested(self, self.installed[index]))

    def set_model(self, cli_name: str, model: Optional[str]) -> None:
        """Repaint one row's model in place after it was changed."""
        self.models[cli_name] = model or ""
        if not model:
            self.models.pop(cli_name, None)
        self._repaint_options()

    def _status_text(self) -> str:
        if self.stale_current:
            return (
                f"{Icons.WARNING} The default {self.stale_current} is no longer "
                "installed - pick one below."
            )
        if self.current:
            return f"{Icons.CHECK} Titan will run {self.current}."
        if self.suggestion:
            return (
                f"{Icons.WARNING} No default set yet. {self.suggestion} is the only one "
                "installed - select it to use it."
            )
        return (
            f"{Icons.WARNING} No default set yet. Tasks set to use a CLI cannot run until "
            "you pick one."
        )

    def set_current(self, cli_name: str) -> None:
        """Update the status line and the check marker in place after a selection.

        Guarded like `_highlight` and `_repaint_options`, and for the same two reasons:
        this runs from a posted-message handler, so the screen may have replaced the
        picker by the time it lands, and `#cli-status` does not exist at all when no CLI
        is installed.
        """
        self.current = cli_name
        self.stale_current = None
        self.suggestion = None
        try:
            self.query_one("#cli-status", Static).update(self._status_text())
        except NoMatches:
            return
        self._repaint_options()

    def _repaint_options(self) -> None:
        """Swap each option's prompt without remounting the list.

        The list is what the user is currently operating: rebuilding it under them would
        drop focus mid-keystroke, so only the rendered prompts change and highlight and
        focus survive.
        """
        try:
            option_list = self.query_one(StyledOptionList)
        except NoMatches:
            return
        for index, option in enumerate(self._styled_options()):
            prompt = f"[bold]{option.title}[/bold]\n[dim]{option.description}[/dim]"
            option_list.replace_option_prompt_at_index(index, prompt)


__all__ = [
    "TaskRouting",
    "TaskRoutingRow",
    "CliDefaultPicker",
    "QuickInstanceModal",
    "QuickPickResult",
    "InstanceChoice",
    "cli_choices",
    "connection_choices",
    "TASK_CLI_INHERIT_OPTION",
    "tasks_pinning",
    "cli_option_description",
    "SelectProviderTypeModal",
    "build_task_routings",
    "executable_types",
    "installed_clis",
    "suggested_cli",
    "task_label",
    "provider_type_label",
    "widget_key",
]
