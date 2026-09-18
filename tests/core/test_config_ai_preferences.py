# tests/core/test_config_ai_preferences.py
"""Persistence of AI routing preferences (one provider choice per AI task)."""

from pathlib import Path

import pytest
import tomli
import tomli_w

from titan_cli.core.config import TitanConfig
from titan_cli.core.models import AIConfig


@pytest.fixture
def config(tmp_path: Path, monkeypatch, mocker) -> TitanConfig:
    """A TitanConfig backed by a throwaway global config file."""
    mocker.patch("titan_cli.core.config.PluginRegistry")

    global_config_path = tmp_path / ".titan" / "config.toml"
    global_config_path.parent.mkdir(parents=True)
    with open(global_config_path, "wb") as f:
        tomli_w.dump({"config_version": "1.0"}, f)

    monkeypatch.setattr(TitanConfig, "GLOBAL_CONFIG", global_config_path)
    monkeypatch.chdir(tmp_path)
    return TitanConfig()


def _written_preferences(config: TitanConfig) -> dict:
    with open(TitanConfig.GLOBAL_CONFIG, "rb") as f:
        return tomli.load(f).get("ai", {}).get("preferences", {})


def test_task_preference_roundtrips_to_disk(config: TitanConfig):
    config.upsert_task_ai_preference("commit_message", {"provider": "cli_headless"})

    written = _written_preferences(config)
    assert written["tasks"]["commit_message"] == {"provider": "cli_headless"}


def test_a_task_preference_stores_nothing_it_was_not_given(config: TitanConfig):
    """
    A preference is sparse: the provider kind alone, unless the user pinned an instance.

    This used to assert that the provider kind was the ONLY thing storable (D-017.1). It
    now asserts the weaker, still important thing - nothing is written that the caller did
    not ask for - because a task may pin its own CLI and model (D-001), but an unpinned
    task must keep inheriting the global defaults rather than freezing a copy of them.
    """
    config.upsert_task_ai_preference("commit_message", {"provider": "cli_headless"})

    stored = _written_preferences(config)["tasks"]["commit_message"]
    assert set(stored) == {"provider"}


def test_task_preference_is_visible_in_memory_without_reloading(config: TitanConfig):
    """
    TitanConfig lives for the whole session, so a write must also update the
    parsed model - a step resolving a route right after must see the new value.
    """
    config.upsert_task_ai_preference("commit_message", {"provider": "off"})

    assert config.config.ai.preferences.tasks["commit_message"].provider == "off"


def test_deleting_a_task_preference_removes_it(config: TitanConfig):
    config.upsert_task_ai_preference("commit_message", {"provider": "remote"})

    config.delete_task_ai_preference("commit_message")

    assert _written_preferences(config)["tasks"] == {}
    assert config.config.ai.preferences.tasks == {}


def test_deleting_an_absent_task_preference_is_a_no_op(config: TitanConfig):
    config.delete_task_ai_preference("never_configured")

    assert _written_preferences(config).get("tasks", {}) == {}


def test_preferences_survive_a_full_reload(config: TitanConfig):
    config.upsert_task_ai_preference("pr_description", {"provider": "remote"})

    reloaded = TitanConfig()

    preference = reloaded.config.ai.preferences.tasks["pr_description"]
    assert preference.provider == "remote"


def test_default_cli_roundtrips_and_can_be_cleared(config: TitanConfig):
    config.set_default_ai_cli("claude")

    reloaded = TitanConfig()
    assert reloaded.config.ai.default_cli == "claude"

    config.clear_default_ai_cli()

    assert TitanConfig().config.ai.default_cli is None


def test_setting_a_default_cli_works_without_any_ai_connection(config: TitanConfig):
    """A CLI-only setup has no default connection, which TOML cannot store as a null."""
    config.set_default_ai_cli("claude")

    with open(TitanConfig.GLOBAL_CONFIG, "rb") as f:
        ai_section = tomli.load(f)["ai"]

    assert ai_section["default_cli"] == "claude"
    assert "default_connection" not in ai_section


def test_only_task_scope_is_persisted(config: TitanConfig):
    """The task is the only preference scope - nothing else is written."""
    config.upsert_task_ai_preference("commit_message", {"provider": "remote"})

    assert set(_written_preferences(config).keys()) == {"tasks"}


def test_a_cli_model_roundtrips_and_can_be_cleared(config: TitanConfig):
    config.set_cli_model("claude", "opus")

    reloaded = TitanConfig()
    assert reloaded.config.ai.cli_models == {"claude": "opus"}
    assert reloaded.get_cli_model("claude") == "opus"

    config.clear_cli_model("claude")

    assert TitanConfig().get_cli_model("claude") is None


