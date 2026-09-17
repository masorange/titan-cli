"""
Tests for AIRouteResolver's three-level precedence chain:
runtime override -> persisted task preference -> the step's declared default.

A preference names only a KIND of provider; which connection or CLI serves it comes from the
global defaults, so most of these also assert that the resolved decision names the instance
that will actually run.
"""

import pytest

from titan_cli.ai.router import (
    AIProviderType,
    AIRouteDecision,
    AIRouteNeedsInput,
    AIRoutePolicy,
    AIRouteResolver,
)
from titan_cli.ai.router.availability import AIProviderAvailability
from titan_cli.ai.router.session import AISessionOverride
from titan_cli.core.models import (
    AIConfig,
    AIConnectionConfig,
    AIConnectionType,
    AIGatewayBackend,
    AIPreferences,
    AIProviderPreference,
)


class FakeAvailability:
    """Availability checker stub driven by explicit identifier lists."""

    def __init__(self, remote=(), headless=(), interactive=()):
        self._remote = list(remote)
        self._headless = list(headless)
        self._interactive = list(interactive)

    def available_remote_connections(self):
        return [
            AIProviderAvailability(provider=AIProviderType.REMOTE, identifier=i) for i in self._remote
        ]

    def available_headless_clis(self):
        return [
            AIProviderAvailability(provider=AIProviderType.CLI_HEADLESS, identifier=i)
            for i in self._headless
        ]

    def available_interactive_clis(self):
        return [
            AIProviderAvailability(provider=AIProviderType.CLI_INTERACTIVE, identifier=i)
            for i in self._interactive
        ]

    def is_provider_available(self, provider):
        if provider == AIProviderType.REMOTE:
            return bool(self._remote)
        if provider == AIProviderType.CLI_HEADLESS:
            return bool(self._headless)
        if provider == AIProviderType.CLI_INTERACTIVE:
            return bool(self._interactive)
        if provider == AIProviderType.OFF:
            return True
        return False


def _connection(name: str) -> AIConnectionConfig:
    return AIConnectionConfig(
        name=name,
        connection_type=AIConnectionType.GATEWAY,
        gateway_backend=AIGatewayBackend.OPENAI_COMPATIBLE,
        base_url="https://example.invalid",
    )


def _config(
    *,
    default_connection: str = "work-litellm",
    default_cli: str = "claude",
    **task_preferences,
) -> AIConfig:
    """Build an AIConfig with global defaults and type-only task preferences."""
    return AIConfig(
        default_connection=default_connection,
        default_cli=default_cli,
        connections={default_connection: _connection(default_connection)}
        if default_connection
        else {},
        preferences=AIPreferences(
            tasks={
                task: AIProviderPreference(provider=provider)
                for task, provider in task_preferences.items()
            }
        ),
    )


@pytest.fixture
def availability():
    return FakeAvailability(remote=["work-litellm"], headless=["claude"], interactive=["claude"])


def test_runtime_override_wins_over_persisted_preference(availability):
    resolver = AIRouteResolver(_config(commit_message="remote"), availability)

    decision = resolver.resolve(
        task="commit_message", runtime_override=AIProviderType.CLI_HEADLESS
    )

    assert isinstance(decision, AIRouteDecision)
    assert decision.provider == AIProviderType.CLI_HEADLESS
    assert decision.cli == "claude"


def test_unavailable_runtime_override_needs_input():
    resolver = AIRouteResolver(_config(), FakeAvailability(remote=["work-litellm"]))

    resolution = resolver.resolve(
        task="commit_message", runtime_override=AIProviderType.CLI_HEADLESS
    )

    assert isinstance(resolution, AIRouteNeedsInput)
    assert "claude" in resolution.reason
    assert "not available" in resolution.reason


def test_task_preference_wins_over_declared_default(availability):
    resolver = AIRouteResolver(_config(commit_message="cli_headless"), availability)
    policy = AIRoutePolicy(task="commit_message", preferred=[AIProviderType.REMOTE])

    decision = resolver.resolve(task="commit_message", policy=policy)

    assert isinstance(decision, AIRouteDecision)
    assert decision.provider == AIProviderType.CLI_HEADLESS
    assert decision.cli == "claude"


