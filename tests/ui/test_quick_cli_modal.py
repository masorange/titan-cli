"""
The quick picker behind F2 and F3.

One component serves both keys - F2 loads it with CLIs, F3 with remote connections - so
most of what matters here is asserted for BOTH, parameterized over the key. That is not
thoroughness for its own sake: the two used to be near-copies, and the whole point of
merging them is that a change to one cannot quietly miss the other.

It is a form: choosing a row marks a pending selection and writes nothing. Nothing is
persisted until Save, `S` applies the same composition for the session only, and Cancel
leaves everything - the model included - untouched.
"""

import asyncio
from unittest.mock import MagicMock

import pytest
from textual.screen import Screen
from textual.widgets import Static

from titan_cli.ai.router.availability import AIProviderAvailability
from titan_cli.ai.router.enums import AIProviderType
from titan_cli.core.models import AIConfig, AIConnectionConfig
from titan_cli.ui.tui.app import TitanApp
from titan_cli.ui.tui.screens.ai_routing import QuickInstanceModal
from titan_cli.ui.tui.widgets import Button, StyledOptionList


class _BlankScreen(Screen):
    def compose(self):
        yield Static("blank")


def _gateway(name, model):
    return AIConnectionConfig(
        name=name,
        connection_type="gateway",
        gateway_backend="openai_compatible",
        base_url="https://gateway.example/v1",
        default_model=model,
    )


def _config(*, default_cli="claude", cli_models=None, default_connection="work"):
    config = MagicMock()
    config.config.ai = AIConfig(
        default_cli=default_cli,
        cli_models=cli_models or {},
        default_connection=default_connection,
        connections={"work": _gateway("Work", "gpt-5"), "personal": _gateway("Personal", "mini")},
    )
    config.get_project_name.return_value = "test-project"
    config.get_cli_model.side_effect = lambda cli: (cli_models or {}).get(cli)
    return config


def _stub_availability(monkeypatch, clis=("claude", "opencode")):
    class _Checker:
        def __init__(self, *args, **kwargs):
            pass

        def available_headless_clis(self):
            return [
                AIProviderAvailability(provider=AIProviderType.CLI_HEADLESS, identifier=n)
                for n in clis
            ]

        def available_interactive_clis(self):
            return [
                AIProviderAvailability(provider=AIProviderType.CLI_INTERACTIVE, identifier=n)
                for n in clis
            ]

    monkeypatch.setattr("titan_cli.ai.router.availability.AIAvailabilityChecker", _Checker)
    monkeypatch.setattr(
        "titan_cli.core.security.create_broker_factory", lambda root: MagicMock()
    )


def _run(config, monkeypatch, key, keys=(), *, press_button=None, before=None):
    """Open the picker with `key`, press `keys`, optionally click a button."""
    _stub_availability(monkeypatch)
    captured = {}

    async def run():
        app = TitanApp(config, initial_screen=lambda: _BlankScreen())
        async with app.run_test() as pilot:
            await pilot.pause()
            if before:
                before(app)
            await pilot.press(key)
            await pilot.pause()
            captured["opened"] = isinstance(app.screen, QuickInstanceModal)
            for k in keys:
                await pilot.press(k)
                await pilot.pause()
            if press_button and isinstance(app.screen, QuickInstanceModal):
                app.screen.query_one(f"#{press_button}", Button).press()
                await pilot.pause()
            captured["screen"] = app.screen
            captured["override"] = (
                app.ai_session_override.cli,
                app.ai_session_override.cli_model,
                app.ai_session_override.connection,
                app.ai_session_override.connection_model,
            )

    asyncio.run(run())
    return captured


# The two keys, and what each one is expected to write when accepted.
# Which half of the session override each key owns.
OVERRIDE_FIELDS = [
    pytest.param("f2", "cli", "opencode", id="f2-cli"),
    pytest.param("f3", "connection", "personal", id="f3-connection"),
]


def _picker_text(config, monkeypatch, key, *, before=None) -> str:
    """Open a picker and return everything it renders as text."""
    _stub_availability(monkeypatch)
    captured = {}

    async def run():
        app = TitanApp(config, initial_screen=lambda: _BlankScreen())
        async with app.run_test() as pilot:
            await pilot.pause()
            if before:
                setattr(app.ai_session_override, before[0], before[1])
            await pilot.press(key)
            await pilot.pause()
            captured["text"] = " ".join(
                str(w.renderable) for w in app.screen.query(Static)
            )

    asyncio.run(run())
    return captured["text"]