def test_each_cli_keeps_its_own_model(config: TitanConfig):
    """An identifier only means something to the CLI that accepts it."""
    config.set_cli_model("claude", "opus")
    config.set_cli_model("opencode", "anthropic/claude-sonnet-5")

    assert TitanConfig().config.ai.cli_models == {
        "claude": "opus",
        "opencode": "anthropic/claude-sonnet-5",
    }


def test_a_new_cli_model_is_visible_without_reloading(config: TitanConfig):
    """The next workflow step routes off the in-memory config, not off disk."""
    config.set_cli_model("claude", "opus")

    assert config.config.ai.cli_models["claude"] == "opus"
    assert config.get_cli_model("claude") == "opus"


def test_an_unpinned_cli_has_no_model(config: TitanConfig):
    config.set_cli_model("claude", "opus")

    assert config.get_cli_model("gemini") is None


class TestPerTaskPins:
    """
    Setting and clearing the per-task CLI and model pins (ai_task_routing air-002).

    The rule that shapes all of it: a clear DELETES its key. TOML has no null, and this
    saver (unlike the connections one) does not filter Nones, so a pin cleared by writing
    None makes tomli_w raise TypeError - verified, not assumed. Deleting the key is the
    only shape that means "inherit again".
    """

    def test_pinning_a_cli_keeps_the_provider_kind(self, config: TitanConfig):
        config.upsert_task_ai_preference("commit_message", {"provider": "cli_headless"})

        config.set_task_ai_cli("commit_message", "gemini")

        stored = _written_preferences(config)["tasks"]["commit_message"]
        assert stored == {"provider": "cli_headless", "cli": "gemini"}

    def test_pinning_a_model_keeps_the_cli_pin(self, config: TitanConfig):
        """Each setter touches one key; they are set independently and must not clobber."""
        config.upsert_task_ai_preference("commit_message", {"provider": "cli_headless"})
        config.set_task_ai_cli("commit_message", "gemini")

        config.set_task_ai_model("commit_message", "flash")

        stored = _written_preferences(config)["tasks"]["commit_message"]
        assert stored == {"provider": "cli_headless", "cli": "gemini", "model": "flash"}

    def test_clearing_a_pin_removes_the_key_rather_than_emptying_it(self, config: TitanConfig):
        """
        The model goes with it - see TestChangingTheInstanceInvalidatesTheModel.

        This test originally asserted `model: flash` survived. It does not: `flash` was
        chosen for gemini, and clearing the CLI pin sends the task back to whatever the
        global default is.
        """
        config.upsert_task_ai_preference("commit_message", {"provider": "cli_headless"})
        config.set_task_ai_cli("commit_message", "gemini")
        config.set_task_ai_model("commit_message", "flash")

        config.clear_task_ai_cli("commit_message")

        stored = _written_preferences(config)["tasks"]["commit_message"]
        assert "cli" not in stored
        assert stored == {"provider": "cli_headless"}

    def test_a_cleared_pin_stays_cleared_after_a_reload(self, config: TitanConfig):
        """The failure this guards: a dropped None reading back as the old value."""
        config.upsert_task_ai_preference("commit_message", {"provider": "cli_headless"})
        config.set_task_ai_cli("commit_message", "gemini")
        config.clear_task_ai_cli("commit_message")

        config.load()

        assert config.config.ai.preferences.tasks["commit_message"].cli is None

    def test_clearing_a_pin_that_was_never_set_is_a_no_op(self, config: TitanConfig):
        config.upsert_task_ai_preference("commit_message", {"provider": "cli_headless"})

        config.clear_task_ai_model("commit_message")
        config.clear_task_ai_cli("unknown_task")

        assert _written_preferences(config)["tasks"]["commit_message"] == {
            "provider": "cli_headless"
        }

    def test_pinning_a_task_with_no_preference_needs_a_provider(self, config: TitanConfig):
        """A pin cannot exist on its own: the preference it lives in requires a kind."""
        with pytest.raises(ValueError) as excinfo:
            config.set_task_ai_cli("commit_message", "gemini")

        assert "commit_message" in str(excinfo.value)
        assert "no stored preference" in str(excinfo.value)

    def test_pinning_creates_the_preference_when_given_a_provider(self, config: TitanConfig):
        config.set_task_ai_cli("commit_message", "gemini", provider="cli_headless")

        assert _written_preferences(config)["tasks"]["commit_message"] == {
            "provider": "cli_headless",
            "cli": "gemini",
        }

    def test_an_existing_preference_keeps_its_own_kind(self, config: TitanConfig):
        """`provider=` is a creation argument, not a way to change the kind sideways."""
        config.upsert_task_ai_preference("commit_message", {"provider": "cli_interactive"})

        config.set_task_ai_cli("commit_message", "gemini", provider="cli_headless")

        assert _written_preferences(config)["tasks"]["commit_message"]["provider"] == (
            "cli_interactive"
        )

    def test_a_pin_is_visible_in_memory_without_reloading(self, config: TitanConfig):
        """A step resolving a route right after the screen wrote it must see the pin."""
        config.upsert_task_ai_preference("commit_message", {"provider": "cli_headless"})

        config.set_task_ai_cli("commit_message", "gemini")
        config.set_task_ai_model("commit_message", "flash")

        pinned = config.config.ai.preferences.tasks["commit_message"]
        assert (pinned.cli, pinned.model) == ("gemini", "flash")

    def test_pins_are_independent_between_tasks(self, config: TitanConfig):
        config.set_task_ai_cli("commit_message", "gemini", provider="cli_headless")
        config.set_task_ai_cli("code_review_findings", "claude", provider="cli_headless")

        tasks = _written_preferences(config)["tasks"]
        assert tasks["commit_message"]["cli"] == "gemini"
        assert tasks["code_review_findings"]["cli"] == "claude"

    def test_deleting_the_preference_takes_its_pins_with_it(self, config: TitanConfig):
        config.set_task_ai_cli("commit_message", "gemini", provider="cli_headless")

        config.delete_task_ai_preference("commit_message")

        assert "commit_message" not in _written_preferences(config)["tasks"]

    def test_get_task_ai_preference_reads_what_was_written(self, config: TitanConfig):
        config.set_task_ai_model("commit_message", "flash", provider="cli_headless")

        assert config.get_task_ai_preference("commit_message") == {
            "provider": "cli_headless",
            "model": "flash",
        }
        assert config.get_task_ai_preference("never_configured") is None