def test_declared_default_used_when_nothing_persisted(availability):
    resolver = AIRouteResolver(_config(), availability)
    policy = AIRoutePolicy(
        task="commit_message",
        preferred=[AIProviderType.CLI_HEADLESS, AIProviderType.REMOTE],
    )

    decision = resolver.resolve(task="commit_message", policy=policy)

    assert isinstance(decision, AIRouteDecision)
    assert decision.provider == AIProviderType.CLI_HEADLESS
    assert decision.cli == "claude"


def test_declared_default_skips_unavailable_provider_types():
    resolver = AIRouteResolver(_config(), FakeAvailability(remote=["work-litellm"]))
    policy = AIRoutePolicy(
        task="commit_message",
        preferred=[AIProviderType.CLI_HEADLESS, AIProviderType.REMOTE],
    )

    decision = resolver.resolve(task="commit_message", policy=policy)

    assert isinstance(decision, AIRouteDecision)
    assert decision.provider == AIProviderType.REMOTE
    assert decision.connection_id == "work-litellm"


def test_no_preference_and_no_available_default_needs_input(availability):
    resolver = AIRouteResolver(_config(), availability)

    resolution = resolver.resolve(task="commit_message")

    assert isinstance(resolution, AIRouteNeedsInput)
    assert [c.identifier for c in resolution.candidates] == ["work-litellm", "claude", "claude"]


class TestGlobalInstanceResolution:
    """Which connection/CLI runs a task is a single global setting, not part of the preference."""

    def test_configured_default_cli_that_is_gone_never_swaps_to_another(self):
        """The one installed CLI is not silently substituted for the configured one."""
        resolver = AIRouteResolver(
            _config(default_cli="gemini", commit_message="cli_headless"),
            FakeAvailability(headless=["claude"]),
        )

        resolution = resolver.resolve(task="commit_message")

        assert isinstance(resolution, AIRouteNeedsInput)
        assert "gemini" in resolution.reason
        assert "not available" in resolution.reason

    def test_no_default_cli_configured_says_so(self):
        resolver = AIRouteResolver(
            _config(default_cli=None, commit_message="cli_headless"),
            FakeAvailability(headless=["claude"]),
        )

        resolution = resolver.resolve(task="commit_message")

        assert isinstance(resolution, AIRouteNeedsInput)
        assert "no default CLI is configured" in resolution.reason

    def test_no_default_connection_configured_says_so(self):
        resolver = AIRouteResolver(
            _config(default_connection=None, commit_message="remote"),
            FakeAvailability(remote=["work-litellm"]),
        )

        resolution = resolver.resolve(task="commit_message")

        assert isinstance(resolution, AIRouteNeedsInput)
        assert "no default AI connection is configured" in resolution.reason

    def test_changing_the_global_default_changes_every_task_using_that_kind(self):
        """The point of a single global instance: one edit, not one per task."""
        availability = FakeAvailability(headless=["claude", "gemini"])
        config = _config(default_cli="claude", commit_message="cli_headless", slack_summary="cli_headless")
        resolver = AIRouteResolver(config, availability)

        assert resolver.resolve(task="commit_message").cli == "claude"
        assert resolver.resolve(task="slack_summary").cli == "claude"

        config.default_cli = "gemini"

        assert resolver.resolve(task="commit_message").cli == "gemini"
        assert resolver.resolve(task="slack_summary").cli == "gemini"

    def test_a_missing_cli_default_is_reported_even_for_a_declared_default(self):
        """The step-default path reports the real obstacle, not a generic failure."""
        resolver = AIRouteResolver(
            _config(default_cli=None),
            FakeAvailability(interactive=["claude"]),
        )
        policy = AIRoutePolicy(
            task="generic_assistant", preferred=[AIProviderType.CLI_INTERACTIVE]
        )

        resolution = resolver.resolve(task="generic_assistant", policy=policy)

        assert isinstance(resolution, AIRouteNeedsInput)
        assert "no default CLI is configured" in resolution.reason

    def test_first_obstacle_wins_when_every_declared_default_fails(self):
        """With several failing candidates, the reason surfaced is the first one hit."""
        resolver = AIRouteResolver(
            _config(default_cli=None, default_connection=None),
            FakeAvailability(),
        )
        policy = AIRoutePolicy(
            task="generic_assistant",
            preferred=[AIProviderType.CLI_HEADLESS, AIProviderType.REMOTE],
        )

        resolution = resolver.resolve(task="generic_assistant", policy=policy)

        assert isinstance(resolution, AIRouteNeedsInput)
        assert "no default CLI is configured" in resolution.reason
        assert "connection" not in resolution.reason