BOTH_KEYS = [
    pytest.param("f2", "set_default_ai_cli", "opencode", id="f2-cli"),
    pytest.param("f3", "set_default_ai_connection", "personal", id="f3-connection"),
]


class TestNothingIsWrittenUntilYouAccept:
    @pytest.mark.parametrize("key,writer,expected", BOTH_KEYS)
    def test_choosing_a_row_marks_it_without_saving(self, key, writer, expected, monkeypatch):
        config = _config()

        captured = _run(config, monkeypatch, key, keys=["down", "enter"])

        assert captured["opened"]
        assert isinstance(captured["screen"], QuickInstanceModal)  # still open
        getattr(config, writer).assert_not_called()

    @pytest.mark.parametrize("key,writer,expected", BOTH_KEYS)
    def test_accepting_writes_the_marked_choice(self, key, writer, expected, monkeypatch):
        config = _config()

        _run(
            config, monkeypatch, key, keys=["down", "enter"],
            press_button="quick-instance-save",
        )

        getattr(config, writer).assert_called_once_with(expected)

    @pytest.mark.parametrize("key,writer,expected", BOTH_KEYS)
    def test_cancelling_writes_nothing(self, key, writer, expected, monkeypatch):
        config = _config()

        _run(
            config, monkeypatch, key, keys=["down", "enter"],
            press_button="quick-instance-cancel",
        )

        getattr(config, writer).assert_not_called()

    @pytest.mark.parametrize("key,writer,expected", BOTH_KEYS)
    def test_escape_writes_nothing(self, key, writer, expected, monkeypatch):
        config = _config()

        _run(config, monkeypatch, key, keys=["down", "enter", "escape"])

        getattr(config, writer).assert_not_called()

    @pytest.mark.parametrize("key,writer,expected", BOTH_KEYS)
    def test_accepting_without_choosing_anything_writes_nothing(
        self, key, writer, expected, monkeypatch
    ):
        """The pending selection starts at what is in force, so Save is a real no-op."""
        config = _config()

        _run(config, monkeypatch, key, press_button="quick-instance-save")

        getattr(config, writer).assert_not_called()


class TestTheSessionScope:
    @pytest.mark.parametrize("key,writer,expected", BOTH_KEYS)
    def test_s_applies_without_writing(self, key, writer, expected, monkeypatch):
        config = _config()

        captured = _run(config, monkeypatch, key, keys=["down", "enter", "s"])

        getattr(config, writer).assert_not_called()
        assert expected in captured["override"]

    @pytest.mark.parametrize("key,field,value", OVERRIDE_FIELDS)
    def test_c_clears_this_kinds_override(self, key, field, value, monkeypatch):
        config = _config()

        captured = _run(
            config,
            monkeypatch,
            key,
            keys=["c"],
            before=lambda app: setattr(app.ai_session_override, field, value),
        )

        assert captured["override"] == (None, None, None, None)

    @pytest.mark.parametrize("key,field,value", OVERRIDE_FIELDS)
    def test_an_active_override_of_this_kind_is_announced(
        self, key, field, value, monkeypatch
    ):
        text = _picker_text(_config(), monkeypatch, key, before=(field, value))

        assert "Session override active" in text
        assert value in text


class TestEachKeyMindsItsOwnOverride:
    """
    Found in use 2026-09-18: the connection picker announced "Session override active:
    codex / gpt-5.6-luna" - a CLI override - and offered to clear it.

    The two halves are set by different keys and shown in different status-bar cells, so
    naming one from the other's picker reports something the user cannot act on from
    where they are standing, and clearing it removes a setting they cannot even see.
    """

    def test_f3_ignores_a_cli_override(self, monkeypatch):
        text = _picker_text(_config(), monkeypatch, "f3", before=("cli", "opencode"))

        assert "Session override active" not in text

    def test_f2_ignores_a_connection_override(self, monkeypatch):
        text = _picker_text(_config(), monkeypatch, "f2", before=("connection", "personal"))

        assert "Session override active" not in text

    def test_clearing_from_one_picker_leaves_the_other_kind_alone(self, monkeypatch):
        """C in the CLI picker must not silently drop the connection override."""
        config = _config()
        _stub_availability(monkeypatch)
        captured = {}

        async def run():
            app = TitanApp(config, initial_screen=lambda: _BlankScreen())
            async with app.run_test() as pilot:
                await pilot.pause()
                app.ai_session_override.cli = "opencode"
                app.ai_session_override.connection = "personal"
                await pilot.press("f2")
                await pilot.pause()
                await pilot.press("c")
                await pilot.pause()
                override = app.ai_session_override
                captured["state"] = (override.cli, override.connection)

        asyncio.run(run())

        assert captured["state"] == (None, "personal")


