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
from typing import Dict, List, Mapping, Optional, Sequence

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.css.query import NoMatches
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import OptionList, Static

from titan_cli.ai.router.availability import AIProviderAvailability
from titan_cli.ai.router.enums import (
    AIProviderType,
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


@dataclass(frozen=True)
class QuickCliResult:
    """What the quick picker was asked to do with a CLI.

    Several outcomes, not one: the same row answers "run this from now on", "run it with
    this model", and "run it just for this session". Collapsing them into a bare name
    would leave the caller guessing which was meant - and the difference between the
    first and the third is whether anything is written to the user's config at all.
    """

    cli_name: str
    pick_model: bool = False
    session_only: bool = False
    clear_session: bool = False


class QuickCliModal(ModalScreen[Optional["QuickCliResult"]]):
    """
    Quick picker for the global default CLI, reachable from any screen via a keybinding.

    The same single choice the AI Configuration screen's CLI section offers, without the
    navigation: Enter runs that CLI from now on, `m` opens its model picker instead, and
    Escape leaves everything untouched. Dismisses with a `QuickCliResult`, or `None` if
    cancelled.
    """

    DEFAULT_CSS = """
    QuickCliModal {
        align: center middle;
    }

    #quick-cli-container {
        width: 74;
        height: auto;
        max-height: 26;
        background: $surface-lighten-1;
        border: solid $primary;
        padding: 2;
    }

    #quick-cli-list {
        height: auto;
        max-height: 16;
        margin-top: 1;
    }
    """

    BINDINGS = [
        ("escape", "dismiss_modal", "Cancel"),
        ("m", "pick_model", "Model"),
        ("s", "use_for_session", "This session"),
        ("c", "clear_session", "Clear override"),
    ]

    def __init__(
        self,
        installed: Sequence[str],
        *,
        current: Optional[str],
        models: Optional[Dict[str, str]] = None,
        session_override=None,
        pinned_tasks: Optional[Sequence[str]] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.installed = list(installed)
        self.current = current if current in self.installed else None
        self.models = dict(models or {})
        self.session_override = session_override
        self.pinned_tasks = list(pinned_tasks or ())

    def compose(self) -> ComposeResult:
        from titan_cli.external_cli.configs import CLI_REGISTRY

        with Container(id="quick-cli-container"):
            yield Static(f"{Icons.AI_CONFIG} Which CLI should Titan run?")
            if not self.installed:
                yield WarningText(
                    f"{Icons.WARNING} No supported CLI is installed. "
                    "Install one and reopen this picker."
                )
                yield DimText("Esc to close.")
                return
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
            yield StyledOptionList(*options, id="quick-cli-list")

            override = self.session_override
            if override is not None and override.is_active:
                yield WarningText(
                    f"{Icons.WARNING} Session override active: {override.describe()}. "
                    "C to clear it."
                )

            # Tasks that pin their own CLI will not follow this choice. Saying so here is
            # what stops the key from looking broken: without it, a pinned task silently
            # ignoring F2 reads as a bug rather than as the setting the user asked for.
            if self.pinned_tasks:
                count = len(self.pinned_tasks)
                names = ", ".join(self.pinned_tasks[:3])
                more = f" and {count - 3} more" if count > 3 else ""
                yield DimText(
                    f"{count} task{'s' if count != 1 else ''} pin their own CLI and will "
                    f"not change: {names}{more}."
                )

            yield DimText(
                "Enter to set it · S for this session only · M to choose its model · "
                "Esc to cancel."
            )

    def on_mount(self) -> None:
        if self.current is None or not self.installed:
            return
        index = self.installed.index(self.current)
        self.call_after_refresh(self._highlight, index)

    def _highlight(self, index: int) -> None:
        try:
            option_list = self.query_one(StyledOptionList)
        except NoMatches:
            return
        option_list.highlighted = index

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_list.id != "quick-cli-list":
            return
        if event.option.id is not None:
            self.dismiss(QuickCliResult(event.option.id))

    def action_pick_model(self) -> None:
        """Hand the highlighted CLI back for a model choice, without making it default.

        Choosing a model is not choosing the CLI: pinning a model on one you are not
        switching to is a normal thing to do, and silently making it default as a side
        effect would change what runs your next workflow.
        """
        highlighted = self._highlighted_cli()
        if highlighted is not None:
            self.dismiss(QuickCliResult(highlighted, pick_model=True))

    def action_use_for_session(self) -> None:
        """Use the highlighted CLI for this session only, writing nothing to config.

        The saved default is what the user decided; this is what they are trying. Keeping
        them apart is the whole point - otherwise every experiment silently rewrites the
        configuration it was meant to sidestep.
        """
        highlighted = self._highlighted_cli()
        if highlighted is not None:
            self.dismiss(QuickCliResult(highlighted, session_only=True))

    def action_clear_session(self) -> None:
        """Drop any session override, so saved configuration applies again."""
        override = self.session_override
        if override is None or not override.is_active:
            return
        self.dismiss(QuickCliResult("", clear_session=True))

    def _highlighted_cli(self) -> Optional[str]:
        try:
            option_list = self.query_one(StyledOptionList)
        except NoMatches:
            return None
        index = option_list.highlighted
        if index is None or not (0 <= index < len(self.installed)):
            return None
        return self.installed[index]

    def action_dismiss_modal(self) -> None:
        self.dismiss(None)


# Sentinel option id meaning "stop pinning; follow whatever the global default is".
# A pin is an override, so removing one has to be expressible in the same picker that
# sets it - otherwise the only way back is the row's Clear, which also drops the
# provider kind the user chose.
TASK_CLI_INHERIT_OPTION = "__inherit__"


@dataclass(frozen=True)
class InstanceChoice:
    """One selectable instance - a CLI or a remote connection - and how it reads."""

    identifier: str
    title: str
    description: str = ""


class SelectTaskInstanceModal(ModalScreen[Optional[str]]):
    """
    Modal for choosing which INSTANCE serves ONE task, overriding the global default.

    Instance, not kind: a CLI for a CLI-routed task, a connection for a remote one. The
    two are the same question asked of different transports (D-006), so they share one
    modal rather than two that would drift. Dismisses with an identifier, with
    `TASK_CLI_INHERIT_OPTION` to drop the pin, or `None` if cancelled.
    """

    DEFAULT_CSS = """
    SelectTaskInstanceModal {
        align: center middle;
    }

    #task-cli-container {
        width: 74;
        height: auto;
        max-height: 26;
        background: $surface-lighten-1;
        border: solid $primary;
        padding: 2;
    }

    #task-cli-list {
        height: auto;
        max-height: 16;
        margin-top: 1;
    }
    """

    BINDINGS = [("escape", "dismiss_modal", "Cancel")]

    def __init__(
        self,
        task_label_text: str,
        choices: Sequence[InstanceChoice],
        *,
        noun: str = "CLI",
        pinned: Optional[str] = None,
        default_instance: Optional[str] = None,
        empty_message: Optional[str] = None,
        **kwargs,
    ):
        """
        Args:
            task_label_text: The task being configured, for the heading.
            choices: The instances that can serve it, already rendered for display.
            noun: What an instance is called here - "CLI" or "connection". Only wording.
            pinned: The instance currently pinned, marked in the list.
            default_instance: The global default, named in the inherit option so the user
                can see what "follow the default" means today.
            empty_message: Shown instead of the list when nothing is available.
        """
        super().__init__(**kwargs)
        self.task_label_text = task_label_text
        self.choices = list(choices)
        self.noun = noun
        self.pinned = pinned
        self.default_instance = default_instance
        self.empty_message = empty_message

    def compose(self) -> ComposeResult:
        with Container(id="task-cli-container"):
            yield Static(
                f"{Icons.AI_CONFIG} Which {self.noun} should run {self.task_label_text}?"
            )
            if not self.choices:
                yield WarningText(
                    f"{Icons.WARNING} "
                    + (
                        self.empty_message
                        or f"No {self.noun} is available. Configure one and reopen this picker."
                    )
                )
                yield DimText("Esc to close.")
                return

            options = [
                StyledOption(
                    id=TASK_CLI_INHERIT_OPTION,
                    title=(
                        "Follow the default"
                        + (f" ({self.default_instance})" if self.default_instance else "")
                        + ("" if self.pinned else f" {Icons.CHECK}")
                    ),
                    description=(
                        f"No pin: this task moves with the {self.noun} you set for Titan, "
                        "including from the quick picker."
                    ),
                )
            ]
            for choice in self.choices:
                marker = f" {Icons.CHECK}" if choice.identifier == self.pinned else ""
                options.append(
                    StyledOption(
                        id=choice.identifier,
                        title=f"{choice.title}{marker}",
                        description=choice.description,
                    )
                )
            yield StyledOptionList(*options, id="task-cli-list")
            yield DimText("Enter to pin it for this task only · Esc to cancel.")

    @staticmethod
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
            )
            for name in installed
        ]

    @staticmethod
    def connection_choices(connections: Mapping[str, object]) -> List[InstanceChoice]:
        """Configured remote connections, described by what answers and with which model."""
        return [
            InstanceChoice(
                identifier=connection_id,
                title=getattr(cfg, "name", connection_id),
                description=(
                    f"model: {getattr(cfg, 'default_model', None) or 'connection default'}"
                ),
            )
            for connection_id, cfg in connections.items()
        ]

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_list.id != "task-cli-list":
            return
        if event.option.id is not None:
            self.dismiss(event.option.id)

    def action_dismiss_modal(self) -> None:
        self.dismiss(None)


