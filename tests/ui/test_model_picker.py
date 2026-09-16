"""
Tests for the model picker: the F3 shortcut and the modal both entry points share.

Mounts the real app and presses the real keys, matching the other screen-mount tests.
"""

import asyncio
from unittest.mock import MagicMock

from textual.screen import Screen
from textual.widgets import Input, Static

from titan_cli.core.models import AIConfig, AIConnectionConfig
from titan_cli.ui.tui.app import TitanApp
from titan_cli.ui.tui.screens.model_picker import (
    ModelChoice,
    SelectModelModal,
    cli_model_loader,
)
from titan_cli.ui.tui.widgets import StyledOptionList


class _BlankScreen(Screen):
    def compose(self):
        yield Static("blank")


def _gateway_connection(model="gpt-5"):
    return AIConnectionConfig(
        name="Work gateway",
        connection_type="gateway",
        gateway_backend="openai_compatible",
        base_url="https://gateway.example/v1",
        default_model=model,
    )


def _direct_connection():
    return AIConnectionConfig(
        name="Anthropic",
        connection_type="direct_provider",
        provider="anthropic",
        default_model="claude-sonnet-5",
    )


def _config(ai_config):
    config = MagicMock()
    config.config.ai = ai_config
    config.get_project_name.return_value = "test-project"
    config.get_cli_model.side_effect = lambda cli: ai_config.cli_models.get(cli)
    return config


def _stub_gateway(monkeypatch, models=("fast-model", "big-model"), error=None):
    """Stand in for the broker-built gateway client the picker loads from."""

    class _Client:
        def list_models(self):
            if error:
                raise error
            return [MagicMock(id=name, owned_by="acme") for name in models]

    broker = MagicMock()
    broker.create_client.return_value = _Client()
    factory = MagicMock()
    factory.for_plugin.return_value = broker
    monkeypatch.setattr(
        "titan_cli.core.security.create_broker_factory", lambda root: factory
    )


class TestQuickModelShortcut:
    """F3 changes which model the default connection answers with."""

    def _run(self, config, monkeypatch, keys=()):
        captured = {}

        async def run():
            app = TitanApp(config, initial_screen=lambda: _BlankScreen())
            async with app.run_test() as pilot:
                await pilot.pause()
                app.notify = lambda message, **kwargs: captured.setdefault(
                    "notices", []
                ).append(message)
                await pilot.press("f3")
                await pilot.pause()
                captured["screen"] = app.screen
                if isinstance(app.screen, SelectModelModal):
                    # The loader runs in a worker; wait for what it mounts.
                    for _ in range(6):
                        await pilot.pause()
                    try:
                        option_list = app.screen.query_one(StyledOptionList)
                        captured["options"] = [
                            str(option_list.get_option_at_index(i).prompt)
                            for i in range(option_list.option_count)
                        ]
                    except Exception:
                        captured["options"] = []
                for key in keys:
                    await pilot.press(key)
                    await pilot.pause()
                captured["final_screen"] = app.screen
                captured["has_input"] = bool(app.screen.query(Input))

        asyncio.run(run())
        return captured

    def test_f3_lists_the_models_the_gateway_publishes(self, monkeypatch):
        _stub_gateway(monkeypatch)
        config = _config(
            AIConfig(default_connection="work", connections={"work": _gateway_connection()})
        )

        captured = self._run(config, monkeypatch)

        assert isinstance(captured["screen"], SelectModelModal)
        assert any("fast-model" in option for option in captured["options"])

    def test_choosing_a_model_saves_it_on_the_connection(self, monkeypatch):
        _stub_gateway(monkeypatch)
        config = _config(
            AIConfig(default_connection="work", connections={"work": _gateway_connection()})
        )

        self._run(config, monkeypatch, keys=["enter"])

        config.update_ai_connection.assert_called_once_with(
            "work", {"default_model": "fast-model"}
        )

    def test_escape_changes_nothing(self, monkeypatch):
        _stub_gateway(monkeypatch)
        config = _config(
            AIConfig(default_connection="work", connections={"work": _gateway_connection()})
        )

        self._run(config, monkeypatch, keys=["escape"])

        config.update_ai_connection.assert_not_called()

    def test_without_a_default_connection_f3_explains_instead_of_opening(self, monkeypatch):
        _stub_gateway(monkeypatch)
        config = _config(AIConfig())

        captured = self._run(config, monkeypatch)

        assert not isinstance(captured["screen"], SelectModelModal)
        assert any("No default AI connection" in n for n in captured["notices"])

    def test_a_direct_provider_has_no_list_to_show(self, monkeypatch):
        """Only gateways publish one; saying so beats an empty modal."""
        _stub_gateway(monkeypatch)
        config = _config(
            AIConfig(default_connection="anthropic", connections={"anthropic": _direct_connection()})
        )

        captured = self._run(config, monkeypatch)

        assert not isinstance(captured["screen"], SelectModelModal)
        assert any("gateway" in n for n in captured["notices"])

    def test_a_gateway_that_cannot_be_reached_still_lets_you_type_one(self, monkeypatch):
        """A listing is a convenience; naming a model must not depend on it."""
        _stub_gateway(monkeypatch, error=RuntimeError("connection refused"))
        config = _config(
            AIConfig(default_connection="work", connections={"work": _gateway_connection()})
        )

        captured = self._run(config, monkeypatch)

        assert isinstance(captured["screen"], SelectModelModal)
        assert captured["has_input"]