class TestTheHintAndTheDisclosure:
    @pytest.mark.parametrize("key,writer,expected", BOTH_KEYS)
    def test_the_hint_explains_the_keys(self, key, writer, expected, monkeypatch):
        """It used to be clipped by a fixed max-height exactly when there was most to say."""
        _stub_availability(monkeypatch)
        captured = {}

        async def run():
            app = TitanApp(_config(), initial_screen=lambda: _BlankScreen())
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press(key)
                await pilot.pause()
                captured["text"] = " ".join(
                    str(w.renderable) for w in app.screen.query(Static)
                )

        asyncio.run(run())

        assert "S for this session only" in captured["text"]
        assert "Nothing is saved until you accept" in captured["text"]

    def test_pinned_tasks_are_named_without_claiming_s_skips_them(self, monkeypatch):
        """
        A session override outranks a pin (D-008), so "will not change" was a lie.

        This line exists to stop the key looking broken; saying the wrong thing in it is
        worse than saying nothing.
        """
        from titan_cli.core.models import AIPreferences, AIProviderPreference

        config = _config()
        config.config.ai.preferences = AIPreferences(
            tasks={
                "code_review_plan": AIProviderPreference(provider="cli_headless", cli="codex")
            }
        )
        _stub_availability(monkeypatch)
        captured = {}

        async def run():
            app = TitanApp(config, initial_screen=lambda: _BlankScreen())
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("f2")
                await pilot.pause()
                captured["text"] = " ".join(
                    str(w.renderable) for w in app.screen.query(Static)
                )

        asyncio.run(run())

        assert "will not follow a save" in captured["text"]
        assert "S still applies to them" in captured["text"]


class TestComposingAModel:
    def test_m_opens_the_model_picker_and_comes_back(self, monkeypatch):
        """It used to close everything and save; the model is now part of the composition."""
        from titan_cli.ui.tui.screens.model_picker import SelectModelModal

        config = _config()
        _stub_availability(monkeypatch)
        captured = {}

        async def run():
            app = TitanApp(config, initial_screen=lambda: _BlankScreen())
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("f2")
                await pilot.pause()
                await pilot.press("m")
                await pilot.pause()
                captured["picker"] = isinstance(app.screen, SelectModelModal)
                app.screen.dismiss("haiku")
                await pilot.pause()
                captured["back"] = isinstance(app.screen, QuickInstanceModal)
                captured["pending"] = app.screen.pending_model
                captured["saved_yet"] = config.set_cli_model.called

        asyncio.run(run())

        assert captured["picker"]
        assert captured["back"]
        assert captured["pending"] == "haiku"
        assert captured["saved_yet"] is False

    def test_the_model_is_written_only_on_accept(self, monkeypatch):
        config = _config()
        _stub_availability(monkeypatch)

        async def run():
            app = TitanApp(config, initial_screen=lambda: _BlankScreen())
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("f2")
                await pilot.pause()
                await pilot.press("m")
                await pilot.pause()
                app.screen.dismiss("haiku")
                await pilot.pause()
                app.screen.query_one("#quick-instance-save", Button).press()
                await pilot.pause()

        asyncio.run(run())

        config.set_cli_model.assert_called_once_with("claude", "haiku")

    def test_choosing_another_instance_forgets_the_pending_model(self, monkeypatch):
        """A model belongs to the instance it was chosen for (D-007)."""
        config = _config()
        _stub_availability(monkeypatch)
        captured = {}

        async def run():
            app = TitanApp(config, initial_screen=lambda: _BlankScreen())
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("f2")
                await pilot.pause()
                await pilot.press("m")
                await pilot.pause()
                app.screen.dismiss("haiku")
                await pilot.pause()
                app.screen.query_one(StyledOptionList).focus()
                await pilot.press("down")
                await pilot.press("enter")
                await pilot.pause()
                captured["pending_model"] = app.screen.pending_model
                captured["touched"] = app.screen.model_touched

        asyncio.run(run())

        assert captured["pending_model"] is None
        assert captured["touched"] is False

    def test_a_session_model_is_finally_expressible(self, monkeypatch):
        """
        `AISessionOverride.cli_model` had no way in before this: `M` saved globally and
        closed, so the resolver read a field nothing could write.
        """
        config = _config()
        _stub_availability(monkeypatch)
        captured = {}

        async def run():
            app = TitanApp(config, initial_screen=lambda: _BlankScreen())
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("f2")
                await pilot.pause()
                await pilot.press("m")
                await pilot.pause()
                app.screen.dismiss("haiku")
                await pilot.pause()
                app.screen.query_one("#quick-instance-session", Button).press()
                await pilot.pause()
                captured["override"] = (
                    app.ai_session_override.cli,
                    app.ai_session_override.cli_model,
                )

        asyncio.run(run())

        assert captured["override"] == ("claude", "haiku")
        config.set_cli_model.assert_not_called()