@dataclass(frozen=True)
class QuickConnectionResult:
    """What the F3 picker was asked to do with a connection. Mirrors `QuickCliResult`."""

    connection_id: str
    pick_model: bool = False
    session_only: bool = False
    clear_session: bool = False


class QuickConnectionModal(ModalScreen[Optional["QuickConnectionResult"]]):
    """
    Quick picker for the remote connection, reachable from any screen via a keybinding.

    F3's counterpart to F2's `QuickCliModal`, and deliberately the same shape: Enter makes
    it the default, S uses it for this session only, M opens its model list, C drops the
    session override, Escape changes nothing. The two keys answer the same question of
    different transports (D-006), so they should not need to be learned twice.
    """

    DEFAULT_CSS = """
    QuickConnectionModal {
        align: center middle;
    }

    #quick-connection-container {
        width: 74;
        height: auto;
        max-height: 26;
        background: $surface-lighten-1;
        border: solid $primary;
        padding: 2;
    }

    #quick-connection-list {
        height: auto;
        max-height: 16;
        margin-top: 1;
    }
    """

    BINDINGS = [
        ("escape", "dismiss_modal", "Cancel"),
        ("m", "pick_model", "Model"),
        ("s", "use_for_session", "This session"),
        ("c", "clear_session", "Clear override"),
    ]

    def __init__(
        self,
        connections: Mapping[str, object],
        *,
        current: Optional[str],
        session_override=None,
        pinned_tasks: Optional[Sequence[str]] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.connections = dict(connections)
        self.ids = list(self.connections)
        self.current = current if current in self.connections else None
        self.session_override = session_override
        self.pinned_tasks = list(pinned_tasks or ())

    def compose(self) -> ComposeResult:
        with Container(id="quick-connection-container"):
            yield Static(f"{Icons.AI_CONFIG} Which connection should answer?")
            if not self.ids:
                yield WarningText(
                    f"{Icons.WARNING} No AI connection is configured. "
                    "Add one in AI Configuration."
                )
                yield DimText("Esc to close.")
                return

            options = []
            for connection_id in self.ids:
                cfg = self.connections[connection_id]
                marker = f" {Icons.CHECK}" if connection_id == self.current else ""
                options.append(
                    StyledOption(
                        id=connection_id,
                        title=f"{getattr(cfg, 'name', connection_id)}{marker}",
                        description=(
                            f"model: {getattr(cfg, 'default_model', None) or 'connection default'}"
                        ),
                    )
                )
            yield StyledOptionList(*options, id="quick-connection-list")

            override = self.session_override
            if override is not None and override.is_active:
                yield WarningText(
                    f"{Icons.WARNING} Session override active: {override.describe()}. "
                    "C to clear it."
                )

            if self.pinned_tasks:
                count = len(self.pinned_tasks)
                names = ", ".join(self.pinned_tasks[:3])
                more = f" and {count - 3} more" if count > 3 else ""
                yield DimText(
                    f"{count} task{'s' if count != 1 else ''} pin their own connection and "
                    f"will not change: {names}{more}."
                )

            yield DimText(
                "Enter to set it · S for this session only · M to choose its model · "
                "Esc to cancel."
            )

    def on_mount(self) -> None:
        if self.current is None or not self.ids:
            return
        self.call_after_refresh(self._highlight, self.ids.index(self.current))

    def _highlight(self, index: int) -> None:
        try:
            self.query_one(StyledOptionList).highlighted = index
        except NoMatches:
            return

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_list.id != "quick-connection-list":
            return
        if event.option.id is not None:
            self.dismiss(QuickConnectionResult(event.option.id))

    def action_pick_model(self) -> None:
        highlighted = self._highlighted_connection()
        if highlighted is not None:
            self.dismiss(QuickConnectionResult(highlighted, pick_model=True))

    def action_use_for_session(self) -> None:
        highlighted = self._highlighted_connection()
        if highlighted is not None:
            self.dismiss(QuickConnectionResult(highlighted, session_only=True))

    def action_clear_session(self) -> None:
        override = self.session_override
        if override is None or not override.is_active:
            return
        self.dismiss(QuickConnectionResult("", clear_session=True))

    def _highlighted_connection(self) -> Optional[str]:
        try:
            option_list = self.query_one(StyledOptionList)
        except NoMatches:
            return None
        index = option_list.highlighted
        if index is None or not (0 <= index < len(self.ids)):
            return None
        return self.ids[index]

    def action_dismiss_modal(self) -> None:
        self.dismiss(None)


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
        pinned_instance = self.routing.pinned_instance
        yield DimText(
            f"  {noun}: {instance} ({'pinned here' if pinned_instance else 'default'})"
        )
        if resolution.model:
            origin = (
                "pinned here"
                if self.routing.pinned_model
                else f"default for this {noun.lower()}"
            )
            yield DimText(f"  Model: {resolution.model} ({origin})")
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
        """Update the status line and the check marker in place after a selection."""
        self.current = cli_name
        self.stale_current = None
        self.suggestion = None
        self.query_one("#cli-status", Static).update(self._status_text())
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
    "QuickCliModal",
    "QuickCliResult",
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
