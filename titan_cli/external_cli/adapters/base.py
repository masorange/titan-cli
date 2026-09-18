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


@dataclass
class HeadlessResponse:
    """Result of a headless CLI execution."""
    stdout: str
    stderr: str
    exit_code: int

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
