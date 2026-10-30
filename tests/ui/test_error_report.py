from titan_cli.core.result import ClientError
from titan_cli.engine.results import Error
from titan_cli.ui.tui.error_report import describe_error
from titan_cli.ui.tui.widgets.collapsible_list import CopyButton


def test_a_plain_message_is_the_whole_report():
    report = describe_error("Push rejected")
    assert report.message == "Push rejected"
    assert report.as_text() == "Push rejected"


def test_title_comes_first_in_the_copy():
    assert describe_error("boom", "Workflow failed").as_text() == "Workflow failed\nboom"


def test_client_error_carries_its_code_and_details():
    report = describe_error(ClientError("not found", error_code="NOT_FOUND", details={"pr": 5}))
    assert report.as_text() == "not found\ncode: NOT_FOUND\npr: 5"


def test_engine_error_names_its_exception_and_copies_the_traceback():
    try:
        raise ValueError("bad input")
    except ValueError as exc:
        report = describe_error(Error("step failed", exception=exc))

    assert report.details == ["exception: ValueError"]
    assert "Traceback" in report.as_text() and "ValueError: bad input" in report.as_text()
    assert "Traceback" not in report.message


def test_engine_error_default_code_is_not_noise():
    assert describe_error(Error("x")).details == []
    assert describe_error(Error("x", code=429)).details == ["code: 429"]


def test_an_exception_without_message_still_says_what_it_is():
    assert describe_error(KeyError()).message == "KeyError"


def test_copy_button_caption_makes_it_a_labelled_button():
    assert str(CopyButton("t", "error", caption="Copy error").renderable) == "⧉ Copy error"
    assert str(CopyButton("t").renderable) == "⧉"


def test_mod_error_card_copies_its_text_and_keeps_the_mods_own_actions():
    from titan_cli.ui.elements import Button
    from titan_cli.ui.components import error_card

    copied = []
    card = error_card("push rejected\nnon-fast-forward", copy=lambda text, what: copied.append((text, what)),
                      title="Could not push", details=["code=API_ERROR"],
                      actions=[Button("✦ Ask AI to fix", lambda: None)])

    buttons = [c for c in card.children[-1].children]
    assert [b.label for b in buttons] == ["⧉ Copy error", "✦ Ask AI to fix"]
    buttons[0].on_press()
    assert copied == [("Could not push\npush rejected\nnon-fast-forward\ncode=API_ERROR", "error")]
    assert card.border == "error"


def test_every_error_a_step_shows_is_an_error_card_with_copy_and_extra_buttons():
    from unittest.mock import MagicMock

    from titan_cli.ui.tui.textual_components import TextualComponents
    from titan_cli.ui.tui.widgets import ErrorCard

    app, output = MagicMock(), MagicMock()
    app.call_from_thread = lambda fn: fn()
    ui = TextualComponents(app, output)
    assert ui.error_shown is False

    ui.error_text("[bold] push rejected", actions=[("⟳ Retry", lambda: None)])

    card = output.mount.call_args.args[0]
    assert isinstance(card, ErrorCard)
    assert card.report.message == "[bold] push rejected"  # plain text: brackets are not markup
    assert [label for label, _ in card._actions] == ["⟳ Retry"]
    assert ui.error_shown is True


def test_an_error_toast_opens_the_error_card_and_other_toasts_stay_toasts():
    from unittest.mock import MagicMock

    from titan_cli.ui.tui.app import TitanApp

    app = MagicMock()
    TitanApp.notify(app, "[bold]Could not save[/bold]: disk full", severity="error", title="mods")
    app.show_error.assert_called_once_with("Could not save: disk full", "mods")



def test_a_mods_error_toast_is_an_error_card():
    from unittest.mock import MagicMock

    from titan_cli.ui.tui.mods_ui import TitanModHost

    app = MagicMock()
    app._thread_id = None
    host = TitanModHost.__new__(TitanModHost)
    host._app = app
    host._on_app_thread = lambda fn: fn()

    host.toast("github", "Could not merge #2: [x]", "error")

    app.show_error.assert_called_once_with("Could not merge #2: [x]", "github")
    app.notify.assert_not_called()


def test_an_error_panel_is_an_error_card_whoever_builds_it():
    from titan_cli.ui.tui.widgets import ErrorCard, Panel

    assert isinstance(Panel("Missing project", panel_type="error"), ErrorCard)
    assert isinstance(Panel("Heads up", panel_type="warning"), Panel)
