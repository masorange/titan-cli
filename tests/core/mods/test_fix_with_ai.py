"""The shared "Fix with AI" button and the spacing of the error card it sits in."""
from pathlib import Path

import yaml

from titan_cli.core.mods import ModBus, Text, error_card, fix_with_ai_button
from titan_cli.core.mods.fix_with_ai import FIX_WORKFLOW


class Host:
    def __init__(self):
        self.runs = []

    def run_workflow(self, mod, name, params):
        self.runs.append((name, dict(params)))
        return None


def api():
    bus = ModBus()
    bus.host = Host()
    return bus.api("github"), bus.host


def test_the_button_runs_the_fix_workflow_with_the_error_as_its_param():
    m, host = api()

    fix_with_ai_button(m, "Could not HEAD ...: 429").on_press()

    assert host.runs == [(FIX_WORKFLOW, {"fix_error": "Could not HEAD ...: 429"})]


def test_the_context_goes_after_the_error():
    m, host = api()

    fix_with_ai_button(m, "boom", context="branch: feat/x").on_press()

    assert host.runs[0][1]["fix_error"] == "boom\n\nbranch: feat/x"


def test_the_workflow_is_the_one_titan_ships_and_takes_the_error_from_its_param():
    shipped = Path(__file__).resolve().parents[3] / "titan_cli" / "workflows" / f"{FIX_WORKFLOW}.yaml"

    flow = yaml.safe_load(shipped.read_text())

    (step,) = flow["steps"]
    assert (step["plugin"], step["step"]) == ("core", "ai_code_assistant")
    assert step["params"]["context_key"] == "fix_error" and "fix_error" in flow["params"]


def test_the_error_card_leaves_a_blank_line_between_the_message_and_its_buttons():
    card = error_card("boom", copy=lambda text, what: None, actions=[fix_with_ai_button(api()[0], "boom")])

    kinds = [type(child).__name__ for child in card.children]
    blank = card.children[kinds.index("Box") - 1]

    assert isinstance(blank, Text) and blank.parts == (" ",)
