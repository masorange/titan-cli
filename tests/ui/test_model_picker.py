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
    """
    F3 opens the connection picker; M from there chooses that connection's model.

    F3 used to go straight to the model modal. It now mirrors F2 (D-006), so every test
    here presses f3 then m - the extra keystroke is the point of the change, not an
    accident of the harness.
    """

    def _run(self, config, monkeypatch, keys=(), open_model=True):
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
                captured["picker"] = app.screen
                # Read the rendered text while the app is still running: querying a
                # widget after the test app shuts down finds nothing.
                captured["picker_text"] = " ".join(
                    str(w.renderable) for w in app.screen.query(Static)
                )
                if open_model:
                    await pilot.press("m")
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

    def test_choosing_a_model_saves_it_only_once_the_picker_is_accepted(self, monkeypatch):
        """
        The model is now part of a composition, not an immediate write (D-009).

        This test used to end at `enter` in the model list. That keystroke no longer
        saves anything: it hands the model back to the quick picker, which holds it until
        the user accepts - which is the point of the change, since Escape used to leave
        the model written.
        """
        from titan_cli.ui.tui.widgets import Button

        _stub_gateway(monkeypatch)
        config = _config(
            AIConfig(default_connection="work", connections={"work": _gateway_connection()})
        )

        self._run(config, monkeypatch, keys=["enter"])

        config.update_ai_connection.assert_not_called()

        # Re-run, this time accepting after the model comes back.
        async def run():
            app = TitanApp(config, initial_screen=lambda: _BlankScreen())
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("f3")
                await pilot.pause()
                await pilot.press("m")
                await pilot.pause()
                for _ in range(6):
                    await pilot.pause()
                # `home` first: this connection's current model is not one the gateway
                # publishes, so the highlight deliberately starts on "type one" rather
                # than on a model the user never chose.
                await pilot.press("home")
                await pilot.press("enter")
                await pilot.pause()
                app.screen.query_one("#quick-instance-save", Button).press()
                await pilot.pause()

        asyncio.run(run())

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

    def test_with_no_connection_configured_the_picker_says_so(self, monkeypatch):
        from titan_cli.ui.tui.screens.ai_routing import QuickInstanceModal

        _stub_gateway(monkeypatch)
        config = _config(AIConfig())

        captured = self._run(config, monkeypatch)

        assert isinstance(captured["picker"], QuickInstanceModal)
        assert not isinstance(captured["screen"], SelectModelModal)
        assert "No AI connection is configured" in captured["picker_text"]

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


class TestSavedNotice:
    """What the user is told after pinning a model, given which CLI Titan runs."""

    def _notice(self, default_cli, cli_name):
        from titan_cli.ui.tui.screens.model_picker import _saved_notice

        return _saved_notice(_config(AIConfig(default_cli=default_cli)), cli_name, "haiku")

    def test_pinning_on_the_default_cli_just_confirms_it(self):
        assert self._notice("claude", "claude") == "claude will run haiku."

    def test_pinning_on_another_cli_says_which_one_titan_still_runs(self):
        """Otherwise the status bar does not move and the save looks like it failed."""
        notice = self._notice("opencode", "claude")

        assert "claude will run haiku" in notice
        assert "still runs opencode" in notice
        assert "Enter" in notice

    def test_with_no_default_cli_at_all_it_says_so(self):
        assert "no CLI" in self._notice(None, "claude")


