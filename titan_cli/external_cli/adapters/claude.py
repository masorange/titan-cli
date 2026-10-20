"""
Headless adapter for Claude CLI (claude).

Uses `claude --print` with the prompt on stdin for non-interactive execution.
"""

import json
import re
import shutil
import subprocess
from typing import Any, Optional

from titan_cli.core import interrupt
from .base import CliModel, HeadlessResponse, SupportedCLI, usage_from_result_envelope

_ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

_MAX_PARTIAL_CHARS = 200_000
"""Ceiling on the salvaged text of a session that ended without an answer.

A review of a large PR hands back more than a later call can be asked to re-read, and
`partial_output` exists to be fed back to a CLI. The tail is kept rather than the head:
the reports arrive in order, so the end is the part a truncated run had not yet used.
"""


def _tool_result_text(content: Any) -> str:
    """The text of a `tool_result` block, whose content is a string or a list of blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            str(block.get("text") or "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    return ""


def _trim_to_last(text: str, limit: int) -> str:
    """Keep the last `limit` characters, cut at a line break so no line is left halved."""
    if len(text) <= limit:
        return text
    tail = text[-limit:]
    _, newline, rest = tail.partition("\n")
    return rest if newline else tail


def _with_session_outcome(activity: Optional[dict[str, Any]], envelope: dict) -> Optional[dict[str, Any]]:
    """Add what the envelope says about how the session ended and how it fanned out.

    `subagent_stats` is the only place the fan-out is reported, and the fan-out is where
    a review spends almost everything (measured 2026-10-19: 93-96% of two sessions' cost
    was in subagents, which the `usage` block does not cover at all).
    """
    outcome = {
        key: envelope[key]
        for key in ("terminal_reason", "subagent_stats", "num_turns")
        if envelope.get(key) is not None
    }
    if not outcome:
        return activity
    return {**(activity or {}), **outcome}


class ClaudeHeadlessAdapter:
    """
    Runs Claude CLI in headless mode via `claude --print`, prompt on stdin.

    The --print flag makes Claude write the response to stdout
    and exit immediately, without starting an interactive session.
    """

    @property
    def cli_name(self) -> SupportedCLI:
        return SupportedCLI.CLAUDE

    @property
    def supports_structured_output(self) -> bool:
        return True

    @property
    def supports_tool_restriction(self) -> bool:
        return True

    @property
    def supports_effort_control(self) -> bool:
        return True

    @property
    def supports_model_selection(self) -> bool:
        return True

    @property
    def supports_subagents(self) -> bool:
        # The `Agent` tool is available in `--print` sessions.
        return True

    @property
    def subagent_model(self) -> Optional[str]:
        # The `Agent` tool takes a model, and the alias tracks the current Sonnet.
        return "sonnet"

    def is_available(self) -> bool:
        return shutil.which("claude") is not None

    def list_models(self) -> list[CliModel]:
        """Claude has no listing subcommand; its own --help publishes the aliases.

        Aliases rather than versioned ids on purpose: `claude --help` documents them as
        "an alias for the latest model", so they keep pointing at the current release
        instead of pinning whatever was current when this adapter was written. A full
        name still works - the caller can always type one.
        """
        return [
            CliModel("opus", "Opus - most capable"),
            CliModel("sonnet", "Sonnet - balanced"),
            CliModel("haiku", "Haiku - fastest"),
            CliModel("fable", "Fable"),
        ]

    def execute(
        self,
        prompt: str,
        cwd: Optional[str] = None,
        timeout: int = 60,
        json_schema: Optional[dict[str, Any]] = None,
        disallowed_tools: Optional[list[str]] = None,
        effort: Optional[str] = None,
        model: Optional[str] = None,
        allowed_tools: Optional[list[str]] = None,
        max_budget_usd: Optional[float] = None,
    ) -> HeadlessResponse:
        # --output-format stream-json on EVERY call, not just the structured ones. Its
        # closing `result` event IS the envelope `--output-format json` prints, and the
        # envelope is the only place claude reports `usage` and `total_cost_usd` and names
        # the model that actually ran (`modelUsage`) — so asking for it only when a schema
        # is passed left every plain-text call with no cost figure at all. Verified
        # 2026-09-22 that the envelope is emitted without `--json-schema`.
        #
        # The stream rather than the single envelope because the envelope is all-or-nothing:
        # a session killed by `--max-budget-usd` reports `is_error` with no `result`, so a
        # review that had already spent the whole ceiling returned zero characters and its
        # work was unrecoverable (there is no transcript left to `--resume` either; measured
        # 2026-10-19 on two runs of a 79-file PR, $6.12 and $6.20 for nothing). Over the
        # stream the same run has already emitted every subagent's hand-back report before
        # it dies, which is the review itself. `--verbose` is what makes `--print` emit the
        # intermediate events rather than the result alone.
        cmd = ["claude", "--print", "--output-format", "stream-json", "--verbose"]
        # The cwd may be a PR worktree: untrusted code. `--print` skips the workspace trust
        # prompt, so without these flags a PR's `.claude/settings.json` (hooks, permissions),
        # `.mcp.json` servers or `CLAUDE.md` would run/load on the reviewer's machine, and
        # `--disallowedTools` stops none of the first two. Only the user's own settings load.
        cmd += ["--setting-sources", "user", "--strict-mcp-config"]
        if json_schema is not None:
            cmd += ["--json-schema", json.dumps(json_schema)]
        if disallowed_tools:
            # --disallowedTools is a variadic flag with no natural terminator: passed as
            # separate argv tokens, it keeps consuming words until the next recognized flag.
            # A single comma-joined token keeps where the list ends unambiguous.
            cmd += [f"--disallowedTools={','.join(disallowed_tools)}"]
        if allowed_tools:
            # Comma-joined into one token for the same reason as --disallowedTools.
            cmd += [f"--allowedTools={','.join(allowed_tools)}"]
        if max_budget_usd is not None:
            cmd += ["--max-budget-usd", f"{max_budget_usd:g}"]
        if effort is not None:
            cmd += ["--effort", effort]
        if model is not None:
            cmd += ["--model", model]
        # The prompt goes on stdin, never argv: Linux caps ONE argv string at 131,072
        # bytes (MAX_ARG_STRLEN), and exceeding it fails the exec with E2BIG before
        # claude starts. Measured 2026-09-24: a 145k-char triage prompt raised
        # "[Errno 7] Argument list too long: 'claude'". `claude --print` reads its prompt
        # from stdin when none is given as an argument.
        try:
            result = interrupt.run_tracked(
                cmd,
                input=prompt,
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return HeadlessResponse(
                stdout="",
                stderr=f"Claude CLI timed out after {timeout}s",
                exit_code=124,
            )
        except FileNotFoundError:
            return HeadlessResponse(
                stdout="",
                stderr="claude command not found",
                exit_code=127,
            )

        return self._parse_stream(result, expect_structured=json_schema is not None)

    def _parse_stream(
        self, result: subprocess.CompletedProcess, *, expect_structured: bool
    ) -> HeadlessResponse:
        """Read the `--output-format stream-json` events: the envelope, plus what was said.

        One pass over the stream collects three things. The closing `result` event is the
        envelope and is handled exactly as the single-envelope output was. Every other
        event feeds `activity` (what the session did) and `partial_output` (what it said),
        the latter being the only thing a run killed by its ceiling leaves behind.

        A stream that carries no `result` event at all — the process died before writing
        it — is not a format this adapter can read, so it falls back to the raw stdout the
        way a pre-stream claude's output would.
        """
        envelope, said, activity = self._read_events(result.stdout)
        partial = said or None
        if envelope is None:
            # No closing event: either a claude old enough not to stream, or a crash that
            # printed prose. Whatever reached stdout is still the best answer available;
            # `usage=None` says honestly that there is no usage to report.
            return HeadlessResponse(
                stdout=self._sanitize(result.stdout),
                stderr=result.stderr.strip(),
                exit_code=result.returncode,
                activity=activity,
                partial_output=partial,
            )
        return self._from_envelope(
            envelope,
            stderr=result.stderr.strip(),
            returncode=result.returncode,
            expect_structured=expect_structured,
            activity=activity,
            partial_output=partial,
        )

    def _read_events(self, stdout: str) -> tuple[Optional[dict], str, Optional[dict[str, Any]]]:
        """One pass: the closing envelope, the text the session produced, and its activity.

        `partial_output` keeps the two things that carry review content: the lead's own
        prose, and each subagent's hand-back (which arrives as a `tool_result` on the
        lead's turn, i.e. an event with no `parent_tool_use_id`). A subagent's internal
        steps carry its task's id and are counted, not kept — they are the work, not the
        report, and keeping them would bury the reports in file dumps.
        """
        envelope: Optional[dict] = None
        said: list[str] = []
        counts: dict[str, int] = {}
        commands: list[str] = []

        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue

            kind = str(event.get("type") or "unknown")
            if kind == "result":
                envelope = event
                continue

            subtype = event.get("subtype")
            label = f"{kind}.{subtype}" if subtype else kind
            counts[label] = counts.get(label, 0) + 1

            content = event.get("message", {}).get("content") if isinstance(event.get("message"), dict) else None
            if not isinstance(content, list):
                continue
            is_lead_turn = event.get("parent_tool_use_id") is None
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_use":
                    command = (block.get("input") or {}).get("command")
                    if isinstance(command, str):
                        commands.append(command[:200])
                elif is_lead_turn and block.get("type") == "text" and kind == "assistant":
                    said.append(str(block.get("text") or ""))
                elif is_lead_turn and block.get("type") == "tool_result":
                    said.append(_tool_result_text(block.get("content")))

        activity = {"items": counts, "commands": commands} if counts or commands else None
        spoken = self._sanitize("\n\n".join(part for part in said if part.strip()))
        return envelope, _trim_to_last(spoken, _MAX_PARTIAL_CHARS), activity

    def _from_envelope(
        self,
        envelope: dict,
        *,
        stderr: str,
        returncode: int,
        expect_structured: bool,
        activity: Optional[dict[str, Any]],
        partial_output: Optional[str],
    ) -> HeadlessResponse:
        """Turn the stream's closing `result` event into the response.

        With a schema, the model's validated answer is under `structured_output` and
        becomes stdout as compact JSON so downstream parsing sees no surrounding prose;
        it falls back to the envelope's `result` text when the model didn't call the
        structured-output tool (e.g. it judged the request ambiguous). Without a schema,
        `result` IS the answer.

        Either way the envelope is also where `usage`, `total_cost_usd` and the model
        that actually ran are reported, so it is read even on the error path — a call
        that failed still cost money, and hiding that would understate every review
        that had a retry in it.
        """
        usage = usage_from_result_envelope(envelope, source="claude_result_envelope")
        activity = _with_session_outcome(activity, envelope)

        if envelope.get("is_error"):
            # A ceiling hit (`--max-budget-usd`) reports no `result`, only `errors`:
            # ["Reached maximum budget ($6)"]. Without reading it the reason was lost.
            errors = "; ".join(str(item) for item in envelope.get("errors") or [])
            return HeadlessResponse(
                stdout="",
                stderr=str(envelope.get("result") or errors or stderr or "Claude CLI reported an error"),
                exit_code=returncode or 1,
                usage=usage,
                activity=activity,
                partial_output=partial_output,
            )

        if expect_structured:
            structured_output = envelope.get("structured_output")
            if structured_output is not None:
                return HeadlessResponse(
                    stdout=json.dumps(structured_output),
                    stderr=stderr,
                    exit_code=returncode,
                    usage=usage,
                    activity=activity,
                    partial_output=partial_output,
                )

        return HeadlessResponse(
            stdout=self._sanitize(str(envelope.get("result", ""))),
            stderr=stderr,
            exit_code=returncode,
            usage=usage,
            activity=activity,
            partial_output=partial_output,
        )

    def _sanitize(self, text: str) -> str:
        """Strip ANSI escape codes and trailing whitespace."""
        return _ANSI_ESCAPE.sub("", text).strip()
