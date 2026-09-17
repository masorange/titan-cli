"""
Tests for the F2 quick default-CLI picker.

Mounts the real app, presses the real keys. Synchronous wrappers around asyncio.run,
matching the repo's other screen-mount tests.
"""

import asyncio
from unittest.mock import MagicMock

from textual.screen import Screen
from textual.widgets import Static

from titan_cli.ai.router.availability import AIProviderAvailability
from titan_cli.ai.router.enums import AIProviderType
from titan_cli.core.models import AIConfig
from titan_cli.ui.tui.app import TitanApp
from titan_cli.ui.tui.screens.ai_routing import QuickCliModal
from titan_cli.ui.tui.widgets import StyledOptionList


class _BlankScreen(Screen):
    def compose(self):
        yield Static("blank")


def _config(default_cli=None, cli_models=None):
    config = MagicMock()
    config.config.ai = AIConfig(default_cli=default_cli, cli_models=cli_models or {})
    config.get_project_name.return_value = "test-project"
    config.get_cli_model.side_effect = lambda cli: (cli_models or {}).get(cli)
    return config


def _stub_availability(monkeypatch, clis):
    class _Checker:
        def __init__(self, *args, **kwargs):
            pass

        def available_headless_clis(self):
            return [
                AIProviderAvailability(provider=AIProviderType.CLI_HEADLESS, identifier=name)
                for name in clis
            ]

        def available_interactive_clis(self):
            return [
                AIProviderAvailability(
                    provider=AIProviderType.CLI_INTERACTIVE, identifier=name
                )
                for name in clis
            ]

    monkeypatch.setattr("titan_cli.ai.router.availability.AIAvailabilityChecker", _Checker)
    monkeypatch.setattr(
        "titan_cli.core.security.create_broker_factory",
        lambda root: MagicMock(),
    )


class TestQuickCliModal:

    def _run(self, config, monkeypatch, keys, *, clis=("claude", "opencode")):
        _stub_availability(monkeypatch, clis)
        captured = {}

        async def run():
            app = TitanApp(config, initial_screen=lambda: _BlankScreen())
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("f2")
                await pilot.pause()
                captured["opened"] = isinstance(app.screen, QuickCliModal)
                if captured["opened"]:
                    captured["listed"] = list(app.screen.installed)
                    option_list = app.screen.query_one(StyledOptionList)
                    captured["highlighted"] = option_list.highlighted
                for key in keys:
                    await pilot.press(key)
                    await pilot.pause()
                captured["closed"] = not isinstance(app.screen, QuickCliModal)

        asyncio.run(run())
        return captured

    def test_f2_opens_the_picker_listing_installed_clis(self, monkeypatch):
        captured = self._run(_config(), monkeypatch, keys=["escape"])

        assert captured["opened"]
        assert captured["listed"] == ["claude", "opencode"]

    def test_the_saved_default_starts_highlighted(self, monkeypatch):
        captured = self._run(_config(default_cli="opencode"), monkeypatch, keys=["escape"])

        assert captured["highlighted"] == 1

    def test_selecting_a_cli_saves_it_and_closes(self, monkeypatch):
        config = _config(default_cli="claude")
        captured = self._run(config, monkeypatch, keys=["down", "enter"])

        assert captured["closed"]
        config.set_default_ai_cli.assert_called_once_with("opencode")

    def test_escape_closes_without_saving(self, monkeypatch):
        config = _config(default_cli="claude")
        captured = self._run(config, monkeypatch, keys=["escape"])

        assert captured["closed"]
        config.set_default_ai_cli.assert_not_called()

    def test_reselecting_the_current_default_saves_nothing(self, monkeypatch):
        config = _config(default_cli="claude")
        captured = self._run(config, monkeypatch, keys=["enter"])

        assert captured["closed"]
        config.set_default_ai_cli.assert_not_called()


