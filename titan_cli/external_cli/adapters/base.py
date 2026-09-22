"""
Base protocol and models for headless CLI adapters.

Each CLI (Claude, Gemini, etc.) implements HeadlessCliAdapter
to abstract away CLI-specific flags and output parsing.
Titan interacts only with this generic interface.
"""

import re
import subprocess
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Optional
from typing import Protocol, runtime_checkable


class SupportedCLI(StrEnum):
    """
    Enum of CLIs with a registered headless adapter.

    Values match the CLI command name and the keys in configs.CLI_REGISTRY,
    so string literals like "claude" remain compatible.
    """
    CLAUDE = "claude"
    GEMINI = "gemini"
    CODEX = "codex"
    OPENCODE = "opencode"
    ANTIGRAVITY = "agy"
    GROK = "grok"


_QUOTA_PATTERNS = re.compile(
    # Google (gemini / agy): gRPC status plus human phrasing like
    # "Individual quota reached" / "Quota exceeded".
    r"resource[_ ]exhausted"
    r"|quota\b.{0,60}\b(reached|exceeded|exhausted)"
    r"|(reached|exceeded)\b.{0,60}\bquota"
    # OpenAI (codex, and opencode on OpenAI): API error type.
    r"|insufficient[_ ]quota"
    # Anthropic (claude): "Claude usage limit reached", "You've reached your usage limit".
    r"|usage limit"
    r"|out of (free )?credits",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CliModel:
    """One model a CLI is willing to run.

    `identifier` is what goes after the CLI's own model flag, verbatim - an alias
    ("opus"), a bare id ("grok-4.6") or a qualified one ("anthropic/claude-sonnet-5"),
    whichever that CLI expects. `label` is for display only.
    """

    identifier: str
    label: str = ""


def model_listing_lines(cmd: list[str], timeout: int = 20) -> list[str]:
    """Run a CLI's own model-listing command and return its non-empty stdout lines.

    Listing models is a convenience, never a precondition for running one: a CLI that
    is not logged in, is offline, or has no such subcommand yields an empty list and the
    caller falls back to letting the user type an identifier. So every failure mode -
    missing binary, non-zero exit, timeout - is flattened to "nothing to offer" rather
    than raised.
    """
    try:
        # errors="replace" because text=True decodes with the platform encoding, and a
        # CLI emitting a stray non-UTF-8 byte would otherwise raise UnicodeDecodeError -
        # a ValueError, which the handler below does not catch - straight through a
        # function whose whole contract is that nothing here raises.
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
            # The child must not reach the terminal. This runs under a Textual app, so
            # a CLI that prompts - not logged in, a pager, a TTY confirmation - would
            # read the user's keystrokes out from under the TUI and only give up when
            # the timeout expires. Listing models is never a precondition, so a CLI
            # that wants input gets EOF and contributes nothing.
            stdin=subprocess.DEVNULL,
        )
    except (subprocess.TimeoutExpired, OSError, ValueError):
        return []
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


@dataclass(frozen=True)
class CliUsage:
    """What one CLI invocation reported about its own consumption.

    Every field is optional because no two CLIs report the same set, and two of the
    five that report anything (codex, agy) never name a price. **A `None` means "this
    CLI did not say", never zero** — an absent figure must not be shown, summed or
    averaged as if the call were free, which is why there is no default of 0 anywhere
    here and why `as_log_fields` omits what it does not have.

    `model_reported` is the model that ACTUALLY ran, when the CLI names it. It is not
    the same thing as the model Titan asked for: a CLI falls back to its own default
    when a pin is missing or unavailable, and that silent substitution is exactly what
    makes two runs incomparable.
    """

    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cache_read_tokens: Optional[int] = None
    cache_write_tokens: Optional[int] = None
    reasoning_tokens: Optional[int] = None
    reported_total_tokens: Optional[int] = None
    cost_usd: Optional[float] = None
    model_reported: Optional[str] = None
    source: Optional[str] = None

    @property
    def total_tokens(self) -> Optional[int]:
        """The CLI's own total when it gives one, else input+output when both exist.

        Deliberately does NOT add cache or reasoning counts into a computed total:
        each CLI folds those into its own figure differently (claude counts cache
        creation separately from input, codex reports `cached_input_tokens` as a
        subset), so summing them would double-count on some CLIs and not others —
        and a total that means something different per CLI is worse than no total.
        """
        if self.reported_total_tokens is not None:
            return self.reported_total_tokens
        if self.input_tokens is None or self.output_tokens is None:
            return None
        return self.input_tokens + self.output_tokens

    @property
    def has_cost(self) -> bool:
        return self.cost_usd is not None

    def as_log_fields(self, prefix: str = "") -> dict[str, Any]:
        """Only the figures this CLI actually reported, ready for a structlog call."""
        fields: dict[str, Any] = {
            f"{prefix}input_tokens": self.input_tokens,
            f"{prefix}output_tokens": self.output_tokens,
            f"{prefix}cache_read_tokens": self.cache_read_tokens,
            f"{prefix}cache_write_tokens": self.cache_write_tokens,
            f"{prefix}reasoning_tokens": self.reasoning_tokens,
            f"{prefix}total_tokens": self.total_tokens,
            f"{prefix}cost_usd": self.cost_usd,
            f"{prefix}model_reported": self.model_reported,
            f"{prefix}usage_source": self.source,
        }
        return {k: v for k, v in fields.items() if v is not None}


