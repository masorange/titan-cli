"""The shared help button, `m.ai.assist` behind it, and the spacing of the error card."""

from titan_cli.core.mods import AssistResult, ModBus, Text, ai_assist_button, error_card, fix_prompt


class Host:
    def __init__(self, refusal=None):
        self.assists, self.refusal = [], refusal

    def ai_assist(self, mod, prompt, cwd):
        self.assists.append((mod, prompt, cwd))
        return AssistResult(False, self.refusal) if self.refusal else AssistResult(True)


def api(refusal=None):
    bus = ModBus()
    bus.host = Host(refusal)
    return bus.api("github"), bus.host


def test_assist_opens_the_cli_with_the_prompt_and_says_it_opened():
    m, host = api()

    assert m.ai.assist("fix this", cwd="/repo") == AssistResult(True)
    assert host.assists == [("github", "fix this", "/repo")]


def test_assist_says_no_when_the_host_refuses():
    m, host = api(refusal="no CLI installed")

    assert m.ai.assist("fix this") == AssistResult(False, "no CLI installed")


def test_the_button_hands_its_prompt_to_the_cli_through_assist_with_no_workflow():
    m, host = api()

    button = ai_assist_button(m, "summarise this issue", label="✦ Summarise")
    button.on_press()

    assert button.label == "✦ Summarise"
    assert host.assists == [("github", "summarise this issue", None)]


def test_the_fix_prompt_carries_the_error_whole_and_the_context_after_it():
    prompt = fix_prompt("Could not HEAD ...: 429", context="branch: feat/x")

    assert "Find its cause in the code" in prompt and prompt.endswith("Could not HEAD ...: 429\n\nbranch: feat/x")
    assert fix_prompt("boom").endswith("\n\nboom")


def test_the_button_opens_the_cli_in_the_directory_it_was_given():
    m, host = api()

    ai_assist_button(m, fix_prompt("boom"), cwd="/repo").on_press()

    assert host.assists[0][2] == "/repo"


def test_no_workflow_is_shipped_for_it():
    from pathlib import Path

    assert not (Path(__file__).resolve().parents[3] / "titan_cli" / "workflows").exists()


def test_the_error_card_leaves_a_blank_line_between_the_message_and_its_buttons():
    card = error_card("boom", copy=lambda text, what: None, actions=[ai_assist_button(api()[0], fix_prompt("boom"))])

    kinds = [type(child).__name__ for child in card.children]
    blank = card.children[kinds.index("Box") - 1]

    assert isinstance(blank, Text) and blank.parts == (" ",)
