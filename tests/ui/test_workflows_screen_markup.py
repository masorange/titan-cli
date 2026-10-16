"""
A workflow file must not be able to crash the list that shows it.

The Workflows screen builds each row as a Textual markup string from the workflow's own
title and description, both of which come straight out of YAML. Unescaped, a description
containing a stray closing tag does not merely mis-render: it raises `MarkupError`, so one
malformed workflow file made the whole screen unopenable.

Pure row building - nothing is mounted, and the screen is never initialized as a widget.
"""

from pathlib import Path

import pytest
from rich.errors import MarkupError
from rich.text import Text

from titan_cli.core.workflows.workflow_sources import WorkflowInfo
from titan_cli.ui.tui.screens.workflows import WorkflowsScreen

# The shapes that actually break, rather than a generic "[foo]".
HOSTILE = [
    "closes a tag nobody opened: [/bold]",
    "an unclosed one: [bold] and then nothing",
    "a real style name in prose: use [red] for errors",
    "square brackets as prose: pick [one] of these",
    "a stray bracket at the end [",
]


def _screen() -> WorkflowsScreen:
    """The screen as a plain object, with only what row building reads.

    Built without `__init__` on purpose: constructing a Textual `Screen` needs an app, and
    the thing under test is a pure string transformation that does not.
    """
    screen = WorkflowsScreen.__new__(WorkflowsScreen)
    screen._favorite_names = set()
    screen._plugin_source_map = {}
    return screen


def _workflow(title: str = "Title", description: str = "safe") -> WorkflowInfo:
    return WorkflowInfo(
        name="wf",
        description=description,
        source="project",
        path=Path("/tmp/wf.yaml"),
        title=title,
    )


def _rows(workflow: WorkflowInfo):
    return _screen()._build_workflow_options([workflow])


@pytest.mark.parametrize("text", HOSTILE)
def test_a_hostile_description_renders_as_markup(text):
    for option in _rows(_workflow(description=text)):
        Text.from_markup(str(option.prompt))


@pytest.mark.parametrize("text", HOSTILE)
def test_a_hostile_title_renders_as_markup(text):
    for option in _rows(_workflow(title=text)):
        Text.from_markup(str(option.prompt))


def test_the_same_row_unescaped_would_have_raised():
    """
    The half that makes the tests above mean something.

    Without it they would pass on any implementation, including one that dropped the
    description - so this pins that the input really is dangerous.
    """
    with pytest.raises(MarkupError):
        Text.from_markup("[bold]Title[/bold]\n[dim]closes a tag nobody opened: [/bold][/dim]")


def test_the_text_survives_escaping():
    """Escaped, not stripped: the user still reads what the YAML said."""
    option = _rows(_workflow(description="pick [one] of these"))[0]
    assert "pick [one] of these" in Text.from_markup(str(option.prompt)).plain


def test_a_missing_description_does_not_become_the_word_none():
    """`WorkflowInfo.description` is not optional in the type, but empty in practice."""
    option = _rows(_workflow(description=""))[0]
    assert "None" not in Text.from_markup(str(option.prompt)).plain