def test_off_preference_resolves_to_off(availability):
    resolver = AIRouteResolver(_config(commit_message="off"), availability)

    decision = resolver.resolve(task="commit_message")

    assert isinstance(decision, AIRouteDecision)
    assert decision.provider == AIProviderType.OFF


def test_off_needs_no_configured_instance():
    """Turning a task off must work even with nothing else configured."""
    resolver = AIRouteResolver(
        _config(default_connection=None, default_cli=None, commit_message="off"),
        FakeAvailability(),
    )

    decision = resolver.resolve(task="commit_message")

    assert isinstance(decision, AIRouteDecision)
    assert decision.provider == AIProviderType.OFF


def test_unknown_provider_value_is_reported_not_silently_replaced(availability):
    """
    A typo'd or schema-stale stored preference must surface by name instead of
    silently falling through to the step's defaults.
    """
    resolver = AIRouteResolver(_config(commit_message="carrier_pigeon"), availability)
    policy = AIRoutePolicy(task="commit_message", preferred=[AIProviderType.REMOTE])

    decision = resolver.resolve(task="commit_message", policy=policy)

    assert isinstance(decision, AIRouteNeedsInput)
    assert "carrier_pigeon" in decision.reason
    assert "commit_message" in decision.reason


def _pinned_config(
    task: str,
    provider: str,
    *,
    cli=None,
    model=None,
    default_cli: str = "claude",
    cli_models=None,
) -> AIConfig:
    """An AIConfig whose one task preference carries an instance and/or model pin."""
    config = _config(default_cli=default_cli)
    config.cli_models = dict(cli_models or {})
    config.preferences = AIPreferences(
        tasks={task: AIProviderPreference(provider=provider, cli=cli, model=model)}
    )
    return config


class TestPerTaskInstancePin:
    """
    A task may pin the CLI and the model that serve it, as a SPARSE override.

    This reverses ai_execution_service D-017.1, which stored only the provider kind and
    dropped any instance key it found (see ai_task_routing D-001). The reversal is bounded:
    None still means "inherit the global default", so an unpinned task behaves exactly as
    it did before, and a pin is still resolved through availability - never swapped.
    """

    def test_a_pinned_cli_beats_the_global_default(self):
        resolver = AIRouteResolver(
            _pinned_config("commit_message", "cli_headless", cli="gemini", default_cli="claude"),
            FakeAvailability(headless=["claude", "gemini"]),
        )

        decision = resolver.resolve(task="commit_message")

        assert isinstance(decision, AIRouteDecision)
        assert decision.cli == "gemini"

    def test_an_unpinned_task_still_follows_the_global_default(self):
        """The sparse half of D-001: no pin means today's behavior, unchanged."""
        config = _pinned_config(
            "commit_message", "cli_headless", cli="gemini", default_cli="claude"
        )
        config.preferences.tasks["slack_summary"] = AIProviderPreference(provider="cli_headless")
        resolver = AIRouteResolver(
            config, FakeAvailability(headless=["claude", "gemini", "codex"])
        )

        assert resolver.resolve(task="commit_message").cli == "gemini"
        assert resolver.resolve(task="slack_summary").cli == "claude"

        # What F2 does: change the global default. Only the unpinned task moves.
        config.default_cli = "codex"

        assert resolver.resolve(task="commit_message").cli == "gemini"
        assert resolver.resolve(task="slack_summary").cli == "codex"

    def test_a_pinned_cli_that_is_gone_is_reported_by_name_not_swapped(self):
        """D-017's surviving rule: a pin is resolved through availability like any instance."""
        resolver = AIRouteResolver(
            _pinned_config("commit_message", "cli_headless", cli="gemini", default_cli="claude"),
            FakeAvailability(headless=["claude"]),
        )

        resolution = resolver.resolve(task="commit_message")

        assert isinstance(resolution, AIRouteNeedsInput)
        assert "gemini" in resolution.reason
        assert "not available" in resolution.reason

    def test_a_cli_pin_never_redirects_a_remote_task(self):
        """D-004: the connection stays global. A stale cli pin must not leak into it."""
        config = _pinned_config("commit_message", "remote", cli="gemini")
        resolver = AIRouteResolver(config, FakeAvailability(remote=["work-litellm"]))

        decision = resolver.resolve(task="commit_message")

        assert isinstance(decision, AIRouteDecision)
        assert decision.connection_id == "work-litellm"
        assert decision.cli is None

    def test_the_pin_survives_an_interactive_task_too(self):
        resolver = AIRouteResolver(
            _pinned_config("generic_assistant", "cli_interactive", cli="gemini"),
            FakeAvailability(interactive=["claude", "gemini"]),
        )

        decision = resolver.resolve(task="generic_assistant")

        assert isinstance(decision, AIRouteDecision)
        assert decision.cli == "gemini"