class TestComposingBothForTheSession:
    """
    The whole point of the form, in one flow: pick an instance, pick its model, then
    choose the scope — and have the scope apply to BOTH.

    Before the form this was impossible in one pass: `M` saved the model globally and
    closed the picker, so "run codex on haiku, just for today" required two visits and
    left a permanent write behind.
    """

    @staticmethod
    def _compose(config, monkeypatch, *, final_key):
        _stub_availability(monkeypatch)
        captured = {}

        async def run():
            app = TitanApp(config, initial_screen=lambda: _BlankScreen())
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("f2")
                await pilot.pause()
                await pilot.press("down")      # highlight the other CLI
                await pilot.press("enter")     # mark it; focus moves to Save
                await pilot.pause()
                await pilot.press("m")         # ask for its model
                await pilot.pause()
                app.screen.dismiss("haiku")    # the picker hands it back
                await pilot.pause()
                await pilot.press(final_key)   # choose the scope
                await pilot.pause()
                override = app.ai_session_override
                captured["override"] = (override.cli, override.cli_model)
                captured["closed"] = not isinstance(app.screen, QuickInstanceModal)

        asyncio.run(run())
        return captured

    def test_s_applies_the_instance_and_its_model_together(self, monkeypatch):
        config = _config()

        captured = self._compose(config, monkeypatch, final_key="s")

        assert captured["override"] == ("opencode", "haiku")
        assert captured["closed"]
        config.set_default_ai_cli.assert_not_called()
        config.set_cli_model.assert_not_called()

    def test_the_keyboard_path_still_reaches_save(self, monkeypatch):
        """`m` and `s` must keep working once focus has moved off the list to Save."""
        config = _config()

        captured = self._compose(config, monkeypatch, final_key="enter")

        assert captured["closed"]
        config.set_default_ai_cli.assert_called_once_with("opencode")
        config.set_cli_model.assert_called_once_with("opencode", "haiku")
        assert captured["override"] == (None, None)


class TestThePendingLineStatesTheScope:
    """
    "Will apply: X / Y" reads the same whether it is about to be written to disk or held
    until the app closes. The two accepts are labelled on the buttons, but the line above
    them is where the eye goes, so it says which is which.
    """

    @staticmethod
    def _pending_text(config, monkeypatch, keys):
        _stub_availability(monkeypatch)
        captured = {}

        async def run():
            app = TitanApp(config, initial_screen=lambda: _BlankScreen())
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("f2")
                await pilot.pause()
                for k in keys:
                    await pilot.press(k)
                    await pilot.pause()
                captured["text"] = str(
                    app.screen.query_one("#quick-instance-pending", Static).renderable
                )

        asyncio.run(run())
        return captured["text"]

    def test_with_nothing_changed_it_states_what_is_in_force(self, monkeypatch):
        text = self._pending_text(_config(cli_models={"claude": "haiku"}), monkeypatch, [])

        assert "Currently: claude / haiku" in text
        # No scope wording when there is nothing to accept.
        assert "S for this session" not in text

    def test_a_pending_change_names_both_scopes(self, monkeypatch):
        text = self._pending_text(_config(), monkeypatch, ["down", "enter"])

        assert "Will apply: opencode" in text
        assert "Save to keep it" in text
        assert "S for this session only" in text