class TestTheSavingWrappers:
    """
    The two openers that PERSIST what the picker returns (air-015).

    `open_cli_model_picker` had no test asserting it saves anything — a gap the review
    flagged on 2026-09-16 and the reason the sentinel bug below survived being written.
    Everything else goes through the composing form, which holds its answer instead.
    """

    @staticmethod
    def _pick(opener, model, **kwargs):
        """Run an opener, capture the modal it pushes, and hand it `model`."""
        pushed = {}

        class _App:
            def push_screen(self, screen, callback=None):
                pushed["screen"] = screen
                if callback:
                    callback(model)

            def notify(self, message, severity="information"):
                pushed.setdefault("notices", []).append(message)

        opener(_App(), **kwargs)
        return pushed

    def test_choosing_a_model_pins_it_for_that_cli(self):
        from titan_cli.ui.tui.screens.model_picker import open_cli_model_picker

        config = MagicMock()
        config.get_cli_model.return_value = None
        config.config.ai = AIConfig(default_cli="claude")

        self._pick(open_cli_model_picker, "opus", config=config, cli_name="claude")

        config.set_cli_model.assert_called_once_with("claude", "opus")

    def test_re_choosing_the_same_model_saves_nothing(self):
        from titan_cli.ui.tui.screens.model_picker import open_cli_model_picker

        config = MagicMock()
        config.get_cli_model.return_value = "opus"
        config.config.ai = AIConfig(default_cli="claude")

        self._pick(open_cli_model_picker, "opus", config=config, cli_name="claude")

        config.set_cli_model.assert_not_called()

    def test_cancelling_saves_nothing(self):
        from titan_cli.ui.tui.screens.model_picker import open_cli_model_picker

        config = MagicMock()
        config.get_cli_model.return_value = None
        config.config.ai = AIConfig(default_cli="claude")

        self._pick(open_cli_model_picker, None, config=config, cli_name="claude")

        config.set_cli_model.assert_not_called()

    def test_the_unpin_option_clears_rather_than_saving_the_sentinel(self):
        """
        `DEFAULT_OPTION_ID` is an instruction, not a model identifier.

        This opener was written before the option existed and passes whatever comes back
        straight to `set_cli_model`, which would have pinned the literal `__default__`
        and then handed it to the CLI as `--model __default__`.
        """
        from titan_cli.ui.tui.screens.model_picker import (
            DEFAULT_OPTION_ID,
            open_cli_model_picker,
        )

        config = MagicMock()
        config.get_cli_model.return_value = "opus"
        config.config.ai = AIConfig(default_cli="claude")

        self._pick(open_cli_model_picker, DEFAULT_OPTION_ID, config=config, cli_name="claude")

        config.clear_cli_model.assert_called_once_with("claude")
        config.set_cli_model.assert_not_called()

    def test_a_failed_save_is_reported_and_not_announced_as_success(self):
        from titan_cli.ui.tui.screens.model_picker import open_cli_model_picker

        config = MagicMock()
        config.get_cli_model.return_value = None
        config.config.ai = AIConfig(default_cli="claude")
        config.set_cli_model.side_effect = OSError("disk full")

        pushed = self._pick(
            open_cli_model_picker, "opus", config=config, cli_name="claude"
        )

        assert any("Failed to set the model" in n for n in pushed["notices"])
        assert not any("will run opus" in n for n in pushed["notices"])


class TestTheConnectionSavingWrapper:
    """
    `open_connection_model_picker` is the connection half of the same seam.

    The asking is shared with the task-level path; only the destination differs, so what
    is worth pinning here is the persistence, not the modal.
    """

    @staticmethod
    def _pick(monkeypatch, model, *, current="gpt-5"):
        from titan_cli.ui.tui.screens import model_picker

        config = MagicMock()
        config.config.ai = AIConfig(
            default_connection="work",
            connections={"work": _gateway_connection(model=current)},
        )
        notices = []

        class _App:
            def notify(self, message, severity="information"):
                notices.append(message)

        monkeypatch.setattr(
            model_picker,
            "open_model_picker_for_connection",
            lambda app, cfg, cid, *, on_picked, **kw: on_picked(model),
        )
        model_picker.open_connection_model_picker(_App(), config, "work")
        return config, notices

    def test_choosing_a_model_saves_it_on_the_connection(self, monkeypatch):
        config, _ = self._pick(monkeypatch, "fast-model")

        config.update_ai_connection.assert_called_once_with(
            "work", {"default_model": "fast-model"}
        )

    def test_re_choosing_the_connections_own_model_saves_nothing(self, monkeypatch):
        config, _ = self._pick(monkeypatch, "gpt-5")

        config.update_ai_connection.assert_not_called()

    def test_cancelling_saves_nothing(self, monkeypatch):
        config, _ = self._pick(monkeypatch, None)

        config.update_ai_connection.assert_not_called()

    def test_a_failed_save_is_reported(self, monkeypatch):
        from titan_cli.ui.tui.screens import model_picker

        config = MagicMock()
        config.config.ai = AIConfig(
            default_connection="work", connections={"work": _gateway_connection()}
        )
        config.update_ai_connection.side_effect = OSError("disk full")
        notices = []

        class _App:
            def notify(self, message, severity="information"):
                notices.append(message)

        monkeypatch.setattr(
            model_picker,
            "open_model_picker_for_connection",
            lambda app, cfg, cid, *, on_picked, **kw: on_picked("fast-model"),
        )
        model_picker.open_connection_model_picker(_App(), config, "work")

        assert any("Failed to update model" in n for n in notices)