class TestPerTaskModelPin:
    """
    The decision names the model that will run, so the log and the on-screen chip can too.

    Precedence inside the resolver (ai_task_routing D-002, lower rungs only - the call-site
    model= and the session override are the executor's business): task pin > cli_models.
    """

    def test_the_decision_carries_the_pinned_model(self):
        resolver = AIRouteResolver(
            _pinned_config("commit_message", "cli_headless", model="haiku-fast"),
            FakeAvailability(headless=["claude"]),
        )

        decision = resolver.resolve(task="commit_message")

        assert isinstance(decision, AIRouteDecision)
        assert decision.cli == "claude"
        assert decision.model == "haiku-fast"

    def test_the_task_pin_beats_the_global_model_for_that_cli(self):
        resolver = AIRouteResolver(
            _pinned_config(
                "commit_message",
                "cli_headless",
                model="haiku-fast",
                cli_models={"claude": "opus-slow"},
            ),
            FakeAvailability(headless=["claude"]),
        )

        assert resolver.resolve(task="commit_message").model == "haiku-fast"

    def test_without_a_pin_the_decision_carries_the_global_model(self):
        resolver = AIRouteResolver(
            _pinned_config("commit_message", "cli_headless", cli_models={"claude": "opus-slow"}),
            FakeAvailability(headless=["claude"]),
        )

        assert resolver.resolve(task="commit_message").model == "opus-slow"

    def test_the_global_model_follows_the_pinned_cli_not_the_default_cli(self):
        """A CLI pin changes which cli_models entry applies - they are keyed by CLI."""
        resolver = AIRouteResolver(
            _pinned_config(
                "commit_message",
                "cli_headless",
                cli="gemini",
                default_cli="claude",
                cli_models={"claude": "opus-slow", "gemini": "flash"},
            ),
            FakeAvailability(headless=["claude", "gemini"]),
        )

        decision = resolver.resolve(task="commit_message")

        assert decision.cli == "gemini"
        assert decision.model == "flash"

    def test_nothing_pinned_anywhere_leaves_the_model_unset(self):
        """None still means 'let the CLI pick', which is what it meant before."""
        resolver = AIRouteResolver(
            _pinned_config("commit_message", "cli_headless"),
            FakeAvailability(headless=["claude"]),
        )

        assert resolver.resolve(task="commit_message").model is None

    def test_a_model_pin_reaches_a_remote_decision_too(self):
        """
        Written the other way round first, under D-004's asymmetry, and corrected by D-006.

        A model pin is not CLI vocabulary: "run this task on a small model" means the same
        thing whichever transport answers it, and the only difference is where the
        instance's own default lives.
        """
        config = _pinned_config("commit_message", "remote", model="gpt-5-mini")
        resolver = AIRouteResolver(config, FakeAvailability(remote=["work-litellm"]))

        decision = resolver.resolve(task="commit_message")

        assert decision.connection_id == "work-litellm"
        assert decision.model == "gpt-5-mini"


def test_leftover_workflow_scope_in_config_has_no_effect(availability):
    """
    A config written before the workflow scope was removed must resolve exactly
    as if that section were absent - the task is the only scope.
    """
    preferences = AIPreferences.model_validate(
        {
            "tasks": {},
            "workflows": {
                "Commit with AI, Linter and Tests": {
                    "provider": "cli_headless",
                    "cli": "gemini",
                }
            },
        }
    )
    assert not hasattr(preferences, "workflows")

    config = _config()
    config.preferences = preferences
    resolver = AIRouteResolver(config, availability)
    policy = AIRoutePolicy(task="commit_message", preferred=[AIProviderType.REMOTE])

    decision = resolver.resolve(task="commit_message", policy=policy)

    assert isinstance(decision, AIRouteDecision)
    assert decision.provider == AIProviderType.REMOTE


