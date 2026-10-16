"""
Mods screen: every mod Titan found, grouped by where it comes from, with a switch for
the mod and one for each of its sections.

Switches write the user's own global config, scoped to the active project: a mod
is switched on or off per project, but it is a personal choice, not shared with the team
through the project's own `.titan/config.toml`. They apply at once: switching the mod
unloads or loads it (`reload_mod`), switching a section tells the running mod.
"""

from typing import Dict, Optional

from rich.markup import escape
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from titan_cli.core.logging import get_logger
from titan_cli.core.mods.loader import read_mods_config, reload_mod
from titan_cli.core.mods.settings import set_mod_enabled, set_mod_section
from titan_cli.core.mods.status import FAILED, ModEntry, mod_entries, source_kind
from titan_cli.ui.tui.icons import Icons
from titan_cli.ui.tui.widgets import BoldPrimaryText, BoldText, DimText, LabeledSwitch, ListDetailPanel, Text

from .base import BaseScreen

logger = get_logger(__name__)

SOURCE_TITLES = {
    "titan": "Shipped with Titan",
    "plugin": "From plugins",
    "project": "This project",
    "user": "Yours",
    "dev": "In development",
}
MOD_SWITCH = "mod"
SECTION_PREFIX = "section:"


def state_icon(entry: ModEntry) -> str:
    if entry.status.state == FAILED:
        return Icons.ERROR
    return Icons.SUCCESS if entry.enabled else Icons.ERROR


def status_markup(entry: ModEntry) -> str:
    colour = "red" if entry.status.state == FAILED or not entry.enabled else "green"
    return f"[bold]Status:[/bold] [{colour}]{state_text(entry)}[/{colour}]"


def row_prompt(entry: ModEntry) -> str:
    return f"{state_icon(entry)} {escape(entry.name)} - {state_text(entry)}"


def state_text(entry: ModEntry) -> str:
    if entry.status.state == FAILED:
        return "Load failed"
    return "Enabled" if entry.enabled else "Disabled"


