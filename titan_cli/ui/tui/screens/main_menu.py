"""
Main Menu Screen

The home screen: a quick-launch grid of workflows, plus the keys that reach everything else.

It used to be a three-row menu, which rendered three options as peers when they are not:
Workflows is why you opened Titan, while Plugin Management and AI Configuration are monthly
setup - and the daily half of AI configuration already lives on F2/F3 with its own status-bar
cells. So the body belongs to the workflows and those two demote to keys.
"""

import asyncio
from typing import Dict, List

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Grid, VerticalScroll
from textual.css.query import NoMatches
from textual.widgets import Static

from titan_cli import __version__
from titan_cli.core.workflows import (
    DEFAULT_SLOT_COUNT,
    QuickLaunchService,
    QuickLaunchSlot,
)
from titan_cli.core.workflows.workflow_filter_service import WorkflowFilterService
from titan_cli.ui.tui.icons import Icons
from titan_cli.ui.tui.widgets import Button, StatusBarWidget, WorkflowCard
from titan_cli.core.plugins.community_sources import (
    CommunityPluginRecord,
    PluginChannel,
    get_github_token,
    check_for_updates,
)
from .base import BaseScreen
from .card_grid import CardGridNavigationMixin

from .ai_config import AIConfigScreen
from .plugin_management import PluginManagementScreen

# Width a card needs before another one fits beside it. The column count is derived from
# this on resize; the SET of cards never is - a grid whose contents changed with the window
# would remap the number keys under the user's fingers.
CARD_TARGET_WIDTH = 38
MAX_COLUMNS = 4
# Horizontal space #home-body's padding takes out of the screen width.
HOME_BODY_GUTTER = 8
# Same idea for the action row: a button whose label is squeezed below this reads as
# truncation, so the row stacks instead of shrinking. Its labels are shorter than a
# card's body, hence the smaller target.
ACTION_TARGET_WIDTH = 24
# The grid's heading. Deliberately says nothing about where the cards came from: a
# heading cannot be true of a mixed grid, and the per-card star already is.
SECTION_TITLE = f"{Icons.WORKFLOW} Quick launch"


