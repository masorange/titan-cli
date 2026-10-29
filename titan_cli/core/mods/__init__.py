"""Mods: user code that hooks Titan's runtime events. See `bus.py` for the hook contract."""

from .bus import AIAnswer, DockSlot, HomeCardSlot, ModAPI, ModBus, ModHost
from .error_card import error_card
from .fix_with_ai import fix_with_ai_button
from .elements import Box, Button, Input, Link, Text
from .choice_card import Option, choice_card
from .events import AppStart, SectionChange, StepCall, UIRender, WorkflowRun, outcome
from .state import ModState
from .loader import ModManifest, build_mod_bus, discover_mods, import_mod, load_mods, mod_sources, read_manifest, reload_mod

__all__ = [
    "AIAnswer",
    "DockSlot",
    "HomeCardSlot",
    "AppStart",
    "SectionChange",
    "Box",
    "error_card",
    "fix_with_ai_button",
    "Option",
    "choice_card",
    "Button",
    "Link",
    "ModAPI",
    "ModBus",
    "ModHost",
    "ModState",
    "Input",
    "StepCall",
    "Text",
    "UIRender",
    "WorkflowRun",
    "ModManifest",
    "build_mod_bus",
    "discover_mods",
    "import_mod",
    "load_mods",
    "reload_mod",
    "mod_sources",
    "outcome",
    "read_manifest",
]