class TestThePendingModelBelongsToThePendingInstance:
    """
    Found in use 2026-09-18: marking codex still read "Will apply: codex / haiku".

    `haiku` was claude's pinned model, and the line was resolving it from the CURRENT
    instance instead of the marked one. Same class of mistake the routing layer removed in
    D-007 and D-008 - a model shown against an instance it was never chosen for - only
    here it misleads before anything is written rather than after.
    """

    @staticmethod
    def _pending_after(keys, monkeypatch, cli_models):
        _stub_availability(monkeypatch)
        captured = {}

        async def run():
            app = TitanApp(
                _config(cli_models=cli_models), initial_screen=lambda: _BlankScreen()
            )
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("f2")
                await pilot.pause()
                for k in keys:
                    await pilot.press(k)
                    await pilot.pause()
                captured["text"] = str(
                    app.screen.query_one("#quick-instance-pending", Static).renderable
                )

        asyncio.run(run())
        return captured["text"]

    def test_marking_another_instance_drops_the_previous_ones_model(self, monkeypatch):
        text = self._pending_after(
            ["down", "enter"], monkeypatch, {"claude": "haiku"}
        )

        assert "opencode" in text
        assert "haiku" not in text

    def test_it_shows_the_marked_instances_own_model(self, monkeypatch):
        text = self._pending_after(
            ["down", "enter"], monkeypatch, {"claude": "haiku", "opencode": "qwen"}
        )

        assert "opencode / qwen" in text

    def test_an_instance_with_no_model_says_it_runs_its_own_default(self, monkeypatch):
        text = self._pending_after(["down", "enter"], monkeypatch, {"claude": "haiku"})

        assert "opencode / CLI default" in text

    def test_the_model_picker_prefills_from_the_marked_instance(self, monkeypatch):
        """`M` after marking codex must offer codex's model, not claude's."""

        _stub_availability(monkeypatch)
        captured = {}

        async def run():
            app = TitanApp(
                _config(cli_models={"claude": "haiku", "opencode": "qwen"}),
                initial_screen=lambda: _BlankScreen(),
            )
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("f2")
                await pilot.pause()
                await pilot.press("down")
                await pilot.press("enter")
                await pilot.pause()
                await pilot.press("m")
                await pilot.pause()
                captured["current"] = app.screen.current

        asyncio.run(run())

        assert captured["current"] == "qwen"


class TestRefreshingTheListKeepsEveryRowItself:
    """
    Found in use 2026-09-18: after marking a row, a later row rendered another CLI's text.

    The id underneath stayed right - hovering reported the real one - so only the painted
    prompt was wrong, which is the worst shape for this bug: the list lies and nothing
    downstream disagrees.
    """

    def test_every_row_still_carries_its_own_title_after_a_selection(self, monkeypatch):
        """
        Data-level only, and that is worth stating: the ids and prompts were ALREADY
        right while the screen showed otherwise, so this cannot see the paint bug. It
        guards the neighbouring regression - a rebuild that reorders or drops rows - and
        the paint itself is handled by not rebuilding at all.
        """
        _stub_availability(monkeypatch, clis=("claude", "gemini", "codex", "opencode", "agy"))
        captured = {}

        async def run():
            app = TitanApp(_config(), initial_screen=lambda: _BlankScreen())
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("f2")
                await pilot.pause()
                await pilot.press("down")
                await pilot.press("down")
                await pilot.press("enter")     # mark codex; repaints the list
                await pilot.pause()
                option_list = app.screen.query_one(StyledOptionList)
                captured["rows"] = [
                    (
                        option_list.get_option_at_index(i).id,
                        str(option_list.get_option_at_index(i).prompt),
                    )
                    for i in range(option_list.option_count)
                ]

        asyncio.run(run())

        for identifier, prompt in captured["rows"]:
            assert f"command: {identifier}" in prompt, (
                f"row {identifier!r} is painted with another row's text: {prompt!r}"
            )