class MainMenuScreen(CardGridNavigationMixin, BaseScreen):
    """
    Home screen.

    Body: up to nine workflow cards, launchable by their number key. Favorites come first
    and carry a star; the rest of the slots are filled so the grid is never ragged.

    Footer row: the three things the old menu held, as keys - `w` workflows, `p` plugins,
    `a` AI.
    """

    def __init__(self, config, **kwargs):
        """Initialize main menu with version in title."""
        super().__init__(
            config,
            title=f"Titan CLI v{__version__}",
            show_back=False,
            **kwargs
        )
        self._slots: List[QuickLaunchSlot] = []
        # Discovery is cached so a screen resume does not rescan every workflow YAML;
        # config.load() builds a fresh WorkflowRegistry on every transition, so the
        # registry's own cache cannot be relied on here.
        self._workflows = None
        # What the grid currently on screen was built FROM. A resume compares against
        # these rather than rebuilding: on_screen_resume fires on every transition, and
        # re-running discover() there is precisely the startup cost O-001 was about.
        self._favorite_names: List[str] = []
        self._last_used: Dict[str, str] = {}
        # Set when something that can change the workflow SET (not just its order) has
        # happened, so the cached discovery is dropped instead of trusted.
        self._discovery_dirty = False

    CARD_GRID_ID = "home-grid"

    # Textual's default AUTO_FOCUS of "*" focuses the first focusable widget when the screen
    # becomes active, which happens AFTER on_mount - so it silently overrode
    # `_focus_first_card()` and left the focus on the scrollable body. The cards were never
    # focused on arrival, which meant Enter did nothing until the user pressed Tab, and the
    # arrows scrolled the container instead of moving between cards. None hands the choice
    # back to `_focus_first_card()`.
    AUTO_FOCUS = None

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("escape", "quit", "Quit"),
        Binding("w", "open_workflows", "Workflows"),
        Binding("p", "open_plugins", "Plugins"),
        Binding("a", "open_ai_config", "AI"),
    ] + [
        Binding(str(number), f"launch_slot({number})", show=False)
        for number in range(1, DEFAULT_SLOT_COUNT + 1)
    ]

    CSS = """
    #home-body {
        height: 1fr;
        padding: 1 3 0 3;
    }

    #home-section-title {
        text-style: bold;
        color: $primary;
        margin: 0 0 1 1;
    }

    #home-grid {
        grid-size: 3;
        grid-rows: 9;
        /* Row and column gutter, so the cards breathe instead of sharing borders. */
        grid-gutter: 1 2;
        height: auto;
    }

    #home-hint {
        color: $text-muted;
        margin-top: 1;
    }

    /* A Grid, not a Horizontal, for the same reason the cards are one: on a narrow
       terminal three buttons side by side shrink until their labels truncate. The column
       count is recomputed on resize and drops to 1, stacking them the way the cards
       stack. */
    #home-actions {
        height: auto;
        padding: 1 3 1 3;
        grid-size: 3;
        grid-rows: 3;
        grid-gutter: 1 2;
    }

    /* Real buttons rather than chips. A Chip is content-width by design - it exists to
       annotate a step's output - so three of them read as a caption strip under the grid
       instead of as the way out of this screen. These span the row and match the cards'
       weight. */
    #home-actions Button {
        width: 1fr;
        margin: 0;
    }

    #home-empty {
        height: 1fr;
        align: center middle;
    }

    #home-empty-message {
        width: auto;
        text-align: center;
    }
    """

    def compose_content(self) -> ComposeResult:
        """Compose the home screen.

        Workflows are read synchronously: measured at 30-67 ms against a 1.1-1.6 s startup
        across three projects, which is not worth a worker and the complexity it brings.
        """
        self._slots = self._build_slots()

        if not self._workflows:
            # Nothing to launch at all - the only honest thing to offer is the screen that
            # fixes it. A grid with no cards would read as a failed load.
            with Container(id="home-empty"):
                yield Static(
                    f"{Icons.PLUGIN}  No plugins are enabled for this project\n\n"
                    "[dim]Enable Git, GitHub or Jira to start running workflows.[/dim]",
                    id="home-empty-message",
                )
            with Grid(id="home-actions"):
                yield self._action_button(
                    Icons.PLUGIN, "p", "Manage plugins", variant="primary"
                )
                yield self._action_button(Icons.AI_CONFIG, "a", "AI")
            return

        has_favorites = any(slot.is_favorite for slot in self._slots)
        with VerticalScroll(id="home-body"):
            # One neutral title, never a claim about where the cards came from. Titling
            # the grid '⭐ Favorites' whenever ANY card was starred was the opposite of
            # honest in the normal case: one favorite and eight fillers all sat under a
            # heading that said the user had chosen them. The per-card star already
            # carries that distinction, card by card, and it is the only place it is
            # true.
            yield Static(SECTION_TITLE, id="home-section-title")
            with Grid(id="home-grid"):
                for slot in self._slots:
                    yield self._card_for(slot)
            # Mounted in both states and hidden when it does not apply: a refresh
            # after a star toggle then only flips `display`, instead of mounting and
            # unmounting a widget in the middle of a rebuild.
            hint = Static(
                f"[dim]{Icons.STAR} Press [/dim]f[dim] while running a workflow to "
                f"star it, and it will take a slot here.[/dim]",
                id="home-hint",
            )
            hint.display = not has_favorites
            yield hint

        with Grid(id="home-actions"):
            # Workflows is the primary: it is the one a user reaches for, and the other
            # two are monthly setup.
            yield self._action_button(
                Icons.WORKFLOW, "w", "All workflows", variant="primary"
            )
            yield self._action_button(Icons.PLUGIN, "p", "Plugins")
            yield self._action_button(Icons.AI_CONFIG, "a", "AI")

    def _action_button(self, icon: str, key: str, label: str, variant: str = "default") -> Button:
        """One action, sized and weighted to be seen, with its key shown on it.

        `w` as plain text beside the label read as the first word of "w All workflows",
        so the key is bracketed - it is a shortcut, not part of the name.
        """
        # The bracket is escaped: a Button label is markup, so a bare `[w]` is parsed as
        # a tag and silently disappears - the same hazard the card descriptions have.
        button = Button(
            f"{icon}  {label}  \\[{key}]",
            variant=variant,
            id=f"home-action-{key}",
        )
        button.tooltip = f"Press {key}"
        return button

    def _build_slots(self) -> List[QuickLaunchSlot]:
        """Read what the grid needs and choose the slots."""
        if self._workflows is None:
            self._workflows = self.config.workflows.discover()
        self._favorite_names = self.config.get_favorite_workflows()
        self._last_used = self.config.get_workflow_last_used()
        return QuickLaunchService.build_slots(
            self._workflows,
            self._favorite_names,
            self._last_used,
        )

    def _card_for(self, slot: QuickLaunchSlot) -> WorkflowCard:
        """Build the card for one slot."""
        workflow = slot.workflow
        return WorkflowCard(
            workflow_name=workflow.name,
            title=workflow.title or workflow.name.replace("-", " ").capitalize(),
            group=WorkflowFilterService.detect_plugin_name(workflow),
            description=workflow.description or "",
            key=slot.key,
            is_favorite=slot.is_favorite,
        )

    def on_mount(self) -> None:
        for message in self.config.get_plugin_sync_events():
            self.app.notify(message, severity="information", timeout=6)
        self._reflow_grid()
        self._reflow_actions()
        self._focus_first_card()
        self.run_worker(self._check_plugin_updates(), exclusive=False)

    def on_resize(self) -> None:
        """Reflow the columns. The set of cards is deliberately untouched (D-003)."""
        self._reflow_grid()
        self._reflow_actions()

    def _column_count(self, width: int) -> int:
        """How many card columns fit in `width`."""
        return max(1, min(MAX_COLUMNS, (width - HOME_BODY_GUTTER) // CARD_TARGET_WIDTH))

    def _reflow_grid(self) -> None:
        """Fit as many columns as the width allows, without changing what is shown.

        Assigning the column count unconditionally would relayout, which emits another
        Resize, which lands back here - so the write is guarded on the value changing.
        """
        try:
            grid = self.query_one("#home-grid", Grid)
        except NoMatches:
            return
        # Measured against the SCREEN, not the grid's container. The container's width
        # depends on whether the scrollbar is showing, which depends on the grid's height,
        # which depends on the column count computed here - a loop that never settles and
        # surfaces as "widgets did not finish processing pending messages".
        columns = self._column_count(self.size.width)
        if grid.styles.grid_size_columns != columns:
            grid.styles.grid_size_columns = columns

    async def on_screen_resume(self) -> None:
        """Bring the grid up to date, but only when something it depends on changed.

        This fires on EVERY screen transition and the base class already reloads the
        config here, so the naive version - rebuilding unconditionally - would re-run
        discover() each time the user backs out of any screen. Favorites and last_used
        are two cheap reads of the file the base class has just reloaded; discovery is
        not, so it is reused unless it is known to be stale.
        """
        super().on_screen_resume()

        if self._discovery_dirty:
            # The set of workflows itself may have changed (a plugin was enabled or
            # disabled), which can also flip the body between its three states - so the
            # body is composed again rather than refilled.
            self._discovery_dirty = False
            self._workflows = None
            self.refresh(recompose=True)
            return

        if (
            self.config.get_favorite_workflows() == self._favorite_names
            and self.config.get_workflow_last_used() == self._last_used
        ):
            return

        await self._refresh_grid()

    async def _refresh_grid(self) -> None:
        """Refill the grid from the cached discovery, keeping the body's state honest.

        Awaited rather than fire-and-forget: removing and mounting in the same tick
        without waiting leaves the old cards in the tree while the new ones arrive.
        """
        try:
            grid = self.query_one("#home-grid", Grid)
            hint = self.query_one("#home-hint", Static)
        except NoMatches:
            # The onboarding body has no grid; it only changes when discovery does,
            # which is the _discovery_dirty path above.
            return

        self._slots = self._build_slots()
        has_favorites = any(slot.is_favorite for slot in self._slots)
        # The title is constant; only the hint reacts, and only to having no favorites
        # at all - which is the one thing a neutral heading can no longer say.
        hint.display = not has_favorites

        await grid.remove_children()
        await grid.mount_all([self._card_for(slot) for slot in self._slots])
        self._reflow_grid()
        self._focus_first_card()

    def _reflow_actions(self) -> None:
        """Wrap the action row the same way the cards wrap, down to one per line.

        Guarded on the value changing for the same reason `_reflow_grid` is: an
        unconditional style write relayouts, which emits another Resize, which lands
        back here.
        """
        try:
            actions = self.query_one("#home-actions", Grid)
        except NoMatches:
            return
        buttons = len(actions.query(Button))
        if not buttons:
            return
        available = self.size.width - HOME_BODY_GUTTER
        columns = max(1, min(buttons, available // ACTION_TARGET_WIDTH))
        if actions.styles.grid_size_columns != columns:
            actions.styles.grid_size_columns = columns

    def _focus_first_card(self) -> None:
        """Put the cursor on the first card, so Enter means something immediately."""
        cards = list(self.query(WorkflowCard))
        if cards:
            cards[0].focus()

    async def _check_plugin_updates(self) -> None:
        records = self._get_project_stable_records()
        if not records:
            return
        token = await asyncio.to_thread(get_github_token)
        updates = await asyncio.to_thread(check_for_updates, records, token)
        for record, latest in updates:
            self.app.notify(
                f"Update available for '{record.titan_plugin_name}': "
                f"{record.requested_ref} → {latest}\n"
                "Go to Plugin Management to update.",
                severity="warning",
                timeout=12,
            )

    def _get_project_stable_records(self) -> list[CommunityPluginRecord]:
        """Return synthetic records for project-pinned community plugins."""
        records: list[CommunityPluginRecord] = []
        for plugin_name in self.config.get_enabled_plugins():
            repo_url = self.config.get_project_plugin_repo_url(plugin_name)
            resolved_commit = self.config.get_project_plugin_resolved_commit(plugin_name)
            if not repo_url or not resolved_commit:
                continue
            records.append(
                CommunityPluginRecord(
                    repo_url=repo_url,
                    package_name=plugin_name,
                    titan_plugin_name=plugin_name,
                    installed_at="",
                    channel=PluginChannel.STABLE,
                    dev_local_path=None,
                    requested_ref=self.config.get_project_plugin_requested_ref(plugin_name) or resolved_commit,
                    resolved_commit=resolved_commit,
                )
            )
        return records

    def on_workflow_card_selected(self, message: WorkflowCard.Selected) -> None:
        """A card was chosen - run its workflow."""
        self.execute_workflow(message.workflow_name)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """An action button was pressed or clicked."""
        actions = {
            "home-action-w": self.action_open_workflows,
            "home-action-p": self.action_open_plugins,
            "home-action-a": self.action_open_ai_config,
        }
        action = actions.get(event.button.id)
        if action is not None:
            action()

    def action_launch_slot(self, number: int) -> None:
        """Launch the workflow on the given number key."""
        for slot in self._slots:
            if slot.key == number:
                self.execute_workflow(slot.workflow.name)
                return

    def execute_workflow(self, workflow_name: str) -> None:
        """Open the execution screen for a workflow."""
        from .workflow_execution import WorkflowExecutionScreen

        self.app.push_screen(WorkflowExecutionScreen(self.config, workflow_name))

    def action_open_workflows(self) -> None:
        """Open the full workflow list."""
        from .workflows import WorkflowsScreen

        self.app.push_screen(WorkflowsScreen(self.config))

    def action_open_plugins(self) -> None:
        """Open plugin management.

        Enabling or disabling a plugin changes which workflows exist, so the cached
        discovery this screen holds is marked stale for the resume that follows.
        """
        self._discovery_dirty = True
        self.app.push_screen(PluginManagementScreen(self.config))

    def action_open_ai_config(self) -> None:
        """Open AI configuration."""
        def on_ai_config_closed(result) -> None:
            """Refresh the status bar with whatever the screen changed."""
            try:
                self.config.load()
                status_bar = self.query_one("#status-bar", StatusBarWidget)
                self._update_status_bar(status_bar)
            except Exception as e:
                self.app.notify(f"Error refreshing status bar: {e}", severity="error")

        self.app.push_screen(AIConfigScreen(self.config), callback=on_ai_config_closed)

    def action_quit(self) -> None:
        """Quit the application."""
        self.app.exit()