class TestChangingTheInstanceInvalidatesTheModel:
    """
    A pinned model belongs to the instance it was chosen for (found in use, 2026-09-17).

    The user pinned claude + opus on a task, then switched the task to codex, and `opus`
    stayed - so Titan would have run `codex -m opus`, an identifier codex has never heard
    of. The global layer never had this bug because `cli_models` is keyed BY CLI; a task's
    pin stores a bare model with no instance attached, so changing the instance has to
    invalidate it.
    """

    def test_switching_the_pinned_cli_drops_the_model(self, config: TitanConfig):
        config.upsert_task_ai_preference("code_review_plan", {"provider": "cli_headless"})
        config.set_task_ai_cli("code_review_plan", "claude")
        config.set_task_ai_model("code_review_plan", "opus")

        config.set_task_ai_cli("code_review_plan", "codex")

        stored = _written_preferences(config)["tasks"]["code_review_plan"]
        assert stored == {"provider": "cli_headless", "cli": "codex"}

    def test_repinning_the_same_cli_keeps_the_model(self, config: TitanConfig):
        """Only a CHANGE invalidates it - re-saving the same choice is not a change."""
        config.upsert_task_ai_preference("code_review_plan", {"provider": "cli_headless"})
        config.set_task_ai_cli("code_review_plan", "claude")
        config.set_task_ai_model("code_review_plan", "opus")

        config.set_task_ai_cli("code_review_plan", "claude")

        assert _written_preferences(config)["tasks"]["code_review_plan"]["model"] == "opus"

    def test_clearing_the_cli_pin_drops_the_model_too(self, config: TitanConfig):
        """Following the global default again is also a change of instance."""
        config.upsert_task_ai_preference("code_review_plan", {"provider": "cli_headless"})
        config.set_task_ai_cli("code_review_plan", "claude")
        config.set_task_ai_model("code_review_plan", "opus")

        config.clear_task_ai_cli("code_review_plan")

        assert _written_preferences(config)["tasks"]["code_review_plan"] == {
            "provider": "cli_headless"
        }

    def test_switching_the_pinned_connection_drops_the_model(self, config: TitanConfig):
        config.upsert_task_ai_preference("jira_analysis", {"provider": "remote"})
        config.set_task_ai_connection("jira_analysis", "work")
        config.set_task_ai_model("jira_analysis", "gpt-5")

        config.set_task_ai_connection("jira_analysis", "personal")

        stored = _written_preferences(config)["tasks"]["jira_analysis"]
        assert stored == {"provider": "remote", "connection": "personal"}

    def test_the_setter_reports_whether_it_dropped_a_model(self, config: TitanConfig):
        """The UI has to be able to say so; a model vanishing in silence is its own bug."""
        config.upsert_task_ai_preference("code_review_plan", {"provider": "cli_headless"})
        config.set_task_ai_cli("code_review_plan", "claude")
        config.set_task_ai_model("code_review_plan", "opus")

        assert config.set_task_ai_cli("code_review_plan", "codex") == "opus"
        assert config.set_task_ai_cli("code_review_plan", "gemini") is None


