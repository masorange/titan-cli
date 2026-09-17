"""
The session override reaches a running workflow (ai_task_routing air-004).

The seam is narrow but easy to get wrong: the app owns one mutable override, the context
builder makes a fresh `AIExecutor` per run, and what must travel is the OBJECT - a copy
taken at build time would freeze whatever was set just before the user pressed F2.
"""

from unittest.mock import MagicMock

from titan_cli.ai.router.session import AISessionOverride
from titan_cli.core.models import AIConfig
from titan_cli.engine.builder import WorkflowContextBuilder


def _builder(**kwargs):
    return WorkflowContextBuilder(
        plugin_registry=MagicMock(), ai_config=AIConfig(default_cli="claude"), **kwargs
    )


def test_the_router_built_for_a_run_carries_the_session_override(mocker):
    mocker.patch("titan_cli.engine.builder.create_broker_factory")
    override = AISessionOverride(cli="codex")

    ctx = _builder().with_ai_router(session_override=override).build()

    assert ctx.ai_router.resolver.session_override is override


def test_a_run_started_without_one_still_works(mocker):
    """Nothing overridden is the normal case and must not need a placeholder."""
    mocker.patch("titan_cli.engine.builder.create_broker_factory")

    ctx = _builder().with_ai_router().build()

    assert ctx.ai_router.resolver.session_override is None


def test_changing_the_override_after_the_context_is_built_still_applies(mocker):
    """The user presses F2 between runs, not between builder calls."""
    mocker.patch("titan_cli.engine.builder.create_broker_factory")
    override = AISessionOverride()

    ctx = _builder().with_ai_router(session_override=override).build()
    override.cli = "gemini"

    assert ctx.ai_router.resolver.session_override.cli == "gemini"
