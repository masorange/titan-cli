"""
Every blocking ask_* method must abort the workflow when the app is no longer running.

Two guarantees, and the second exists because the first was met the wrong way.

**It must not hang.** The workflow runs on a NON-DAEMON executor thread (Textual
thread worker → asyncio's default ThreadPoolExecutor), and `concurrent.futures`
joins those threads at interpreter exit. So an ask_* wait loop with no app-exit
escape turns "quit while a prompt is open" into a hung console: the TUI is gone,
the prompt thread spins forever, and the atexit join never returns until a second
Ctrl+C kills it with a threading-shutdown traceback. A KeyboardInterrupt handler
inside the loop cannot prevent this - SIGINT is only ever delivered to the main
thread, never to the worker.

**It must not answer for the user.** The escape used to return the prompt's
default, which unblocks the thread but lets the rest of the step run on invented
answers with no UI to show them in. Quitting at "Export report as PDF?" (default
True) still wrote the PDF, and would have said yes to publishing it. So the escape
raises `WorkflowAborted` instead: a BaseException, so the `except Exception` that
converts step failures into step errors does not catch it, and it unwinds to
`workflow_execution.py`, which logs it and lets the thread die.

These tests run each prompt on a plain thread against an app that reports
`is_running = False`. A regression that hangs shows up as the join timeout; a
regression that answers for the user shows up as a missing `WorkflowAborted`.
"""

import threading

import pytest

from titan_cli.core.interrupt import WorkflowAborted
from titan_cli.engine.option_item import OptionItem
from titan_cli.ui.tui.textual_components import TextualComponents
from titan_cli.ui.tui.widgets import ChoiceOption, SelectionOption


class _ExitingApp:
    """An app in the state right after the user quit: not running, loop gone."""

    is_running = False

    def call_from_thread(self, fn, *args, **kwargs):
        raise RuntimeError("App is closing")


def _raises_on_thread(fn, timeout=5.0):
    """Run fn on a thread and return what it raised; fail (not hang) if it never returns."""
    box = {}

    def target():
        try:
            box["result"] = fn()
        except BaseException as exc:  # WorkflowAborted is not an Exception
            box["raised"] = exc

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(timeout=timeout)
    assert not thread.is_alive(), (
        "the prompt stayed blocked after the app stopped running - this is the "
        "hung-console-on-Ctrl+C bug"
    )
    assert "raised" in box, (
        f"the prompt returned {box.get('result')!r} instead of aborting - answering for "
        "the user is how quitting mid-prompt used to still generate the PDF"
    )
    return box["raised"]


@pytest.fixture
def components():
    return TextualComponents(app=_ExitingApp(), output_widget=None)


def test_ask_option_aborts_when_app_stops(components):
    assert isinstance(
        _raises_on_thread(
            lambda: components.ask_option("pick", [OptionItem(value=1, title="one")])
        ),
        WorkflowAborted,
    )


def test_ask_multiselect_aborts_when_app_stops(components):
    assert isinstance(
        _raises_on_thread(
            lambda: components.ask_multiselect(
                "pick", [SelectionOption(value="a", label="A", selected=False)]
            )
        ),
        WorkflowAborted,
    )


def test_ask_text_aborts_when_app_stops(components):
    assert isinstance(
        _raises_on_thread(lambda: components.ask_text("name?", default="dft")),
        WorkflowAborted,
    )


def test_ask_confirm_aborts_instead_of_confirming(components):
    """The one that wrote unwanted PDFs: default True became a silent yes."""
    assert isinstance(
        _raises_on_thread(lambda: components.ask_confirm("sure?", default=True)),
        WorkflowAborted,
    )


def test_ask_choice_aborts_when_app_stops(components):
    assert isinstance(
        _raises_on_thread(
            lambda: components.ask_choice("pick", [ChoiceOption(value="y", label="Yes")])
        ),
        WorkflowAborted,
    )


def test_ask_password_aborts_when_app_stops(components):
    """The secret broker prompts through this one; an empty secret must not flow on."""
    assert isinstance(
        _raises_on_thread(lambda: components.ask_password("passphrase?")),
        WorkflowAborted,
    )


def test_ask_multiline_aborts_when_app_stops(components):
    assert isinstance(
        _raises_on_thread(lambda: components.ask_multiline("body?", default="dft")),
        WorkflowAborted,
    )
