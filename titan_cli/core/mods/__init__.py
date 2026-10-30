"""Mods: user code that hooks Titan's runtime events. See `bus.py` for the hook contract."""

from .bus import AIAnswer, AssistResult, DockSlot, HomeCardSlot, ModAPI, ModBus, ModHost
from .error_card import error_card
from .ai_answer import AIResult, ai_answer_box, ai_ask_button, ai_chip, ai_result, ask_ai, refresh_ai_chip
from .ai_assist import ai_assist_button, fix_prompt
from .elements import Box, Button, Input, Link, Text
from .choice_card import Option, choice_card
from .events import AppStart, SectionChange, StepCall, UIRender, WorkflowRun, outcome
from .state import ModState
from .loader import ModManifest, build_mod_bus, discover_mods, import_mod, load_mods, mod_sources, read_manifest, reload_mod

__all__ = [
    "AIAnswer",
    "AssistResult",
    "DockSlot",
    "HomeCardSlot",
    "AppStart",
    "SectionChange",
    "Box",
    "error_card",
    "AIResult",
    "ai_answer_box",
    "ai_ask_button",
    "ai_assist_button",
    "ai_chip",
    "ai_result",
    "ask_ai",
    "refresh_ai_chip",
    "fix_prompt",
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