class TestClearPathsKeepTheLiveConfigInSync:
    """
    Clearing must update the in-memory model too, not only the file (review, 2026-09-18).

    The existing clear tests re-read through a fresh `TitanConfig()`, so they pass whether
    or not the clear path syncs. `TitanConfig` lives for the whole session: if the sync
    were dropped, a step resolving a route right after would keep using the stale pin and
    nothing would fail.
    """

    def test_clearing_a_cli_model_is_visible_without_a_reload(self, config: TitanConfig):
        config.set_cli_model("claude", "opus")

        config.clear_cli_model("claude")

        assert config.get_cli_model("claude") is None            # same instance
        assert TitanConfig().get_cli_model("claude") is None      # and on disk

    def test_clearing_the_default_cli_is_visible_without_a_reload(self, config: TitanConfig):
        config.set_default_ai_cli("claude")

        config.clear_default_ai_cli()

        assert config.config.ai.default_cli is None
        assert TitanConfig().config.ai.default_cli is None

    def test_clearing_one_clis_model_leaves_the_others(self, config: TitanConfig):
        """The regression this guards would silently unpin every CLI at once."""
        config.set_cli_model("claude", "opus")
        config.set_cli_model("opencode", "anthropic/claude-sonnet-5")

        config.clear_cli_model("claude")

        assert TitanConfig().config.ai.cli_models == {
            "opencode": "anthropic/claude-sonnet-5"
        }

    def test_replacing_a_model_pin_drops_nothing_and_reports_nothing(
        self, config: TitanConfig
    ):
        """
        Only an INSTANCE change invalidates a model, so replacing one reports nothing.

        This test used to be called "reports what it dropped" while asserting `is None`
        — which is what the setter returns unconditionally, since `"model"` is not in
        `_INSTANCE_PIN_KEYS`. It passed whether or not any reporting existed and
        documented a guarantee the code does not make.
        """
        config.set_task_ai_cli("commit_message", "claude", provider="cli_headless")
        config.set_task_ai_model("commit_message", "opus")

        assert config.set_task_ai_model("commit_message", "haiku") is None
        assert _written_preferences(config)["tasks"]["commit_message"]["model"] == "haiku"

    def test_clearing_an_instance_pin_reports_the_model_it_invalidated(
        self, config: TitanConfig
    ):
        """The clear path has the same contract as the set path, and no test had it."""
        config.set_task_ai_cli("code_review_plan", "claude", provider="cli_headless")
        config.set_task_ai_model("code_review_plan", "opus")

        assert config.clear_task_ai_cli("code_review_plan") == "opus"


