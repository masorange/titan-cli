"""
Mod Home Card Widget

A mod's own card on the home screen, beside the quick-launch workflows
(`m.ui.home_card`): its icon, title and text, launched by
Enter or a click like a `WorkflowCard`, but with no number key - home cards
are not quick-launch slots, so they don't compete for them.
"""

from textual.binding import Binding
from textual.widgets import Static

from .collapsible_list import escape_markup


class ModHomeCard(Static):
    """A focusable card that runs one mod's `on_click`, if it gave one."""

    can_focus = True

    BINDINGS = [
        Binding("enter", "launch", "Open", show=False),
    ]

    DEFAULT_CSS = """
    ModHomeCard {
        width: 1fr;
        height: 9;
        border: round $accent 60%;
        border-title-align: left;
        padding: 1 2;
        background: $surface-lighten-1;
    }

    ModHomeCard:focus {
        border: round $accent;
        background: $accent 15%;
    }

    ModHomeCard:hover {
        border: round $accent;
    }

    ModHomeCard.-inert:hover {
        border: round $accent 60%;
        background: $surface-lighten-1;
    }
    """

    def __init__(self, mod: str, icon: str, title: str, text: str, clickable: bool, **kwargs):
        self.mod = mod
        body = f"[bold]{escape_markup(f'{icon} {title}'.strip())}[/bold]"
        if text:
            body = f"{body}\n\n{escape_markup(text)}"
        super().__init__(body, **kwargs)
        # Focusable either way (Tab reaches it like any other card); a mod with no
        # on_click just answers a press with nothing - press_home_card() already
        # no-ops there. The -inert class only mutes the hover/focus styling so it
        # doesn't invite a press that does nothing.
        self.set_class(not clickable, "-inert")

    def action_launch(self) -> None:
        self.app.mods_host.press_home_card(self.mod)

    def on_click(self) -> None:
        self.focus()
        self.action_launch()