def test_persisted_preference_outside_executes_is_refused(availability):
    """
    A preference the step's code can't run must be refused by name, not handed
    over to fail later and further from the cause.
    """
    resolver = AIRouteResolver(_config(generic_assistant="remote"), availability)
    policy = AIRoutePolicy(
        task="generic_assistant",
        executes=[AIProviderType.CLI_INTERACTIVE],
        preferred=[AIProviderType.CLI_INTERACTIVE],
    )

    resolution = resolver.resolve(task="generic_assistant", policy=policy)

    assert isinstance(resolution, AIRouteNeedsInput)
    assert "cannot run" in resolution.reason


def test_runtime_override_outside_executes_is_refused(availability):
    """
    A runtime override comes from a caller that never consulted `executes`,
    so it gets the same guard as a persisted preference: refused by name
    rather than handed to a step that can't drive it.
    """
    resolver = AIRouteResolver(_config(), availability)
    policy = AIRoutePolicy(
        task="generic_assistant",
        executes=[AIProviderType.CLI_INTERACTIVE],
        preferred=[AIProviderType.CLI_INTERACTIVE],
    )

    resolution = resolver.resolve(
        task="generic_assistant",
        policy=policy,
        runtime_override=AIProviderType.REMOTE,
    )

    assert isinstance(resolution, AIRouteNeedsInput)
    assert "cannot run" in resolution.reason
    assert "requested" in resolution.reason


def test_off_preference_passes_the_executes_guard(availability):
    """Any step can skip - 'off' is honored regardless of executes."""
    resolver = AIRouteResolver(_config(generic_assistant="off"), availability)
    policy = AIRoutePolicy(
        task="generic_assistant", executes=[AIProviderType.CLI_INTERACTIVE]
    )

    decision = resolver.resolve(task="generic_assistant", policy=policy)

    assert isinstance(decision, AIRouteDecision)
    assert decision.provider == AIProviderType.OFF


def test_preference_within_executes_passes_the_guard(availability):
    resolver = AIRouteResolver(_config(commit_message="cli_headless"), availability)
    policy = AIRoutePolicy(
        task="commit_message",
        executes=[AIProviderType.REMOTE, AIProviderType.CLI_HEADLESS],
        preferred=[AIProviderType.REMOTE],
    )

    decision = resolver.resolve(task="commit_message", policy=policy)

    assert isinstance(decision, AIRouteDecision)
    assert decision.cli == "claude"


def test_no_declared_executes_means_no_guard(availability):
    """Steps that declare nothing keep the old behavior - no filtering."""
    resolver = AIRouteResolver(_config(thread_resolution="remote"), availability)

    decision = resolver.resolve(task="thread_resolution")

    assert isinstance(decision, AIRouteDecision)
    assert decision.provider == AIProviderType.REMOTE


def test_missing_ai_config_needs_input():
    resolver = AIRouteResolver(None, FakeAvailability())

    resolution = resolver.resolve(task="commit_message")

    assert isinstance(resolution, AIRouteNeedsInput)
    assert resolution.candidates == []


