"""
The two AI cells of the status bar: what F2 will run, and what F3 will answer with.

The bar is the only place those shortcuts are advertised, so what it says about them is
worth pinning down.
"""

import asyncio
from unittest.mock import MagicMock

from textual.widgets import Static

from titan_cli.core.models import AIConfig, AIConnectionConfig
from titan_cli.ui.tui.app import TitanApp
from titan_cli.ui.tui.screens.base import BaseScreen
from titan_cli.ui.tui.widgets import StatusBarWidget


class _BarScreen(BaseScreen):
    """The thinnest screen that still carries the status bar."""

    def __init__(self, config):
        super().__init__(config, title="Bar")

    def compose_content(self):
        yield Static("content")


def _config(ai_config):
    config = MagicMock()
    config.config.ai = ai_config
    config.get_project_name.return_value = "titan-cli"
    config.registry.ensure_initialized.return_value = None
    return config


def _cells(ai_config):
    captured = {}

    async def run():
        config = _config(ai_config)
        app = TitanApp(config, initial_screen=lambda: _BarScreen(config))
        async with app.run_test() as pilot:
            await pilot.pause()
            bar = app.screen.query_one(StatusBarWidget)
            captured["cli"] = bar.cli_info
            captured["ai"] = bar.ai_info
            captured["rendered"] = [
                str(cell.render()) for cell in bar.query(Static)
            ]

    asyncio.run(run())
    return captured


def _gateway(model="gpt-5"):
    return AIConnectionConfig(
        name="Work gateway",
        connection_type="gateway",
        gateway_backend="openai_compatible",
        base_url="https://gateway.example/v1",
        default_model=model,
    )


def test_both_cells_name_the_key_that_changes_them():
    cells = _cells(
        AIConfig(
            default_cli="claude",
            cli_models={"claude": "opus"},
            default_connection="work",
            connections={"work": _gateway()},
        )
    )

    assert cells["cli"] == "F2 claude / opus"
    assert cells["ai"].startswith("F3 ")
    assert "gpt-5" in cells["ai"]


def test_an_unpinned_cli_model_reads_as_the_clis_own_default():
    """The CLI still has a model; Titan just isn't the one choosing it."""
    cells = _cells(AIConfig(default_cli="gemini"))

    assert cells["cli"] == "F2 gemini / default"


def test_nothing_configured_shows_a_dash_rather_than_a_stale_name():
    cells = _cells(AIConfig())

    assert cells["cli"] == "F2 —"
    assert cells["ai"] == "F3 —"


def test_the_bar_renders_four_cells():
    cells = _cells(AIConfig(default_cli="claude"))

    assert len(cells["rendered"]) == 4


class TestSessionOverrideInTheBar:
    """
    An active session override takes over the F2 cell and marks itself (air-004, D-003).

    Showing the saved value while something else actually runs would make the bar lie -
    and this is the only place an override announces itself once the picker is closed.
    """

    @staticmethod
    def _cells_with_override(ai_config, *, cli=None, model=None):
        captured = {}

        async def run():
            config = _config(ai_config)
            app = TitanApp(config, initial_screen=lambda: _BarScreen(config))
            async with app.run_test() as pilot:
                await pilot.pause()
                app.ai_session_override.cli = cli
                app.ai_session_override.model = model
                app.refresh_status_bar()
                await pilot.pause()
                captured["cli"] = app.screen.query_one(StatusBarWidget).cli_info

        asyncio.run(run())
        return captured

    def test_an_overridden_cli_replaces_the_saved_one_and_is_starred(self):
        cells = self._cells_with_override(
            AIConfig(default_cli="claude", cli_models={"claude": "opus"}), cli="codex"
        )

        assert cells["cli"] == "F2 codex / default *"

    def test_an_overridden_model_shows_against_the_saved_cli(self):
        cells = self._cells_with_override(
            AIConfig(default_cli="claude", cli_models={"claude": "opus"}), model="haiku"
        )

        assert cells["cli"] == "F2 claude / haiku *"

    def test_no_override_leaves_the_cell_exactly_as_it_was(self):
        cells = self._cells_with_override(
            AIConfig(default_cli="claude", cli_models={"claude": "opus"})
        )

        assert cells["cli"] == "F2 claude / opus"