class TestChangingTheKindKeepsWhatStillMakesSense:
    """
    `[Change]` used to replace the whole preference, dropping cli/connection/model with
    no notice — even when the user re-picked the kind it already had (review, 2026-09-18).

    What survives follows from D-010: an instance pin belongs to its transport and is
    simply inert while another kind is in effect, but a MODEL belongs to whichever
    instance serves the task, so a change of transport invalidates it.
    """

    def test_re_picking_the_same_kind_changes_nothing(self, config: TitanConfig):
        config.set_task_ai_cli("commit_message", "gemini", provider="cli_headless")
        config.set_task_ai_model("commit_message", "flash")

        dropped = config.set_task_ai_provider("commit_message", "cli_headless")

        assert dropped is None
        assert _written_preferences(config)["tasks"]["commit_message"] == {
            "provider": "cli_headless",
            "cli": "gemini",
            "model": "flash",
        }

    def test_moving_between_the_two_cli_kinds_keeps_the_cli_and_its_model(
        self, config: TitanConfig
    ):
        """Same binary, invoked differently - `claude` vs `claude -p`."""
        config.set_task_ai_cli("generic_assistant", "gemini", provider="cli_headless")
        config.set_task_ai_model("generic_assistant", "flash")

        dropped = config.set_task_ai_provider("generic_assistant", "cli_interactive")

        assert dropped is None
        assert _written_preferences(config)["tasks"]["generic_assistant"] == {
            "provider": "cli_interactive",
            "cli": "gemini",
            "model": "flash",
        }

    def test_switching_transport_drops_the_model_and_says_so(self, config: TitanConfig):
        config.set_task_ai_cli("jira_analysis", "gemini", provider="cli_headless")
        config.set_task_ai_model("jira_analysis", "flash")

        dropped = config.set_task_ai_provider("jira_analysis", "remote")

        assert dropped == "flash"
        assert _written_preferences(config)["tasks"]["jira_analysis"] == {
            "provider": "remote",
            "cli": "gemini",
        }

    def test_the_other_transports_pin_survives_to_be_used_again(self, config: TitanConfig):
        """An inert pin is not a wrong one: switch back and it is still there."""
        config.set_task_ai_cli("jira_analysis", "gemini", provider="cli_headless")
        config.set_task_ai_provider("jira_analysis", "remote")

        config.set_task_ai_provider("jira_analysis", "cli_headless")

        assert _written_preferences(config)["tasks"]["jira_analysis"]["cli"] == "gemini"

    def test_a_task_with_no_preference_gets_one(self, config: TitanConfig):
        config.set_task_ai_provider("commit_message", "off")

        assert _written_preferences(config)["tasks"]["commit_message"] == {"provider": "off"}


class TestAHandEditedConfigDoesNotCrashThePicker:
    """
    `~/.titan/config.toml` is editable by hand, so every level has to be checked.

    A string where a table was expected used to raise AttributeError out of
    `setdefault`, surfacing as a crash in the model picker rather than as a config
    problem.
    """

    @staticmethod
    def _write(raw: dict):
        with open(TitanConfig.GLOBAL_CONFIG, "wb") as f:
            tomli_w.dump(raw, f)

    def test_a_non_table_ai_section_is_normalized(self, config: TitanConfig):
        self._write({"config_version": "1.0", "ai": "broken"})

        assert config.get_ai_preferences_config() == {"tasks": {}}

    def test_a_non_table_preferences_section_is_normalized(self, config: TitanConfig):
        self._write({"config_version": "1.0", "ai": {"preferences": ["nope"]}})

        assert config.get_ai_preferences_config() == {"tasks": {}}

    def test_a_non_table_tasks_section_is_normalized(self, config: TitanConfig):
        self._write({"config_version": "1.0", "ai": {"preferences": {"tasks": "nope"}}})

        assert config.get_ai_preferences_config()["tasks"] == {}

    def test_writing_still_works_afterwards(self, config: TitanConfig):
        self._write({"config_version": "1.0", "ai": {"preferences": "broken"}})

        config.upsert_task_ai_preference("commit_message", {"provider": "off"})

        assert _written_preferences(config)["tasks"]["commit_message"] == {"provider": "off"}


class TestAProjectOverrideIsNotTrampled:
    """
    The in-memory sync must not write a global value over a project's own (review).

    `self.config` is the merged model and `_merge_configs` lets a project's `[ai]` table
    win, so copying a freshly-saved GLOBAL value onto it made the session use the global
    one and silently revert on the next `load()` — the same staleness class as
    `ai-exec-019`, visible to nobody until a workflow ran with the wrong CLI.
    """

    def test_a_project_default_cli_survives_a_global_save(self, config: TitanConfig):
        config.project_config = {"ai": {"default_cli": "opencode"}}
        config.config.ai = AIConfig(default_cli="opencode")

        config.set_default_ai_cli("claude")

        assert config.config.ai.default_cli == "opencode"          # session unchanged
        assert TitanConfig().config.ai.default_cli == "claude"      # global written

    def test_a_project_cli_models_table_survives_a_global_save(self, config: TitanConfig):
        config.project_config = {"ai": {"cli_models": {"claude": "sonnet"}}}
        config.config.ai = AIConfig(cli_models={"claude": "sonnet"})

        config.set_cli_model("claude", "opus")

        assert config.config.ai.cli_models == {"claude": "sonnet"}
        assert TitanConfig().get_cli_model("claude") == "opus"

    def test_without_a_project_override_the_session_still_updates(self, config: TitanConfig):
        config.project_config = {}

        config.set_default_ai_cli("claude")

        assert config.config.ai.default_cli == "claude"