class TestSessionOverride:
    """
    What the user chose with F2/F3 for this session only (ai_task_routing D-003).

    It sits above a task's pin and the global default, and below an explicit call-site
    model= (which the executor applies). It overrides INSTANCES, never kinds.
    """

    def test_the_session_cli_beats_a_task_pin(self):
        resolver = AIRouteResolver(
            _pinned_config("commit_message", "cli_headless", cli="gemini"),
            FakeAvailability(headless=["claude", "gemini", "codex"]),
            session_override=AISessionOverride(cli="codex"),
        )

        assert resolver.resolve(task="commit_message").cli == "codex"

    def test_the_session_cli_beats_the_global_default(self):
        resolver = AIRouteResolver(
            _pinned_config("commit_message", "cli_headless", default_cli="claude"),
            FakeAvailability(headless=["claude", "codex"]),
            session_override=AISessionOverride(cli="codex"),
        )

        assert resolver.resolve(task="commit_message").cli == "codex"

    def test_the_session_model_beats_a_task_pin(self):
        resolver = AIRouteResolver(
            _pinned_config(
                "commit_message",
                "cli_headless",
                model="haiku-fast",
                cli_models={"claude": "opus-slow"},
            ),
            FakeAvailability(headless=["claude"]),
            session_override=AISessionOverride(model="sonnet-now"),
        )

        assert resolver.resolve(task="commit_message").model == "sonnet-now"

    def test_an_inactive_override_changes_nothing(self):
        """An empty override must be indistinguishable from having none at all."""
        config = _pinned_config("commit_message", "cli_headless", cli="gemini", model="flash")
        availability = FakeAvailability(headless=["claude", "gemini"])

        without = AIRouteResolver(config, availability).resolve(task="commit_message")
        with_empty = AIRouteResolver(
            config, availability, session_override=AISessionOverride()
        ).resolve(task="commit_message")

        assert (without.cli, without.model) == (with_empty.cli, with_empty.model)

    def test_a_session_cli_that_is_gone_is_reported_by_name(self):
        """Overriding is still choosing an instance, so the no-silent-swap rule applies."""
        resolver = AIRouteResolver(
            _pinned_config("commit_message", "cli_headless"),
            FakeAvailability(headless=["claude"]),
            session_override=AISessionOverride(cli="codex"),
        )

        resolution = resolver.resolve(task="commit_message")

        assert isinstance(resolution, AIRouteNeedsInput)
        assert "codex" in resolution.reason
        assert "not available" in resolution.reason

    def test_a_session_cli_never_redirects_a_remote_task(self):
        """It overrides instances, not kinds: a remote task stays on its connection."""
        config = _pinned_config("commit_message", "remote")
        resolver = AIRouteResolver(
            config,
            FakeAvailability(remote=["work-litellm"]),
            session_override=AISessionOverride(cli="codex"),
        )

        decision = resolver.resolve(task="commit_message")

        assert isinstance(decision, AIRouteDecision)
        assert decision.provider == AIProviderType.REMOTE
        assert decision.connection_id == "work-litellm"

    def test_a_session_override_turns_an_off_task_on_for_nobody(self):
        """Off is a kind, and kinds are not what this overrides."""
        resolver = AIRouteResolver(
            _pinned_config("commit_message", "off"),
            FakeAvailability(headless=["claude", "codex"]),
            session_override=AISessionOverride(cli="codex"),
        )

        assert resolver.resolve(task="commit_message").provider == AIProviderType.OFF


class TestPerTaskRemotePin:
    """
    A remote task pins its connection and model the same way a CLI task pins its CLI.

    The two halves were asymmetric in the first cut of this domain (D-004 kept connections
    global); D-006 made them symmetric because the shapes are the same - an instance, and
    a model belonging to that instance.
    """

    @staticmethod
    def _remote_config(task, *, connection=None, model=None, default_connection="work-litellm"):
        config = _config(default_connection=default_connection)
        config.connections["other-litellm"] = _connection("other-litellm")
        config.preferences = AIPreferences(
            tasks={task: AIProviderPreference(provider="remote", connection=connection, model=model)}
        )
        return config

    def test_a_pinned_connection_beats_the_global_default(self):
        resolver = AIRouteResolver(
            self._remote_config("jira_analysis", connection="other-litellm"),
            FakeAvailability(remote=["work-litellm", "other-litellm"]),
        )

        decision = resolver.resolve(task="jira_analysis")

        assert isinstance(decision, AIRouteDecision)
        assert decision.connection_id == "other-litellm"

    def test_a_pinned_connection_that_is_gone_is_reported_by_name(self):
        resolver = AIRouteResolver(
            self._remote_config("jira_analysis", connection="other-litellm"),
            FakeAvailability(remote=["work-litellm"]),
        )

        resolution = resolver.resolve(task="jira_analysis")

        assert isinstance(resolution, AIRouteNeedsInput)
        assert "other-litellm" in resolution.reason
        assert "not available" in resolution.reason

    def test_a_pinned_model_rides_on_a_remote_decision_too(self):
        resolver = AIRouteResolver(
            self._remote_config("jira_analysis", model="gpt-5-mini"),
            FakeAvailability(remote=["work-litellm"]),
        )

        assert resolver.resolve(task="jira_analysis").model == "gpt-5-mini"

    def test_without_a_pin_the_connections_own_model_is_named(self):
        """The global rung for remote is the connection's default_model, by symmetry
        with cli_models being the global rung for a CLI."""
        config = self._remote_config("jira_analysis")
        config.connections["work-litellm"].default_model = "gpt-5"
        resolver = AIRouteResolver(config, FakeAvailability(remote=["work-litellm"]))

        assert resolver.resolve(task="jira_analysis").model == "gpt-5"

    def test_the_model_follows_the_pinned_connection_not_the_default_one(self):
        config = self._remote_config("jira_analysis", connection="other-litellm")
        config.connections["work-litellm"].default_model = "gpt-5"
        config.connections["other-litellm"].default_model = "claude-sonnet"
        resolver = AIRouteResolver(
            config, FakeAvailability(remote=["work-litellm", "other-litellm"])
        )

        decision = resolver.resolve(task="jira_analysis")

        assert (decision.connection_id, decision.model) == ("other-litellm", "claude-sonnet")

    def test_a_connection_pin_never_redirects_a_cli_task(self):
        config = _config(default_cli="claude")
        config.preferences = AIPreferences(
            tasks={
                "commit_message": AIProviderPreference(
                    provider="cli_headless", connection="other-litellm"
                )
            }
        )
        resolver = AIRouteResolver(config, FakeAvailability(headless=["claude"]))

        assert resolver.resolve(task="commit_message").cli == "claude"


