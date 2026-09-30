"""
A workflow file must not be able to crash the screens that list it.

Titles and descriptions come straight out of workflow YAML into a Textual markup string.
Unescaped, a description containing a stray closing tag does not merely mis-render: it
raises `MarkupError` and takes the render down with it. The Workflows screen used to build
its rows as `f"[bold]{title}[/bold]\\n[dim]{description}[/dim]"`, so one malformed workflow
killed the whole list; the card replaced that, and this is the guard that it stays replaced.

Pure rendering of the body string - nothing is mounted.
"""

import pytest
from rich.errors import MarkupError
from rich.text import Text

from titan_cli.ui.tui.widgets import WorkflowCard

# The shapes that actually break, rather than a generic "[foo]".
HOSTILE = [
    "closes a tag nobody opened: [/bold]",
    "an unclosed one: [bold] and then nothing",
    "a real style name in prose: use [red] for errors",
    "square brackets as prose: pick [one] of these",
    "a stray bracket at the end [",
]


@pytest.mark.parametrize("text", HOSTILE)
def test_a_hostile_description_renders_as_markup(text):
    card = WorkflowCard(
        workflow_name="wf",
        title="Title",
        group="Git",
        description=text,
    )
    # The body is markup, so this is what the render pipeline does with it.
    Text.from_markup(str(card.renderable))


@pytest.mark.parametrize("text", HOSTILE)
def test_a_hostile_title_renders_as_markup(text):
    card = WorkflowCard(
        workflow_name="wf",
        title=text,
        group="Git",
        description="safe",
    )
    Text.from_markup(str(card.renderable))


def test_the_same_text_unescaped_would_have_raised():
    """
    The half that makes the tests above mean something.

    Without it they would pass on any implementation, including one that silently dropped
    the description - so this pins that the input really is dangerous.
    """
    with pytest.raises(MarkupError):
        Text.from_markup("[bold]Title[/bold]\n[dim]closes a tag nobody opened: [/bold][/dim]")


def test_the_description_survives_escaping():
    """Escaped, not stripped: the user still reads what the YAML said."""
    card = WorkflowCard(
        workflow_name="wf",
        title="Title",
        group="Git",
        description="pick [one] of these",
    )
    rendered = Text.from_markup(str(card.renderable)).plain
    assert "pick [one] of these" in rendered
