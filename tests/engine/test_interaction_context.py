from unittest.mock import MagicMock

from titan_cli.engine.context import WorkflowContext
from titan_cli.engine.interaction.headless import HeadlessInteractionPort
from titan_cli.engine.interaction.textual import TextualInteractionPort


def test_context_defaults_to_headless_interaction():
    ctx = WorkflowContext(secrets=MagicMock())

    assert isinstance(ctx.interaction, HeadlessInteractionPort)
    assert ctx.textual is None


def test_context_wraps_legacy_textual_in_interaction_port():
    textual = MagicMock()

    ctx = WorkflowContext(secrets=MagicMock(), textual=textual)

    assert isinstance(ctx.interaction, TextualInteractionPort)
    assert ctx.textual is textual