class ModsScreen(BaseScreen):
    """Lists the mods and switches them, and their sections, on or off."""

    BINDINGS = [
        ("escape", "go_back", "Back"),
        ("q", "go_back", "Back"),
        Binding("e", "toggle_mod", "Enable/Disable"),
    ]

    CSS = """
    ModsScreen {
        align: center middle;
    }

    #mods-details-content > * {
        margin: 0;
    }

    #mods-details-content .mods-heading {
        margin-top: 1;
    }
    """

    def __init__(self, config):
        super().__init__(config, title=f"{Icons.PLUGIN} Mods", show_back=True)
        self._entries: Dict[str, ModEntry] = {}
        self._selected: Optional[str] = None
        self._loaded = False

    def compose_content(self) -> ComposeResult:
        yield ListDetailPanel(
            "Mods",
            "Mod Details",
            list_id="mods-list",
            scroll_id="mods-details",
            content_id="mods-details-content",
            list_width=28,
        )

    def on_mount(self) -> None:
        self._load()
        self._loaded = True

    def on_screen_resume(self) -> None:
        super().on_screen_resume()
        # The resume that follows the first mount has nothing new to show.
        if self._loaded:
            self._load()

    def _bus(self):
        return self.app.mods

    def _load(self) -> None:
        bus = self._bus()
        entries = mod_entries(bus.found, bus.statuses, read_mods_config())
        self._entries = {e.name: e for e in entries}
        listing = self.query_one("#mods-list", OptionList)
        listing.clear_options()
        if not entries:
            listing.add_option(Option("No mods installed", id="none", disabled=True))
            self.run_worker(self._show(None), exclusive=True)
            return

        options, group = [], None
        for entry in entries:
            kind = source_kind(entry.manifest.source)
            if kind != group:
                group = kind
                options.append(Option(f"[dim]{SOURCE_TITLES.get(kind, kind)}[/dim]", id=f"group:{kind}", disabled=True))
            options.append(Option(row_prompt(entry), id=entry.name))
        listing.add_options(options)

        target = self._selected if self._selected in self._entries else entries[0].name
        self._selected = target
        listing.highlighted = next(i for i, o in enumerate(options) if o.id == target)
        self.run_worker(self._show(target), exclusive=True)

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        name = event.option.id
        if name in self._entries and name != self._selected:
            self._selected = name
            self.run_worker(self._show(name), exclusive=True)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.on_option_list_option_highlighted(event)

    async def _show(self, name: Optional[str]) -> None:
        content = self.query_one("#mods-details-content", Container)
        await content.remove_children()
        entry = self._entries.get(name) if name else None
        if entry is None:
            await content.mount(Static("[dim]Select a mod[/dim]"))
            return

        manifest = entry.manifest
        widgets = [
            BoldPrimaryText(manifest.name),
            Text(""),
            Static(status_markup(entry), id="mods-status"),
        ]
        if entry.status.state == FAILED:
            widgets.append(Static(f"[red]{escape(entry.status.error or '')}[/red]"))
        if manifest.description:
            widgets += [Text(""), BoldText("Description:"), DimText(manifest.description)]
        widgets.append(Text(""))
        widgets.append(Static(f"[bold]Version:[/bold] {escape(manifest.version)}"))
        widgets.append(Static(f"[bold]Source:[/bold] {escape(SOURCE_TITLES.get(source_kind(manifest.source), manifest.source))}"))
        widgets.append(Static(f"[bold]Folder:[/bold] {escape(str(manifest.folder))}"))
        if manifest.requires_plugins:
            widgets.append(Static(f"[bold]Needs plugins:[/bold] {escape(', '.join(manifest.requires_plugins))}"))
        if manifest.events:
            widgets.append(Static(f"[bold]Events:[/bold] {escape(', '.join(manifest.events))}"))
        if manifest.slots:
            widgets.append(Static(f"[bold]Slots:[/bold] {escape(', '.join(manifest.slots))}"))
        widgets.append(Text(""))

        widgets.append(BoldText("Mod"))
        widgets.append(LabeledSwitch("Enabled", entry.enabled, "Load this mod when Titan starts.", name=MOD_SWITCH))
        if manifest.sections:
            widgets.append(Text(""))
            widgets.append(BoldText("Sections"))
            for section in manifest.sections.values():
                widgets.append(
                    LabeledSwitch(
                        section.title or section.name,
                        entry.sections[section.name],
                        section.description,
                        name=SECTION_PREFIX + section.name,
                        disabled=not entry.enabled,
                    )
                )
        await content.mount(*widgets)

    def on_labeled_switch_changed(self, event: LabeledSwitch.Changed) -> None:
        name = self._selected
        if name is None:
            return
        try:
            if event.switch.name == MOD_SWITCH:
                set_mod_enabled(name, event.value)
                reload_mod(self._bus(), name, read_mods_config())
            elif event.switch.name and event.switch.name.startswith(SECTION_PREFIX):
                section = event.switch.name.removeprefix(SECTION_PREFIX)
                set_mod_section(name, section, event.value)
                # A running mod takes it now; one that is not loaded reads it at its next start.
                self._bus().set_section(name, section, event.value)
        except Exception as e:
            logger.exception("mod_setting_save_failed", mod=name)
            self.notify(f"Could not save: {e}", severity="error")
            # The switch already moved: put it back to what is really stored.
            self._refresh(name)
            return
        self._refresh(name)

    def _refresh(self, name: str) -> None:
        """Show what was just saved on the mod's row and in its open details, without redrawing them."""
        bus = self._bus()
        entry = next((e for e in mod_entries(bus.found, bus.statuses, read_mods_config()) if e.name == name), None)
        if entry is None:
            return
        self._entries[name] = entry
        self.query_one("#mods-list", OptionList).replace_option_prompt(name, row_prompt(entry))
        self.query_one("#mods-status", Static).update(status_markup(entry))
        for switch in self.query(LabeledSwitch):
            if switch.name == MOD_SWITCH:
                switch.value = entry.enabled
            else:
                switch.disabled = not entry.enabled
        if entry.status.state == FAILED:
            # The reason it failed is not in the open details yet.
            self.run_worker(self._show(name), exclusive=True)

    def action_toggle_mod(self) -> None:
        entry = self._entries.get(self._selected or "")
        if entry is None:
            return
        try:
            set_mod_enabled(entry.name, not entry.enabled)
            reload_mod(self._bus(), entry.name, read_mods_config())
        except Exception as e:
            logger.exception("mod_setting_save_failed", mod=entry.name)
            self.notify(f"Could not save: {e}", severity="error")
            self._refresh(entry.name)
            return
        self._refresh(entry.name)
