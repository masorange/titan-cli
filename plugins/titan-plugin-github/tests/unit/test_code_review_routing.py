"""
Routing tests for the code-review steps.

These steps run a headless CLI themselves (their own timeouts, structured output,
tool restrictions and batching), so they resolve WHO runs them through the façade
and keep their own execution. What is pinned here is that resolution: the user's
per-task preference decides the CLI, and every way it can fail comes back with a
reason instead of a silent swap.
"""


import pytest

from titan_cli.ai.router.enums import AIProviderType, AITask
from titan_cli.ai.router.executor import AIExecutor
from titan_cli.ai.router.availability import AIProviderAvailability
from titan_cli.core.models import (
    AIConfig,
    AIConnectionConfig,
    AIConnectionType,
    AIDirectProvider,
    AIPreferences,
    AIProviderPreference,
)
from titan_cli.engine import WorkflowContext
import titan_plugin_github.steps.code_review_steps as code_review_steps
from titan_plugin_github.steps.code_review_steps import (
    ai_review_findings,
    ai_review_plan,
    ai_thread_resolution,
    verify_findings,
)


class _FakeAdapter:
    """Stand-in for a headless adapter — its identity, and what it was called with."""

    def __init__(self, cli_name="claude"):
        self.cli_name = cli_name
        self.calls = []

    def execute(self, prompt, **kwargs):
        self.calls.append({"prompt": prompt, **kwargs})
        return None


def _executor(
    *,
    task_preferences=None,
    default_cli="claude",
    installed=("claude", "gemini"),
    default_connection="work-llm",
    cli_models=None,
) -> AIExecutor:
    """
    A real executor (real resolver) with availability pinned.

    Availability is primed rather than probed so a test never depends on which
    CLIs the machine running it happens to have installed.
    """
    connection = AIConnectionConfig(
        name="Test connection",
        connection_type=AIConnectionType.DIRECT_PROVIDER,
        provider=AIDirectProvider.ANTHROPIC,
    )
    config = AIConfig(
        default_connection=default_connection,
        default_cli=default_cli,
        connections={default_connection: connection} if default_connection else {},
        preferences=AIPreferences(tasks=task_preferences or {}),
        cli_models=cli_models or {},
    )
    executor = AIExecutor(ai_config=config)
    executor.availability._cache["headless"] = [
        AIProviderAvailability(provider=AIProviderType.CLI_HEADLESS, identifier=cli)
        for cli in installed
    ]
    executor.availability._cache["interactive"] = []
    executor.availability._cache["remote"] = (
        [AIProviderAvailability(provider=AIProviderType.REMOTE, identifier=default_connection)]
        if default_connection
        else []
    )
    return executor


def _ctx(executor) -> WorkflowContext:
    ctx = WorkflowContext()
    ctx.ai_router = executor
    return ctx


@pytest.fixture(autouse=True)
def stub_adapter_lookup(monkeypatch):
    """Resolve a CLI name to a fake adapter instead of a real installed binary."""
    monkeypatch.setattr(
        code_review_steps,
        "_resolve_headless_adapter",
        lambda cli: _FakeAdapter(cli) if cli in ("auto", "claude", "gemini") else None,
    )


# --- the configured CLI is used -------------------------------------------


@pytest.mark.parametrize(
    "step",
    [ai_review_plan, ai_review_findings, verify_findings, ai_thread_resolution],
)
def test_every_review_step_uses_the_global_default_cli(step):
    adapter, note, ai_off = code_review_steps._resolve_review_adapter(_ctx(_executor()), step)

    assert adapter.cli_name == "claude"
    assert note is None


def test_a_task_preference_for_a_cli_is_honored_over_nothing():
    executor = _executor(
        task_preferences={
            AITask.CODE_REVIEW_FINDINGS: AIProviderPreference(provider=AIProviderType.CLI_HEADLESS)
        },
        default_cli="gemini",
    )

    adapter, note, ai_off = code_review_steps._resolve_review_adapter(_ctx(executor), ai_review_findings)

    assert adapter.cli_name == "gemini"
    assert note is None


def test_findings_and_verification_share_one_task_setting():
    """verify_findings is part of the findings pass, so one preference governs both."""
    executor = _executor(
        task_preferences={
            AITask.CODE_REVIEW_FINDINGS: AIProviderPreference(provider=AIProviderType.OFF)
        }
    )

    findings_adapter, _, findings_off = code_review_steps._resolve_review_adapter(
        _ctx(executor), ai_review_findings
    )
    verify_adapter, _, verify_off = code_review_steps._resolve_review_adapter(
        _ctx(executor), verify_findings
    )

    assert findings_adapter is None and findings_off is True
    assert verify_adapter is None and verify_off is True


# --- every failure names its reason ---------------------------------------


def test_off_reports_that_the_task_is_disabled():
    executor = _executor(
        task_preferences={AITask.CODE_REVIEW_PLAN: AIProviderPreference(provider=AIProviderType.OFF)}
    )

    adapter, note, ai_off = code_review_steps._resolve_review_adapter(_ctx(executor), ai_review_plan)

    assert adapter is None
    assert "turned off" in note
    assert ai_off is True


def test_a_remote_preference_is_refused_by_name_not_silently_run_on_a_cli():
    """A leftover 'remote' preference predates these steps declaring CLI-only."""
    executor = _executor(
        task_preferences={
            AITask.CODE_REVIEW_FINDINGS: AIProviderPreference(provider=AIProviderType.REMOTE)
        }
    )

    adapter, note, ai_off = code_review_steps._resolve_review_adapter(_ctx(executor), ai_review_findings)

    assert adapter is None
    assert "remote" in note
    assert "AI Configuration" in note
    assert ai_off is False