def _as_int(value: Any) -> Optional[int]:
    """Coerce a reported count, treating anything unexpected as "not reported"."""
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _as_float(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    return float(value) if isinstance(value, (int, float)) else None


def usage_from_result_envelope(envelope: Any, source: str) -> Optional[CliUsage]:
    """Read usage out of the `result`-envelope shape claude and grok both emit.

    Both publish `usage` (Anthropic's field names), `total_cost_usd`, and a
    `modelUsage` map keyed by the model id that ran. Shared rather than duplicated
    because the two are the same format, not merely similar — grok's headless output
    is modelled on it, down to `cacheReadInputTokens`.

    Returns None when there is no usage block at all, so a caller can tell "this CLI
    said nothing" from "this CLI said zero".
    """
    if not isinstance(envelope, dict):
        return None
    usage = envelope.get("usage")
    model_usage = envelope.get("modelUsage")
    model_reported = None
    if isinstance(model_usage, dict) and len(model_usage) == 1:
        # One key is the ordinary case: one model answered. With several (a subagent on
        # a different model) no single name is the truth, so report none rather than
        # picking one arbitrarily.
        model_reported = next(iter(model_usage))
    cost = _as_float(envelope.get("total_cost_usd"))

    if not isinstance(usage, dict):
        if cost is None and model_reported is None:
            return None
        return CliUsage(cost_usd=cost, model_reported=model_reported, source=source)

    return CliUsage(
        input_tokens=_as_int(usage.get("input_tokens")),
        output_tokens=_as_int(usage.get("output_tokens")),
        cache_read_tokens=_as_int(usage.get("cache_read_input_tokens")),
        cache_write_tokens=_as_int(usage.get("cache_creation_input_tokens")),
        cost_usd=cost,
        model_reported=model_reported,
        source=source,
    )


@dataclass
class HeadlessResponse:
    """Result of a headless CLI execution."""
    stdout: str
    stderr: str
    exit_code: int
    usage: Optional[CliUsage] = None

    @property
    def succeeded(self) -> bool:
        return self.exit_code == 0

    @property
    def quota_exhausted(self) -> bool:
        """Whether this failure looks like an exhausted usage quota.

        Best-effort, pattern-based: each CLI phrases it differently and none of
        them expose a machine-readable code, so this matches the known provider
        signatures in whatever channel the CLI used. Only meaningful on failed
        runs — a successful answer that merely talks about quotas must not
        trigger it, so it is always False when the run succeeded.
        """
        if self.succeeded:
            return False
        return bool(_QUOTA_PATTERNS.search(f"{self.stderr}\n{self.stdout}"))


@runtime_checkable
class HeadlessCliAdapter(Protocol):
    """
    Generic interface for running a CLI tool in headless (non-interactive) mode.

    Each CLI has a concrete adapter that knows:
    - Which flags to use for non-interactive execution
    - How to sanitize/parse the output
    - How to handle CLI-specific quirks

    Analogous to AIProvider in the AI layer.
    """

    @property
    def cli_name(self) -> SupportedCLI:
        """The CLI identifier."""
        ...

    @property
    def supports_structured_output(self) -> bool:
        """Whether this adapter can enforce a JSON Schema on the CLI's own response,
        instead of relying on prompt instructions the model may not follow."""
        ...

    @property
    def supports_tool_restriction(self) -> bool:
        """Whether this adapter can enforce a tool denylist on the CLI's own session,
        instead of relying on prompt instructions the model may not follow."""
        ...

    @property
    def supports_effort_control(self) -> bool:
        """Whether this adapter can set a reasoning-effort tier for the CLI's own session."""
        ...

    @property
    def supports_model_selection(self) -> bool:
        """Whether this adapter can select a specific model for the CLI's own session."""
        ...

    def is_available(self) -> bool:
        """Return True if the CLI is installed and reachable."""
        ...

    def list_models(self) -> list[CliModel]:
        """Return the models this CLI offers, or an empty list when it offers none.

        Each CLI answers this its own way, because there is no common mechanism: some
        have a listing subcommand to shell out to, some publish a stable set of aliases
        in their own help, and some expose nothing at all. An empty list is a normal
        answer, not an error - the caller then lets the user type an identifier, which
        is also the only way to reach a model newer than this adapter knows about.
        """
        ...

    def execute(
        self,
        prompt: str,
        cwd: Optional[str] = None,
        timeout: int = 60,
        json_schema: Optional[dict[str, Any]] = None,
        disallowed_tools: Optional[list[str]] = None,
        effort: Optional[str] = None,
        model: Optional[str] = None,
    ) -> HeadlessResponse:
        """
        Run the CLI with the given prompt in headless mode.

        Args:
            prompt: The prompt to send to the CLI.
            cwd: Working directory for the subprocess.
            timeout: Seconds before the subprocess is killed.
            json_schema: Optional JSON Schema (top-level type "object") to enforce on the
                response. Ignored by adapters where `supports_structured_output` is False.
            disallowed_tools: Optional list of built-in tool names to remove from the CLI's
                session entirely (e.g. ["Bash", "Agent"]). Ignored by adapters where
                `supports_tool_restriction` is False.
            effort: Optional reasoning-effort tier (e.g. "low", "medium", "high"). Ignored by
                adapters where `supports_effort_control` is False.
            model: Optional model identifier to run the CLI with (e.g. "claude-opus-4-8").
                Ignored by adapters where `supports_model_selection` is False.

        Returns:
            HeadlessResponse with stdout, stderr, and exit_code. When `json_schema` is
            honored, stdout is the schema-validated JSON, with no surrounding prose.
        """
        ...
