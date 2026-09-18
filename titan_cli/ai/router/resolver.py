"""
Route resolution for the AI execution routing layer.

Resolves which provider a task should use given persisted preferences
(`titan_cli.core.models.AIPreferences`) and provider availability
(`AIAvailabilityChecker`). Never picks a fallback silently: if a resolved
provider is unavailable, resolution reports that user input is needed instead
of guessing, regardless of how many compatible candidates remain.

The task is the only persisted preference scope. Resolution has exactly three
levels: a runtime override, the user's persisted preference for the task, and
the step's own declared `preferred` order.

Each of those levels answers only WHICH KIND of provider to use. Which concrete
connection or CLI serves that kind comes from the global settings
(`AIConfig.default_connection` / `AIConfig.default_cli`), unless a higher rung - the
task's own pin, or the session override - supplies one. Either way it is attached here,
so every decision leaves this module naming the instance, and the model, that will
actually run.

Instance and model are resolved TOGETHER, by rung: a bare model identifier may never be
read for an instance that a higher rung chose, or a task pinned to claude+opus would
answer a session switch to codex with `codex -m opus`.
"""

from dataclasses import dataclass, field
from typing import List, Optional

from titan_cli.core.models import AIConfig, AIProviderPreference

from .availability import AIAvailabilityChecker, AIProviderAvailability
from .enums import AIProviderType
from .models import AIRouteDecision, AIRoutePolicy
from .session import AISessionOverride


@dataclass
class AIRouteNeedsInput:
    """
    Resolution could not pick a provider automatically.

    Returned when no preference exists yet, or a persisted preference's
    provider became unavailable. Callers should ask the user; no ask-UI
    exists yet, so callers currently just surface this state.
    """

    reason: str
    candidates: List[AIProviderAvailability] = field(default_factory=list)


AIRouteResolution = AIRouteDecision | AIRouteNeedsInput