class TestQuickCliModalModels:
    """The picker also says, and lets you change, which model each CLI runs."""

    def test_each_row_names_the_model_that_cli_will_run(self, monkeypatch):
        _stub_availability(monkeypatch, ("claude", "opencode"))
        captured = {}

        async def run():
            app = TitanApp(
                _config(default_cli="claude", cli_models={"claude": "opus"}),
                initial_screen=lambda: _BlankScreen(),
            )
            async with app.run_test() as pilot:
                await pilot.press("f2")
                await pilot.pause()
                option_list = app.screen.query_one(StyledOptionList)
                captured["prompts"] = [
                    str(option_list.get_option_at_index(i).prompt) for i in range(2)
                ]

        asyncio.run(run())

        assert "model: opus" in captured["prompts"][0]
        # An unpinned CLI says so rather than leaving a blank that reads as "unknown".
        assert "model: CLI default" in captured["prompts"][1]

    def test_m_opens_the_model_picker_for_the_highlighted_cli(self, monkeypatch):
        from titan_cli.ui.tui.screens.model_picker import SelectModelModal

        _stub_availability(monkeypatch, ("claude", "opencode"))
        config = _config(default_cli="claude")
        captured = {}

        async def run():
            app = TitanApp(config, initial_screen=lambda: _BlankScreen())
            async with app.run_test() as pilot:
                await pilot.press("f2")
                await pilot.pause()
                await pilot.press("down")
                await pilot.press("m")
                await pilot.pause()
                captured["screen"] = app.screen
                captured["subtitle"] = getattr(app.screen, "subtitle", None)

        asyncio.run(run())

        assert isinstance(captured["screen"], SelectModelModal)
        assert "opencode" in captured["subtitle"]
        # Choosing a model for a CLI is not switching to it.
        config.set_default_ai_cli.assert_not_called()


class TestSessionOverrideFromF2:
    """
    F2 can also choose a CLI for this session only, writing nothing (air-004, D-003).

    The distinction these pin down is the one the feature exists for: Enter changes what
    the user decided, S changes only what is running right now.
    """

    def _run(self, config, monkeypatch, keys, *, clis=("claude", "opencode")):
        _stub_availability(monkeypatch, clis)
        captured = {}

        async def run():
            app = TitanApp(config, initial_screen=lambda: _BlankScreen())
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("f2")
                await pilot.pause()
                for key in keys:
                    await pilot.press(key)
                    await pilot.pause()
                captured["override"] = (
                    app.ai_session_override.cli,
                    app.ai_session_override.model,
                )
                captured["active"] = app.ai_session_override.is_active

        asyncio.run(run())
        return captured

    def test_s_sets_the_session_cli_without_saving_anything(self, monkeypatch):
        config = _config(default_cli="claude")

        captured = self._run(config, monkeypatch, keys=["down", "s"])

        assert captured["override"] == ("opencode", None)
        config.set_default_ai_cli.assert_not_called()

    def test_enter_still_saves_and_leaves_the_session_alone(self, monkeypatch):
        config = _config(default_cli="claude")

        captured = self._run(config, monkeypatch, keys=["down", "enter"])

        assert captured["active"] is False
        config.set_default_ai_cli.assert_called_once_with("opencode")

    def test_c_clears_an_active_override(self, monkeypatch):
        config = _config(default_cli="claude")
        _stub_availability(monkeypatch, ("claude", "opencode"))
        captured = {}

        async def run():
            app = TitanApp(config, initial_screen=lambda: _BlankScreen())
            async with app.run_test() as pilot:
                await pilot.pause()
                app.ai_session_override.cli = "opencode"
                await pilot.press("f2")
                await pilot.pause()
                await pilot.press("c")
                await pilot.pause()
                captured["active"] = app.ai_session_override.is_active

        asyncio.run(run())

        assert captured["active"] is False

    def test_the_picker_says_an_override_is_active(self, monkeypatch):
        """An override nobody can see is one the user forgets is on."""
        _stub_availability(monkeypatch, ("claude", "opencode"))
        captured = {}

        async def run():
            app = TitanApp(_config(default_cli="claude"), initial_screen=lambda: _BlankScreen())
            async with app.run_test() as pilot:
                await pilot.pause()
                app.ai_session_override.cli = "opencode"
                await pilot.press("f2")
                await pilot.pause()
                captured["text"] = " ".join(
                    str(w.renderable) for w in app.screen.query(Static)
                )

        asyncio.run(run())

        assert "Session override active" in captured["text"]
        assert "opencode" in captured["text"]


