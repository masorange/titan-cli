"""The shared "Fix with AI" button, `m.ai.assist` behind it, and the spacing of the error card."""

from titan_cli.core.mods import ModBus, Text, error_card, fix_with_ai_button


class Host:
    def __init__(self, refusal=None):
        self.assists, self.refusal = [], refusal

    def ai_assist(self, mod, prompt, cwd):
        self.assists.append((mod, prompt, cwd))
        return self.refusal


def api(refusal=None):
    bus = ModBus()
    bus.host = Host(refusal)
    return bus.api("github"), bus.host


def test_assist_opens_the_cli_with_the_prompt_and_says_it_opened():
    m, host = api()

    assert m.ai.assist("fix this", cwd="/repo") is True
    assert host.assists == [("github", "fix this", "/repo")]


def test_assist_says_no_when_the_host_refuses():
    m, host = api(refusal="no CLI installed")

    assert m.ai.assist("fix this") is False


def test_the_button_hands_the_error_to_the_cli_through_assist_with_no_workflow():
    m, host = api()

    fix_with_ai_button(m, "Could not HEAD ...: 429").on_press()

    (_, prompt, cwd), = host.assists
    assert "Could not HEAD ...: 429" in prompt and "Find its cause in the code" in prompt and cwd is None


def test_the_context_goes_after_the_error():
    m, host = api()

    fix_with_ai_button(m, "boom", context="branch: feat/x", cwd="/repo").on_press()

    (_, prompt, cwd), = host.assists
    assert prompt.endswith("boom\n\nbranch: feat/x") and cwd == "/repo"


def test_no_workflow_is_shipped_for_it():
    from pathlib import Path

    assert not (Path(__file__).resolve().parents[3] / "titan_cli" / "workflows").exists()


def test_the_error_card_leaves_a_blank_line_between_the_message_and_its_buttons():
    card = error_card("boom", copy=lambda text, what: None, actions=[fix_with_ai_button(api()[0], "boom")])

    kinds = [type(child).__name__ for child in card.children]
    blank = card.children[kinds.index("Box") - 1]

    assert isinstance(blank, Text) and blank.parts == (" ",)