def test_no_default_cli_configured_says_so():
    executor = _executor(default_cli=None)

    adapter, note, ai_off = code_review_steps._resolve_review_adapter(_ctx(executor), ai_review_plan)

    assert adapter is None
    assert "no default CLI is configured" in note
    assert ai_off is False


def test_a_configured_cli_that_is_not_installed_is_named():
    executor = _executor(default_cli="codex", installed=("claude",))

    adapter, note, ai_off = code_review_steps._resolve_review_adapter(_ctx(executor), ai_review_plan)

    assert adapter is None
    assert "codex" in note
    assert ai_off is False


def test_no_router_keeps_the_first_available_cli_behavior():
    """A step called without the façade wired (outside a workflow run)."""
    adapter, note, ai_off = code_review_steps._resolve_review_adapter(WorkflowContext(), ai_review_plan)

    assert adapter.cli_name == "auto"
    assert note is None


# --- the declarations the preferences screen reads ------------------------


@pytest.mark.parametrize(
    "step, task",
    [
        (ai_review_plan, AITask.CODE_REVIEW_PLAN),
        (ai_review_findings, AITask.CODE_REVIEW_FINDINGS),
        (verify_findings, AITask.CODE_REVIEW_FINDINGS),
        (ai_thread_resolution, "thread_resolution"),
    ],
)
def test_steps_declare_cli_only_and_enforce_it(step, task):
    assert step.ai_policy.task == task
    assert step.ai_policy.executes == [AIProviderType.CLI_HEADLESS]
    assert step.ai_enforces is True


# --- the pinned model reaches the CLI -------------------------------------


def test_the_resolved_cli_runs_with_the_model_the_user_pinned():
    """
    These steps call the adapter themselves, so the executor never gets to inject the
    model. Resolution wraps it instead - otherwise the setting is silently dropped and
    the CLI answers with whatever its own default is.
    """
    executor = _executor(cli_models={"claude": "haiku"})

    adapter, _, _ = code_review_steps._resolve_review_adapter(_ctx(executor), ai_review_plan)
    adapter.execute("review this", cwd="/repo", timeout=240)

    assert adapter._adapter.calls[0]["model"] == "haiku"


def test_a_model_pinned_for_another_cli_is_not_borrowed():
    executor = _executor(default_cli="gemini", cli_models={"claude": "haiku"})

    adapter, _, _ = code_review_steps._resolve_review_adapter(_ctx(executor), ai_review_plan)
    adapter.execute("review this")

    assert adapter._adapter.calls[0]["model"] is None


def test_a_caller_naming_a_model_still_wins():
    executor = _executor(cli_models={"claude": "haiku"})

    adapter, _, _ = code_review_steps._resolve_review_adapter(_ctx(executor), ai_review_plan)
    adapter.execute("review this", model="opus")

    assert adapter._adapter.calls[0]["model"] == "opus"


def test_the_wrapper_is_transparent_for_everything_else():
    """Call sites read cli_name and the supports_* capabilities straight off it."""
    executor = _executor(cli_models={"claude": "haiku"})

    adapter, _, _ = code_review_steps._resolve_review_adapter(_ctx(executor), ai_review_plan)

    assert adapter.cli_name == "claude"


@pytest.mark.parametrize(
    "step",
    [ai_review_plan, ai_review_findings, verify_findings, ai_thread_resolution],
)
def test_every_review_step_gets_the_pinned_model(step):
    executor = _executor(cli_models={"claude": "haiku"})

    adapter, _, _ = code_review_steps._resolve_review_adapter(_ctx(executor), step)
    adapter.execute("prompt")

    assert adapter._adapter.calls[0]["model"] == "haiku"


class TestPinnedModelCliSemantics:
    """
    An explicit `model=None` means "no opinion", exactly as it does in the executor.

    These steps drive the adapter themselves, so this wrapper is the only thing carrying
    the user's model. `setdefault` treated a forwarded `model=None` - the shape a call
    site passing an optional profile model would produce - as a decision, and suppressed
    the pin entirely.
    """

    @staticmethod
    def _wrapped(pin):
        from titan_plugin_github.steps.code_review_steps import _PinnedModelCli

        class _Adapter:
            def __init__(self):
                self.calls = []

            def execute(self, prompt, **kwargs):
                self.calls.append(kwargs)
                return "ok"

        adapter = _Adapter()
        return _PinnedModelCli(adapter, pin), adapter

    def test_no_call_site_model_uses_the_pin(self):
        wrapper, adapter = self._wrapped("opus")

        wrapper.execute("prompt")

        assert adapter.calls[0]["model"] == "opus"

    def test_an_explicit_none_does_not_suppress_the_pin(self):
        wrapper, adapter = self._wrapped("opus")

        wrapper.execute("prompt", model=None)

        assert adapter.calls[0]["model"] == "opus"

    def test_a_real_call_site_model_still_wins(self):
        wrapper, adapter = self._wrapped("opus")

        wrapper.execute("prompt", model="haiku")

        assert adapter.calls[0]["model"] == "haiku"

    def test_the_pin_is_exposed_for_the_announcement(self):
        wrapper, _ = self._wrapped("opus")

        assert wrapper.pinned_model == "opus"