class TestQuickConnectionModal:
    """
    F3's picker, which mirrors F2's (D-006): Enter saves, S is this session, C clears.

    Two keys answering the same question of different transports should not have to be
    learned twice, so what these assert is mostly that the behaviours match.
    """

    @staticmethod
    def _config_with_connections(default_connection="work"):
        from titan_cli.core.models import AIConnectionConfig

        def gateway(name, model):
            return AIConnectionConfig(
                name=name,
                connection_type="gateway",
                gateway_backend="openai_compatible",
                base_url="https://gateway.example/v1",
                default_model=model,
            )

        config = MagicMock()
        config.config.ai = AIConfig(
            default_connection=default_connection,
            connections={"work": gateway("Work", "gpt-5"), "personal": gateway("Personal", "mini")},
        )
        config.get_project_name.return_value = "test-project"
        return config

    def _run(self, config, keys):
        captured = {}

        async def run():
            app = TitanApp(config, initial_screen=lambda: _BlankScreen())
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("f3")
                await pilot.pause()
                for key in keys:
                    await pilot.press(key)
                    await pilot.pause()
                captured["override"] = (
                    app.ai_session_override.connection,
                    app.ai_session_override.model,
                )

        asyncio.run(run())
        return captured

    def test_s_sets_the_session_connection_without_saving(self):
        config = self._config_with_connections()

        captured = self._run(config, keys=["down", "s"])

        assert captured["override"] == ("personal", None)
        config.set_default_ai_connection.assert_not_called()

    def test_enter_saves_the_default_connection(self):
        config = self._config_with_connections()

        captured = self._run(config, keys=["down", "enter"])

        assert captured["override"] == (None, None)
        config.set_default_ai_connection.assert_called_once_with("personal")

    def test_reselecting_the_current_default_saves_nothing(self):
        config = self._config_with_connections()

        self._run(config, keys=["enter"])

        config.set_default_ai_connection.assert_not_called()

    def test_c_clears_a_session_override_set_from_either_key(self):
        """One override, two keys: F3 must be able to clear what F2 set."""
        config = self._config_with_connections()
        captured = {}

        async def run():
            app = TitanApp(config, initial_screen=lambda: _BlankScreen())
            async with app.run_test() as pilot:
                await pilot.pause()
                app.ai_session_override.cli = "codex"
                await pilot.press("f3")
                await pilot.pause()
                await pilot.press("c")
                await pilot.pause()
                captured["active"] = app.ai_session_override.is_active

        asyncio.run(run())

        assert captured["active"] is False


class TestPinnedTasksAreDisclosed:
    """
    A quick picker says which tasks will ignore it (air-005).

    Without this, the failure mode per-task pins introduce is indistinguishable from a
    broken key: you press F2, the CLI changes, and the workflow you actually care about
    keeps running the old one because you pinned it weeks ago.
    """

    @staticmethod
    def _config_with_pins(**tasks):
        from titan_cli.core.models import AIPreferences, AIProviderPreference

        config = _config(default_cli="claude")
        config.config.ai.preferences = AIPreferences(
            tasks={
                task: AIProviderPreference(**fields) for task, fields in tasks.items()
            }
        )
        return config

    @staticmethod
    def _text_after(key, config):
        captured = {}

        async def run():
            app = TitanApp(config, initial_screen=lambda: _BlankScreen())
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press(key)
                await pilot.pause()
                captured["text"] = " ".join(
                    str(w.renderable) for w in app.screen.query(Static)
                )

        asyncio.run(run())
        return captured["text"]

    def test_f2_names_the_tasks_that_pin_their_own_cli(self, monkeypatch):
        _stub_availability(monkeypatch, ("claude", "opencode"))
        config = self._config_with_pins(
            code_review_plan={"provider": "cli_headless", "cli": "codex"},
            commit_message={"provider": "cli_headless"},
        )

        text = self._text_after("f2", config)

        assert "1 task" in text
        assert "Code review plan" in text
        # The unpinned one follows F2, so naming it would be a lie.
        assert "Commit messages" not in text

    def test_f2_says_nothing_when_no_task_pins_a_cli(self, monkeypatch):
        _stub_availability(monkeypatch, ("claude", "opencode"))
        config = self._config_with_pins(
            commit_message={"provider": "cli_headless"},
        )

        text = self._text_after("f2", config)

        assert "pin their own" not in text

    def test_f2_ignores_connection_pins(self, monkeypatch):
        """Each key reports only the pins it is actually unable to move."""
        _stub_availability(monkeypatch, ("claude", "opencode"))
        config = self._config_with_pins(
            jira_analysis={"provider": "remote", "connection": "personal"},
        )

        text = self._text_after("f2", config)

        assert "pin their own" not in text

    def test_f3_names_the_tasks_that_pin_their_own_connection(self, monkeypatch):
        from titan_cli.core.models import AIConnectionConfig

        config = self._config_with_pins(
            jira_analysis={"provider": "remote", "connection": "personal"},
        )
        config.config.ai.default_connection = "work"
        config.config.ai.connections = {
            "work": AIConnectionConfig(
                name="Work",
                connection_type="gateway",
                gateway_backend="openai_compatible",
                base_url="https://gateway.example/v1",
                default_model="gpt-5",
            )
        }

        text = self._text_after("f3", config)

        assert "1 task" in text
        assert "Jira issue analysis" in text