class AIRouteResolver:
    """Resolves which provider a task should use, given persisted preferences."""

    def __init__(
        self,
        ai_config: Optional[AIConfig],
        availability: AIAvailabilityChecker,
        session_override: Optional[AISessionOverride] = None,
    ):
        """
        Args:
            ai_config: The AI configuration, or None when AI is unconfigured.
            availability: Tells which connections and CLIs can actually be used.
            session_override: What the user chose for this session only (F2/F3). It
                outranks a task's pin and the global default, but is never persisted and
                never changes WHICH KIND of provider runs a task.
        """
        self.ai_config = ai_config
        self.availability = availability
        self.session_override = session_override

    def resolve(
        self,
        task: str,
        policy: Optional[AIRoutePolicy] = None,
        runtime_override: Optional[AIProviderType] = None,
    ) -> AIRouteResolution:
        """
        Resolve a provider following this precedence: runtime override ->
        persisted task preference -> the step's declared `preferred` order ->
        ask the user (no silent fallback).
        """
        if runtime_override is not None:
            refusal = self._guard_executable(runtime_override, policy, task, source="requested")
            if refusal is not None:
                return refusal
            return self._decide(
                runtime_override, reason="runtime override", task=task, policy=policy
            )

        preferences = self._preferences()

        if preferences and task in preferences.tasks:
            return self._resolve_preference(
                preferences.tasks[task],
                policy=policy,
                task=task,
                reason=f"task preference for '{task}'",
            )

        if policy and policy.preferred:
            # Keep the first concrete obstacle: "no default CLI is configured" tells the user
            # what to do, where a generic "nothing resolved" would not.
            first_obstacle: Optional[AIRouteNeedsInput] = None
            for provider in policy.preferred:
                resolved = self._decide(
                    provider, reason=f"step default '{provider}'", task=task, policy=policy
                )
                if isinstance(resolved, AIRouteDecision):
                    return resolved
                first_obstacle = first_obstacle or resolved
            if first_obstacle:
                return first_obstacle

        return AIRouteNeedsInput(
            reason="no persisted preference and no available step default",
            candidates=self._candidates(policy),
        )

    def _decide(
        self,
        provider: AIProviderType,
        reason: str,
        task: str = "",
        policy: Optional[AIRoutePolicy] = None,
    ) -> AIRouteResolution:
        """
        Turn a provider TYPE into a decision naming the instance that will run it.

        The instance is the global default for that kind of provider, unless the task
        pinned one of its own. Either way it is resolved the same: a missing or
        uninstalled instance is reported by name rather than swapped for whatever else
        happens to be available - that rule is what makes a pin safe to offer.
        """
        if provider == AIProviderType.OFF:
            return AIRouteDecision(provider=provider, reason=reason)

        identifier, instance_rung = self._instance_and_rung(provider, task)
        if identifier is None:
            return AIRouteNeedsInput(
                reason=self._missing_instance_reason(provider),
                candidates=self._candidates(policy),
            )

        if not self._identifier_available(provider, identifier):
            return AIRouteNeedsInput(
                reason=(
                    f"the configured {self._instance_noun(provider)} '{identifier}' "
                    f"is not available"
                ),
                candidates=self._candidates(policy),
            )

        model = self._resolved_model(provider, identifier, task, instance_rung)
        if provider == AIProviderType.REMOTE:
            return AIRouteDecision(
                provider=provider,
                connection_id=identifier,
                reason=reason,
                model=model,
            )
        return AIRouteDecision(
            provider=provider, cli=identifier, reason=reason, model=model
        )

    def _configured_instance(self, provider: AIProviderType, task: str = "") -> Optional[str]:
        """The instance serving this kind of provider, ignoring which rung supplied it."""
        return self._instance_and_rung(provider, task)[0]

    # Rungs, highest first. The number is what keeps a model from riding an instance it
    # was never chosen for: a model may come from the rung that supplied the instance or
    # from one ABOVE it, never from below.
    _RUNG_SESSION = 0
    _RUNG_TASK_PIN = 1
    _RUNG_GLOBAL = 2

    def _instance_and_rung(
        self, provider: AIProviderType, task: str
    ) -> tuple[Optional[str], int]:
        """
        The instance serving this kind of provider, and which rung it came from.

        The same three rungs for both kinds - a CLI and a remote connection are the same
        question asked of different transports. Only the half matching this kind is read,
        so a `cli` left on a preference that has since become remote (or the reverse) is
        inert rather than an error.
        """
        if not self.ai_config:
            return None, self._RUNG_GLOBAL

        remote = provider == AIProviderType.REMOTE

        pinned = self._task_preference(task)
        pinned_instance = None
        if pinned is not None:
            pinned_instance = pinned.connection if remote else pinned.cli

        if self.session_override:
            overridden = self.session_override.instance_for(remote)
            if overridden:
                # Naming the instance that is already pinned is not a CHANGE of
                # instance, so the pin's rung still owns the model. Reporting the
                # session rung here would make `_resolved_model` skip the pin and drop a
                # model the user never moved away from - the resolver's version of the
                # rule `use_cli` already applied to the override itself.
                if overridden == pinned_instance:
                    return overridden, self._RUNG_TASK_PIN
                return overridden, self._RUNG_SESSION

        if pinned_instance:
            return pinned_instance, self._RUNG_TASK_PIN

        default = (
            self.ai_config.default_connection if remote else self.ai_config.default_cli
        )
        return default, self._RUNG_GLOBAL

    def _resolved_model(
        self, provider: AIProviderType, identifier: str, task: str, instance_rung: int
    ) -> Optional[str]:
        """
        The model the resolved instance should run with, never taken from below it.

        A session model and a task's pinned model are BARE identifiers: they name a model
        with no instance attached, so reading one for an instance that a higher rung
        chose produces pairs like `codex -m opus` - a claude alias handed to codex. Hence
        the rung guard, and hence `instance_rung`.

        The global layer is exempt and always serves as the fallback, for the same reason
        it never had this bug: its models are keyed BY INSTANCE (`cli_models[cli]`, a
        connection's own `default_model`), so they cannot be read for the wrong one.

        A model from ABOVE the instance's rung is honored on purpose. "Whatever runs this
        task, use this model" is a real instruction - a task pinning only a model, or a
        session naming one without naming an instance - and the user gave it knowing what
        would serve the task.

        `None` means the instance picks for itself. Only an explicit call-site `model=`
        sits above all of this, and it is applied by `AIExecutor` - it is not a user
        setting, so it does not belong in the decision this layer records.
        """
        if not self.ai_config:
            return None

        remote = provider == AIProviderType.REMOTE

        if self.session_override and instance_rung >= self._RUNG_SESSION:
            session_model = self.session_override.model_for(remote)
            if session_model:
                return session_model

        if instance_rung >= self._RUNG_TASK_PIN:
            pinned = self._task_preference(task)
            if pinned is not None and pinned.model:
                return pinned.model

        if remote:
            connection = self.ai_config.connections.get(identifier)
            return getattr(connection, "default_model", None)
        return self.ai_config.cli_models.get(identifier)

    def _task_preference(self, task: str) -> Optional[AIProviderPreference]:
        """The persisted preference for a task, if there is one."""
        preferences = self._preferences()
        if not preferences or not task:
            return None
        return preferences.tasks.get(task)

    @staticmethod
    def _instance_noun(provider: AIProviderType) -> str:
        return "AI connection" if provider == AIProviderType.REMOTE else "CLI"

    @staticmethod
    def _missing_instance_reason(provider: AIProviderType) -> str:
        if provider == AIProviderType.REMOTE:
            return "no default AI connection is configured"
        return "no default CLI is configured"

    def _preferences(self):
        if not self.ai_config or not self.ai_config.preferences:
            return None
        return self.ai_config.preferences

    def _guard_executable(
        self,
        provider: AIProviderType,
        policy: Optional[AIRoutePolicy],
        task: str,
        source: str = "configured",
    ) -> Optional[AIRouteNeedsInput]:
        """
        Refuse a provider the step's code can't execute; None means it can.

        The preferences UI only offers what a step declares in `executes`, but
        a preference can predate a step's declaration (or be shared by several
        steps with different abilities), and a runtime override comes from a
        caller that never consulted `executes` at all. Handing the step a
        provider it can't drive would fail later and further from the cause, so
        it is refused here, by name. Membership depends only on the provider
        kind, so the guard runs before any instance-availability probing: a
        provider the step can never run is refused up front, instead of first
        sending the user off to configure an instance for it. `off` is always
        honored - any step can skip. When the step declared no `executes` at
        all, the guard does not apply.
        """
        if provider == AIProviderType.OFF:
            return None
        if not policy or not policy.executes:
            return None
        if provider in policy.executes:
            return None
        return AIRouteNeedsInput(
            reason=(
                f"the {source} provider for '{task}' is '{provider}', "
                f"which this step cannot run (it supports: "
                f"{', '.join(str(p) for p in policy.executes)})"
            ),
            candidates=self._candidates(policy),
        )

    def _candidates(
        self, policy: Optional[AIRoutePolicy] = None
    ) -> List[AIProviderAvailability]:
        """
        Providers the user could be offered instead.

        Filtered by the step's `executes` when a policy is in scope: offering a
        kind the step can't run would just be refused again by the executable
        guard on the next resolve.
        """
        candidates = (
            self.availability.available_remote_connections()
            + self.availability.available_headless_clis()
            + self.availability.available_interactive_clis()
        )
        if policy and policy.executes:
            candidates = [c for c in candidates if c.provider in policy.executes]
        return candidates

    def _resolve_preference(
        self,
        pref: AIProviderPreference,
        policy: Optional[AIRoutePolicy],
        task: str,
        reason: str,
    ) -> AIRouteResolution:
        """
        Honor a persisted preference, or report why it can't be honored.

        The preference names only a kind of provider; the executable guard runs
        on that kind first, then `_decide` attaches the global instance and
        reports by name if that instance is missing or unavailable. A stored
        provider value that doesn't map to a known `AIProviderType` is reported
        the same way - falling through to the step's defaults would silently
        change which AI runs, hiding the broken preference from the user.
        """
        try:
            provider = AIProviderType(pref.provider)
        except ValueError:
            return AIRouteNeedsInput(
                reason=(
                    f"the stored preference for '{task}' is '{pref.provider}', "
                    f"which is not a known provider type"
                ),
                candidates=self._candidates(policy),
            )

        refusal = self._guard_executable(provider, policy, task)
        if refusal is not None:
            return refusal
        return self._decide(provider, reason=reason, task=task, policy=policy)

    def _identifier_available(self, provider: AIProviderType, identifier: str) -> bool:
        """
        Whether that exact CLI or connection is among the available ones.

        Exact, not "any candidate of the same kind": a configured provider that has gone
        away must be reported, never swapped for a sibling the user didn't choose.
        """
        if provider == AIProviderType.CLI_HEADLESS:
            candidates = self.availability.available_headless_clis()
        elif provider == AIProviderType.CLI_INTERACTIVE:
            candidates = self.availability.available_interactive_clis()
        elif provider == AIProviderType.REMOTE:
            candidates = self.availability.available_remote_connections()
        else:
            return False

        return any(candidate.identifier == identifier for candidate in candidates)


__all__ = ["AIRouteResolver", "AIRouteNeedsInput", "AIRouteResolution"]