class TestSessionOverrideForRemote:
    """F3's half of the session override: same rungs, same rules as F2's (D-006)."""

    @staticmethod
    def _config_with_two_connections(task="jira_analysis"):
        config = _config()
        config.connections["other-litellm"] = _connection("other-litellm")
        config.connections["work-litellm"].default_model = "gpt-5"
        config.connections["other-litellm"].default_model = "claude-sonnet"
        config.preferences = AIPreferences(
            tasks={task: AIProviderPreference(provider="remote")}
        )
        return config

    def test_the_session_connection_beats_the_global_default(self):
        resolver = AIRouteResolver(
            self._config_with_two_connections(),
            FakeAvailability(remote=["work-litellm", "other-litellm"]),
            session_override=AISessionOverride(connection="other-litellm"),
        )

        assert resolver.resolve(task="jira_analysis").connection_id == "other-litellm"

    def test_the_session_connection_beats_a_task_pin(self):
        config = self._config_with_two_connections()
        config.preferences.tasks["jira_analysis"].connection = "work-litellm"
        resolver = AIRouteResolver(
            config,
            FakeAvailability(remote=["work-litellm", "other-litellm"]),
            session_override=AISessionOverride(connection="other-litellm"),
        )

        assert resolver.resolve(task="jira_analysis").connection_id == "other-litellm"

    def test_the_session_model_applies_to_a_remote_task(self):
        resolver = AIRouteResolver(
            self._config_with_two_connections(),
            FakeAvailability(remote=["work-litellm"]),
            session_override=AISessionOverride(model="gpt-5-mini"),
        )

        assert resolver.resolve(task="jira_analysis").model == "gpt-5-mini"

    def test_a_session_connection_that_is_gone_is_reported_by_name(self):
        resolver = AIRouteResolver(
            self._config_with_two_connections(),
            FakeAvailability(remote=["work-litellm"]),
            session_override=AISessionOverride(connection="other-litellm"),
        )

        resolution = resolver.resolve(task="jira_analysis")

        assert isinstance(resolution, AIRouteNeedsInput)
        assert "other-litellm" in resolution.reason


class TestAModelNeverOutlivesItsInstance:
    """
    Found in use 2026-09-17: a task pinned to claude+opus was switched to codex and kept
    `opus`, so the run would have been `codex -m opus`.

    The CRUD is what forgets the model (`TitanConfig._drop_stale_model`); these cover the
    session override's half of the same rule.
    """

    def test_switching_the_session_cli_forgets_the_model(self):
        override = AISessionOverride(cli="claude", model="opus")

        dropped = override.use_cli("codex")

        assert dropped == "opus"
        assert (override.cli, override.model) == ("codex", None)

    def test_reselecting_the_same_cli_keeps_the_model(self):
        override = AISessionOverride(cli="claude", model="opus")

        assert override.use_cli("claude") is None
        assert override.model == "opus"

    def test_switching_the_session_connection_forgets_the_model(self):
        override = AISessionOverride(connection="work", model="gpt-5")

        dropped = override.use_connection("personal")

        assert dropped == "gpt-5"
        assert (override.connection, override.model) == ("personal", None)

    def test_the_resolver_never_sees_a_model_from_another_instance(self):
        """End to end: the decision names codex and no model, not codex and opus."""
        override = AISessionOverride(cli="claude", model="opus")
        override.use_cli("codex")
        resolver = AIRouteResolver(
            _pinned_config("commit_message", "cli_headless"),
            FakeAvailability(headless=["claude", "codex"]),
            session_override=override,
        )

        decision = resolver.resolve(task="commit_message")

        assert (decision.cli, decision.model) == ("codex", None)