class TestSelectModelModal:
    """The modal itself, independent of what feeds it."""

    def _mount(self, loader, *, current=None, keys=(), text=None):
        captured = {}

        class _Host(Screen):
            def compose(self):
                yield Static("host")

            def on_mount(self):
                self.app.push_screen(
                    SelectModelModal("Pick one", "subtitle", loader, current=current),
                    lambda value: captured.setdefault("dismissed", value),
                )

        async def run():
            app = TitanApp(_config(AIConfig()), initial_screen=lambda: _Host())
            async with app.run_test() as pilot:
                # The loader runs in a worker, so the content it mounts lands a few
                # frames after the modal itself.
                for _ in range(6):
                    await pilot.pause()
                if text is not None:
                    app.screen.query_one(Input).value = text
                for key in keys:
                    await pilot.press(key)
                    await pilot.pause()
                # Read the DOM before the app tears it down.
                entries = app.screen.query(Input)
                captured["has_input"] = bool(entries)
                captured["input_value"] = entries[0].value if entries else None

        asyncio.run(run())
        return captured

    def test_a_source_with_no_models_goes_straight_to_the_text_entry(self):
        captured = self._mount(lambda: [])

        assert captured["has_input"]

    def test_the_text_entry_is_prefilled_with_what_is_in_force(self):
        captured = self._mount(lambda: [], current="opus")

        assert captured["input_value"] == "opus"

    def test_a_typed_identifier_is_returned_verbatim(self):
        captured = self._mount(lambda: [], keys=["enter"], text="claude-opus-5")

        assert captured["dismissed"] == "claude-opus-5"

    def test_an_emptied_field_leaves_the_setting_alone(self):
        captured = self._mount(lambda: [], keys=["enter"], text="   ", current="opus")

        assert captured["dismissed"] is None

    def test_a_listed_model_is_returned_by_its_identifier(self):
        captured = self._mount(
            lambda: [ModelChoice("anthropic/claude-sonnet-5", "acme")], keys=["enter"]
        )

        assert captured["dismissed"] == "anthropic/claude-sonnet-5"

    def test_the_list_always_offers_typing_one_it_does_not_know(self):
        """A model newer than the source's list still has to be reachable."""
        captured = self._mount(lambda: [ModelChoice("old-model")], keys=["down", "enter"])

        assert captured["has_input"]
        assert "dismissed" not in captured


class TestCliModelLoader:

    def test_it_asks_the_adapter_for_that_cli(self, monkeypatch):
        adapter = MagicMock()
        adapter.list_models.return_value = [
            MagicMock(identifier="opus", label="Opus - most capable")
        ]
        monkeypatch.setattr(
            "titan_cli.external_cli.adapters.get_headless_adapter", lambda name: adapter
        )

        choices = cli_model_loader("claude")()

        assert choices == [ModelChoice("opus", "Opus - most capable")]

    def test_a_cli_with_no_adapter_offers_nothing_rather_than_failing(self):
        assert cli_model_loader("not-a-cli")() == []
