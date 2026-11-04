"""
Mod Home Card Widget

A mod's own card on the home screen, beside the quick-launch workflows
(`m.ui.home_card`): its icon, title and text, launched by
Enter or a click like a `WorkflowCard`, but with no number key - home cards
are not quick-launch slots, so they don't compete for them. A mod may also give it
buttons (`actions`), each pressable on its own.
"""

from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Static

from .button import Button
from .collapsible_list import escape_markup


class ModHomeCard(Vertical):
    """A focusable card that runs one mod's `on_click`, if it gave one, and holds its buttons."""

    can_focus = True

    BINDINGS = [
        Binding("enter", "launch", "Open", show=False),
    ]

    DEFAULT_CSS = """
    ModHomeCard {
        width: 1fr;
        height: auto;
        min-height: 9;
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

    ModHomeCard .mod-card-body {
        height: auto;
    }

    /* Same specificity as Button.-compact's own margin, which would win by order. */
    ModHomeCard Button.mod-card-action {
        margin: 1 0 0 0;
    }
    """

    def __init__(self, mod: str, icon: str, title: str, text: str, clickable: bool, actions=(), **kwargs):
        self.mod = mod
        self._actions = tuple(actions)
        body = f"[bold]{escape_markup(f'{icon} {title}'.strip())}[/bold]"
        if text:
            body = f"{body}\n\n{escape_markup(text)}"
        self._body = body
        super().__init__(**kwargs)
        # Focusable either way (Tab reaches it like any other card); a mod with no
        # on_click just answers a press with nothing - press_home_card() already
        # no-ops there. The -inert class only mutes the hover/focus styling so it
        # doesn't invite a press that does nothing.
        self.set_class(not clickable, "-inert")

    def compose(self):
        yield Static(self._body, classes="mod-card-body")
        for index, action in enumerate(self._actions):
            yield Button(
                action.label,
                action.variant,
                size="compact",
                on_press=lambda i=index: self.app.mods_host.press_home_action(self.mod, i),
                classes="mod-card-action",
            )

    def action_launch(self) -> None:
        self.app.mods_host.press_home_card(self.mod)

    def on_click(self, event) -> None:
        if isinstance(getattr(event, "widget", None), Button):
            return
        self.focus()
        self.action_launch()
