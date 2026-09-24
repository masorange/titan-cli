"""
Tests for external_cli.adapters — HeadlessCliAdapter implementations and registry.
"""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from titan_cli.external_cli.adapters.antigravity import (
    _HEADLESS_PREAMBLE,
    AntigravityHeadlessAdapter,
)
from titan_cli.external_cli.adapters.base import CliUsage, HeadlessResponse, SupportedCLI
from titan_cli.external_cli.adapters.claude import ClaudeHeadlessAdapter
from titan_cli.external_cli.adapters.codex import CodexHeadlessAdapter
from titan_cli.external_cli.adapters.gemini import GeminiHeadlessAdapter
from titan_cli.external_cli.adapters.grok import (
    _HEADLESS_PREAMBLE as _GROK_PREAMBLE,
    _PERMISSION_MODE as _GROK_PERMISSION_MODE,
    GrokHeadlessAdapter,
)
from titan_cli.external_cli.adapters.opencode import (
    _HEADLESS_PERMISSIONS,
    _HEADLESS_PREAMBLE as _OPENCODE_PREAMBLE,
    OpenCodeHeadlessAdapter,
)
from titan_cli.external_cli.adapters.registry import (
    HEADLESS_ADAPTER_REGISTRY,
    get_headless_adapter,
)


# ── SupportedCLI ─────────────────────────────────────────────────────────────

class TestSupportedCLI(unittest.TestCase):

    def test_values_match_cli_commands(self):
        self.assertEqual(SupportedCLI.CLAUDE, "claude")
        self.assertEqual(SupportedCLI.GEMINI, "gemini")
        self.assertEqual(SupportedCLI.OPENCODE, "opencode")
        self.assertEqual(SupportedCLI.ANTIGRAVITY, "agy")
        self.assertEqual(SupportedCLI.GROK, "grok")

    def test_is_str_compatible(self):
        self.assertIsInstance(SupportedCLI.CLAUDE, str)


# ── HeadlessResponse ─────────────────────────────────────────────────────────

class TestHeadlessResponse(unittest.TestCase):

    def test_succeeded_when_exit_code_zero(self):
        r = HeadlessResponse(stdout="ok", stderr="", exit_code=0)
        self.assertTrue(r.succeeded)

    def test_failed_when_exit_code_nonzero(self):
        r = HeadlessResponse(stdout="", stderr="err", exit_code=1)
        self.assertFalse(r.succeeded)

    def test_quota_exhausted_matches_known_provider_signatures(self):
        signatures = [
            # Google (gemini / agy)
            "RESOURCE_EXHAUSTED (code 429): Individual quota reached. Resets in 166h",
            "Quota exceeded for quota metric 'Generate requests'",
            # OpenAI (codex)
            "You exceeded your current quota, please check your plan (insufficient_quota)",
            # Anthropic (claude)
            "Claude usage limit reached|1756290000",
            # Anthropic again, and the one the list was missing: observed verbatim on
            # 2026-09-22, exit 1 with this in stderr, reported to the user as a bare
            # "exited with code 1" while the review was thrown away.
            "You've hit your session limit \u00b7 resets 6:30pm (Europe/Madrid)",
        ]
        for text in signatures:
            with self.subTest(text=text):
                r = HeadlessResponse(stdout="", stderr=text, exit_code=1)
                self.assertTrue(r.quota_exhausted)

    def test_quota_exhausted_checks_stdout_too(self):
        r = HeadlessResponse(stdout="usage limit reached", stderr="", exit_code=1)
        self.assertTrue(r.quota_exhausted)

    def test_quota_exhausted_false_on_success_even_if_text_mentions_quota(self):
        r = HeadlessResponse(stdout="Your quota was exceeded last week", stderr="", exit_code=0)
        self.assertFalse(r.quota_exhausted)

    def test_quota_exhausted_false_on_unrelated_failure(self):
        r = HeadlessResponse(stdout="", stderr="model overloaded", exit_code=1)
        self.assertFalse(r.quota_exhausted)

    def test_quota_exhausted_does_not_fire_on_an_unrelated_mention_of_limits(self):
        """The patterns have to stay narrow: a failure about a token limit or a rate
        limit is a different problem with a different remedy."""
        for text in ("input length exceeds the context limit", "429 rate limit, retrying"):
            with self.subTest(text=text):
                r = HeadlessResponse(stdout="", stderr=text, exit_code=1)
                self.assertFalse(r.quota_exhausted)


# ── ClaudeHeadlessAdapter ─────────────────────────────────────────────────────

class TestClaudeHeadlessAdapter(unittest.TestCase):

    def setUp(self):
        self.adapter = ClaudeHeadlessAdapter()

    def test_cli_name(self):
        self.assertEqual(self.adapter.cli_name, SupportedCLI.CLAUDE)

    @patch("shutil.which", return_value="/usr/bin/claude")
    def test_is_available_true(self, _):
        self.assertTrue(self.adapter.is_available())

    @patch("shutil.which", return_value=None)
    def test_is_available_false(self, _):
        self.assertFalse(self.adapter.is_available())

    @patch("subprocess.run")
    def test_execute_success(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout="Analysis complete\n",
            stderr="",
            returncode=0,
        )
        response = self.adapter.execute("review this", cwd="/tmp", timeout=30)

        mock_run.assert_called_once_with(
            ["claude", "--print", "--output-format", "json"],
            input="review this",
            capture_output=True,
            text=True,
            cwd="/tmp",
            timeout=30,
        )
        self.assertEqual(response.stdout, "Analysis complete")
        self.assertEqual(response.exit_code, 0)
        self.assertTrue(response.succeeded)

    @patch("subprocess.run")
    def test_execute_failure_exit_code(self, mock_run):
        mock_run.return_value = MagicMock(stdout="", stderr="error", returncode=1)
        response = self.adapter.execute("prompt")
        self.assertFalse(response.succeeded)
        self.assertEqual(response.exit_code, 1)

    @patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="claude", timeout=60))
    def test_execute_timeout(self, _):
        response = self.adapter.execute("prompt", timeout=60)
        self.assertEqual(response.exit_code, 124)
        self.assertIn("timed out", response.stderr)

    @patch("subprocess.run", side_effect=FileNotFoundError)
    def test_execute_cli_not_found(self, _):
        response = self.adapter.execute("prompt")
        self.assertEqual(response.exit_code, 127)
        self.assertIn("not found", response.stderr)

    @patch("subprocess.run")
    def test_execute_strips_ansi_codes(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout="\x1b[32mGreen text\x1b[0m\n",
            stderr="",
            returncode=0,
        )
        response = self.adapter.execute("prompt")
        self.assertEqual(response.stdout, "Green text")

    def test_supports_structured_output(self):
        self.assertTrue(self.adapter.supports_structured_output)

    @patch("subprocess.run")
    def test_execute_with_json_schema_adds_output_format_flags(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout=json.dumps({"structured_output": {"findings": []}}),
            stderr="",
            returncode=0,
        )
        schema = {"type": "object", "properties": {"findings": {"type": "array"}}}
        self.adapter.execute("review this", cwd="/tmp", timeout=45, json_schema=schema)

        mock_run.assert_called_once_with(
            ["claude", "--print", "--output-format", "json", "--json-schema", json.dumps(schema)],
            input="review this",
            capture_output=True,
            text=True,
            cwd="/tmp",
            timeout=45,
        )

    @patch("subprocess.run")
    def test_execute_with_json_schema_unwraps_structured_output(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout=json.dumps({"structured_output": {"findings": [{"title": "Bug"}]}, "is_error": False}),
            stderr="",
            returncode=0,
        )
        response = self.adapter.execute("prompt", json_schema={"type": "object"})

        self.assertEqual(json.loads(response.stdout), {"findings": [{"title": "Bug"}]})
        self.assertTrue(response.succeeded)

    @patch("subprocess.run")
    def test_execute_with_json_schema_falls_back_to_result_text_when_tool_not_called(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout=json.dumps({"result": "I won't call that tool.", "is_error": False}),
            stderr="",
            returncode=0,
        )
        response = self.adapter.execute("prompt", json_schema={"type": "object"})

        self.assertEqual(response.stdout, "I won't call that tool.")
        self.assertTrue(response.succeeded)

    @patch("subprocess.run")
    def test_execute_with_json_schema_surfaces_cli_error(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout=json.dumps({"is_error": True, "result": "API Error: 400 bad schema"}),
            stderr="",
            returncode=1,
        )
        response = self.adapter.execute("prompt", json_schema={"type": "object"})

        self.assertFalse(response.succeeded)
        self.assertIn("bad schema", response.stderr)

    @patch("subprocess.run")
    def test_execute_with_json_schema_falls_back_on_unparseable_envelope(self, mock_run):
        mock_run.return_value = MagicMock(stdout="not json at all", stderr="", returncode=0)
        response = self.adapter.execute("prompt", json_schema={"type": "object"})

        self.assertEqual(response.stdout, "not json at all")
        self.assertTrue(response.succeeded)

    def test_supports_tool_restriction(self):
        self.assertTrue(self.adapter.supports_tool_restriction)

    @patch("subprocess.run")
    def test_the_prompt_never_travels_on_argv(self, mock_run):
        """Linux caps one argv string at 131,072 bytes; a 145k-char triage prompt failed
        the exec with E2BIG before claude started. On stdin there is no such ceiling."""
        mock_run.return_value = MagicMock(stdout=json.dumps({"result": "ok"}), stderr="", returncode=0)
        prompt = "x" * 200_000
        self.adapter.execute(prompt)
        argv = mock_run.call_args.args[0]
        self.assertNotIn(prompt, argv)
        self.assertEqual(mock_run.call_args.kwargs["input"], prompt)

    @patch("subprocess.run")
    def test_execute_with_disallowed_tools_adds_flag(self, mock_run):
        mock_run.return_value = MagicMock(stdout="ok", stderr="", returncode=0)
        self.adapter.execute(
            "review this", cwd="/tmp", timeout=45, disallowed_tools=["Bash", "Agent"]
        )

        mock_run.assert_called_once_with(
            ["claude", "--print", "--output-format", "json", "--disallowedTools=Bash,Agent"],
            input="review this",
            capture_output=True,
            text=True,
            cwd="/tmp",
            timeout=45,
        )

    @patch("subprocess.run")
    def test_execute_without_disallowed_tools_omits_flag(self, mock_run):
        mock_run.return_value = MagicMock(stdout="ok", stderr="", returncode=0)
        self.adapter.execute("review this")

        called_cmd = mock_run.call_args.args[0]
        self.assertNotIn("--disallowedTools", called_cmd)

    def test_supports_effort_control(self):
        self.assertTrue(self.adapter.supports_effort_control)

    @patch("subprocess.run")
    def test_execute_with_effort_adds_flag(self, mock_run):
        mock_run.return_value = MagicMock(stdout="ok", stderr="", returncode=0)
        self.adapter.execute("review this", cwd="/tmp", timeout=45, effort="medium")

        mock_run.assert_called_once_with(
            ["claude", "--print", "--output-format", "json", "--effort", "medium"],
            input="review this",
            capture_output=True,
            text=True,
            cwd="/tmp",
            timeout=45,
        )

    @patch("subprocess.run")
    def test_execute_without_effort_omits_flag(self, mock_run):
        mock_run.return_value = MagicMock(stdout="ok", stderr="", returncode=0)
        self.adapter.execute("review this")

        called_cmd = mock_run.call_args.args[0]
        self.assertNotIn("--effort", called_cmd)


# ── CodexHeadlessAdapter ──────────────────────────────────────────────────────

class TestCodexHeadlessAdapterStructuredOutput(unittest.TestCase):
    """Codex has no structured-output support (yet) — json_schema must be a no-op."""

    def setUp(self):
        self.adapter = CodexHeadlessAdapter()

    def test_supports_structured_output_is_false(self):
        self.assertFalse(self.adapter.supports_structured_output)

    @patch("subprocess.run")
    def test_execute_ignores_json_schema(self, mock_run):
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
        self.adapter.execute("prompt", json_schema={"type": "object"})

        called_cmd = mock_run.call_args.args[0]
        self.assertNotIn("--json-schema", called_cmd)

    def test_supports_tool_restriction_is_false(self):
        self.assertFalse(self.adapter.supports_tool_restriction)

    @patch("subprocess.run")
    def test_execute_ignores_disallowed_tools(self, mock_run):
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
        self.adapter.execute("prompt", disallowed_tools=["Bash", "Agent"])

        called_cmd = mock_run.call_args.args[0]
        self.assertNotIn("--disallowedTools", called_cmd)

    def test_supports_effort_control_is_false(self):
        self.assertFalse(self.adapter.supports_effort_control)

    @patch("subprocess.run")
    def test_execute_ignores_effort(self, mock_run):
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
        self.adapter.execute("prompt", effort="medium")

        called_cmd = mock_run.call_args.args[0]
        self.assertNotIn("--effort", called_cmd)


# ── GeminiHeadlessAdapter ─────────────────────────────────────────────────────

class TestGeminiHeadlessAdapter(unittest.TestCase):

    def setUp(self):
        self.adapter = GeminiHeadlessAdapter()

    def test_cli_name(self):
        self.assertEqual(self.adapter.cli_name, SupportedCLI.GEMINI)

    @patch("shutil.which", return_value="/usr/bin/gemini")
    def test_is_available_true(self, _):
        self.assertTrue(self.adapter.is_available())

    @patch("shutil.which", return_value=None)
    def test_is_available_false(self, _):
        self.assertFalse(self.adapter.is_available())

    def test_supports_structured_output_is_false(self):
        self.assertFalse(self.adapter.supports_structured_output)

    @patch("subprocess.run")
    def test_execute_passes_prompt_with_flag(self, mock_run):
        mock_run.return_value = MagicMock(stdout="response\n", stderr="", returncode=0)
        self.adapter.execute("my prompt", cwd="/repo", timeout=45)

        mock_run.assert_called_once_with(
            ["gemini", "--prompt", "my prompt"],
            capture_output=True,
            text=True,
            cwd="/repo",
            timeout=45,
        )

    @patch("subprocess.run")
    def test_execute_ignores_json_schema(self, mock_run):
        mock_run.return_value = MagicMock(stdout="response\n", stderr="", returncode=0)
        self.adapter.execute("my prompt", json_schema={"type": "object"})

        mock_run.assert_called_once_with(
            ["gemini", "--prompt", "my prompt"],
            capture_output=True,
            text=True,
            cwd=None,
            timeout=60,
        )

    @patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="gemini", timeout=60))
    def test_execute_timeout(self, _):
        response = self.adapter.execute("prompt", timeout=60)
        self.assertEqual(response.exit_code, 124)

    @patch("subprocess.run", side_effect=FileNotFoundError)
    def test_execute_cli_not_found(self, _):
        response = self.adapter.execute("prompt")
        self.assertEqual(response.exit_code, 127)

    def test_supports_tool_restriction_is_false(self):
        self.assertFalse(self.adapter.supports_tool_restriction)

    @patch("subprocess.run")
    def test_execute_ignores_disallowed_tools(self, mock_run):
        mock_run.return_value = MagicMock(stdout="response\n", stderr="", returncode=0)
        self.adapter.execute("my prompt", disallowed_tools=["Bash", "Agent"])

        mock_run.assert_called_once_with(
            ["gemini", "--prompt", "my prompt"],
            capture_output=True,
            text=True,
            cwd=None,
            timeout=60,
        )

    def test_supports_effort_control_is_false(self):
        self.assertFalse(self.adapter.supports_effort_control)

    @patch("subprocess.run")
    def test_execute_ignores_effort(self, mock_run):
        mock_run.return_value = MagicMock(stdout="response\n", stderr="", returncode=0)
        self.adapter.execute("my prompt", effort="medium")

        mock_run.assert_called_once_with(
            ["gemini", "--prompt", "my prompt"],
            capture_output=True,
            text=True,
            cwd=None,
            timeout=60,
        )


# ── OpenCodeHeadlessAdapter ───────────────────────────────────────────────────

class TestOpenCodeHeadlessAdapter(unittest.TestCase):

    def setUp(self):
        self.adapter = OpenCodeHeadlessAdapter()

    def test_cli_name(self):
        self.assertEqual(self.adapter.cli_name, SupportedCLI.OPENCODE)

    @patch("shutil.which", return_value="/usr/bin/opencode")
    def test_is_available_true(self, _):
        self.assertTrue(self.adapter.is_available())

    @patch("shutil.which", return_value=None)
    def test_is_available_false(self, _):
        self.assertFalse(self.adapter.is_available())

    @patch("subprocess.run")
    def test_execute_uses_run_with_json_format(self, mock_run):
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
        self.adapter.execute("my prompt", cwd="/repo", timeout=45)

        kwargs = mock_run.call_args.kwargs
        self.assertEqual(
            mock_run.call_args.args[0],
            ["opencode", "run", "--format", "json", _OPENCODE_PREAMBLE + "my prompt"],
        )
        self.assertEqual(kwargs["cwd"], "/repo")
        self.assertEqual(kwargs["timeout"], 45)
        # Detached from the controlling tty so opencode cannot draw its
        # status bar over Titan's TUI via /dev/tty.
        self.assertEqual(kwargs["stdin"], subprocess.DEVNULL)
        self.assertTrue(kwargs["start_new_session"])

    @patch("subprocess.run")
    def test_execute_exports_readonly_permission_override(self, mock_run):
        # Headless opencode auto-rejects "ask" permissions and the run dies without
        # an answer; the env var scopes read-only git allows to Titan's subprocess
        # without touching the user's own opencode config.
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
        self.adapter.execute("prompt")

        env = mock_run.call_args.kwargs["env"]
        self.assertEqual(json.loads(env["OPENCODE_PERMISSION"]), _HEADLESS_PERMISSIONS)
        self.assertEqual(_HEADLESS_PERMISSIONS["edit"], "deny")
        self.assertEqual(_HEADLESS_PERMISSIONS["bash"]["*"], "deny")
        # The rest of the environment is inherited, not replaced.
        self.assertIn("PATH", env)

    @patch("subprocess.run")
    def test_execute_with_model_adds_flag(self, mock_run):
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
        self.adapter.execute("prompt", model="anthropic/claude-sonnet-4-5")

        called_cmd = mock_run.call_args.args[0]
        self.assertIn("-m", called_cmd)
        self.assertIn("anthropic/claude-sonnet-4-5", called_cmd)

    @patch("subprocess.run")
    def test_execute_extracts_text_events_from_jsonl(self, mock_run):
        jsonl = "\n".join([
            json.dumps({"type": "step_start", "part": {"type": "step-start"}}),
            json.dumps({"type": "text", "part": {"type": "text", "text": "pong"}}),
            json.dumps({"type": "step_finish", "part": {"reason": "stop"}}),
        ])
        mock_run.return_value = MagicMock(stdout=jsonl, stderr="", returncode=0)
        response = self.adapter.execute("prompt")

        self.assertEqual(response.stdout, "pong")
        self.assertTrue(response.succeeded)

    @patch("subprocess.run")
    def test_execute_joins_multiple_text_events(self, mock_run):
        jsonl = "\n".join([
            json.dumps({"type": "text", "part": {"type": "text", "text": "first"}}),
            json.dumps({"type": "text", "part": {"type": "text", "text": "second"}}),
        ])
        mock_run.return_value = MagicMock(stdout=jsonl, stderr="", returncode=0)
        response = self.adapter.execute("prompt")

        self.assertEqual(response.stdout, "first\nsecond")

    @patch("subprocess.run")
    def test_execute_skips_unparseable_lines(self, mock_run):
        jsonl = "not json\n" + json.dumps({"type": "text", "part": {"text": "ok"}})
        mock_run.return_value = MagicMock(stdout=jsonl, stderr="", returncode=0)
        response = self.adapter.execute("prompt")

        self.assertEqual(response.stdout, "ok")

    @patch("subprocess.run")
    def test_execute_discards_narration_before_tool_calls(self, mock_run):
        # Agentic runs narrate between tool calls as plain "text" events; only what
        # comes after the last tool is the answer.
        jsonl = "\n".join([
            json.dumps({"type": "text", "part": {"text": "Reviewing the repo state"}}),
            json.dumps({"type": "tool_use", "part": {"tool": "read"}}),
            json.dumps({"type": "text", "part": {"text": "Now checking the diff"}}),
            json.dumps({"type": "tool_use", "part": {"tool": "bash"}}),
            json.dumps({"type": "text", "part": {"text": "The real answer"}}),
        ])
        mock_run.return_value = MagicMock(stdout=jsonl, stderr="", returncode=0)
        response = self.adapter.execute("prompt")

        self.assertEqual(response.stdout, "The real answer")

    @patch("subprocess.run")
    def test_execute_prefers_final_answer_phase_over_narration(self, mock_run):
        # Some providers tag the answer explicitly; narration in the same step must not
        # be joined in front of it.
        jsonl = "\n".join([
            json.dumps({"type": "tool_use", "part": {"tool": "read"}}),
            json.dumps({"type": "text", "part": {"text": "Let me summarize"}}),
            json.dumps({"type": "text", "part": {
                "text": "The real answer",
                "metadata": {"openai": {"phase": "final_answer"}},
            }}),
        ])
        mock_run.return_value = MagicMock(stdout=jsonl, stderr="", returncode=0)
        response = self.adapter.execute("prompt")

        self.assertEqual(response.stdout, "The real answer")

    @patch("subprocess.run")
    def test_execute_falls_back_to_last_narration_when_run_dies_on_a_tool(self, mock_run):
        # A run that ends on a tool_use (denied permission, tool error) has no text
        # after the last tool; the last narration beats returning an empty string.
        jsonl = "\n".join([
            json.dumps({"type": "text", "part": {"text": "Reviewing the repo state"}}),
            json.dumps({"type": "tool_use", "part": {"tool": "read"}}),
            json.dumps({"type": "text", "part": {"text": "Checking the commit log"}}),
            json.dumps({"type": "tool_use", "part": {"tool": "bash", "state": {"status": "error"}}}),
        ])
        mock_run.return_value = MagicMock(stdout=jsonl, stderr="", returncode=0)
        response = self.adapter.execute("prompt")

        self.assertEqual(response.stdout, "Checking the commit log")

    @patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="opencode", timeout=60))
    def test_execute_timeout(self, _):
        response = self.adapter.execute("prompt", timeout=60)
        self.assertEqual(response.exit_code, 124)
        self.assertIn("timed out", response.stderr)

    @patch("subprocess.run", side_effect=FileNotFoundError)
    def test_execute_cli_not_found(self, _):
        response = self.adapter.execute("prompt")
        self.assertEqual(response.exit_code, 127)
        self.assertIn("not found", response.stderr)

    def test_supports_structured_output_is_false(self):
        self.assertFalse(self.adapter.supports_structured_output)

    @patch("subprocess.run")
    def test_execute_ignores_json_schema(self, mock_run):
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
        self.adapter.execute("prompt", json_schema={"type": "object"})

        called_cmd = mock_run.call_args.args[0]
        self.assertNotIn("--json-schema", called_cmd)

    def test_supports_tool_restriction_is_false(self):
        self.assertFalse(self.adapter.supports_tool_restriction)

    @patch("subprocess.run")
    def test_execute_ignores_disallowed_tools(self, mock_run):
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
        self.adapter.execute("prompt", disallowed_tools=["Bash", "Agent"])

        called_cmd = mock_run.call_args.args[0]
        self.assertNotIn("--disallowedTools", called_cmd)

    def test_supports_effort_control_is_false(self):
        self.assertFalse(self.adapter.supports_effort_control)

    @patch("subprocess.run")
    def test_execute_ignores_effort(self, mock_run):
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
        self.adapter.execute("prompt", effort="medium")

        called_cmd = mock_run.call_args.args[0]
        self.assertNotIn("--effort", called_cmd)
        self.assertNotIn("--variant", called_cmd)


# ── AntigravityHeadlessAdapter ────────────────────────────────────────────────

class TestAntigravityHeadlessAdapter(unittest.TestCase):

    def setUp(self):
        self.adapter = AntigravityHeadlessAdapter()
        # execute() provisions agy's settings file; point it at a temp dir so no
        # test ever touches the real one in the user's home.
        self._settings_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._settings_dir.cleanup)
        self.settings_path = Path(self._settings_dir.name) / "settings.json"
        patcher = patch(
            "titan_cli.external_cli.adapters.antigravity._SETTINGS_PATH", self.settings_path
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_cli_name(self):
        self.assertEqual(self.adapter.cli_name, SupportedCLI.ANTIGRAVITY)

    @patch("shutil.which", return_value="/usr/bin/agy")
    def test_is_available_true(self, _):
        self.assertTrue(self.adapter.is_available())

    @patch("shutil.which", return_value=None)
    def test_is_available_false(self, _):
        self.assertFalse(self.adapter.is_available())

    @patch("subprocess.run")
    def test_execute_success(self, mock_run):
        mock_run.return_value = MagicMock(stdout="pong\n", stderr="", returncode=0)
        response = self.adapter.execute("review this", cwd="/tmp", timeout=30)

        mock_run.assert_called_once_with(
            ["agy", "--output-format", "json", "--print", _HEADLESS_PREAMBLE + "review this"],
            capture_output=True,
            text=True,
            cwd="/tmp",
            timeout=30,
        )
        self.assertEqual(response.stdout, "pong")
        self.assertTrue(response.succeeded)

    @patch("subprocess.run")
    def test_print_flag_is_last_and_immediately_precedes_prompt(self, mock_run):
        # --print consumes the next argv token as its prompt; any flag placed
        # after it would be swallowed. Every option must come before it.
        mock_run.return_value = MagicMock(stdout="ok", stderr="", returncode=0)
        self.adapter.execute(
            "the prompt",
            json_schema={"type": "object"},
            effort="high",
            model="gemini-3-pro",
        )

        called_cmd = mock_run.call_args.args[0]
        self.assertEqual(called_cmd[-2:], ["--print", _HEADLESS_PREAMBLE + "the prompt"])

    @patch("subprocess.run")
    def test_execute_strips_ansi_codes(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout="\x1b[32mGreen text\x1b[0m\n",
            stderr="",
            returncode=0,
        )
        response = self.adapter.execute("prompt")
        self.assertEqual(response.stdout, "Green text")

    @patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="agy", timeout=60))
    def test_execute_timeout(self, _):
        response = self.adapter.execute("prompt", timeout=60)
        self.assertEqual(response.exit_code, 124)
        self.assertIn("timed out", response.stderr)

    @patch("subprocess.run", side_effect=FileNotFoundError)
    def test_execute_cli_not_found(self, _):
        response = self.adapter.execute("prompt")
        self.assertEqual(response.exit_code, 127)
        self.assertIn("not found", response.stderr)

    def test_supports_structured_output(self):
        self.assertTrue(self.adapter.supports_structured_output)

    @patch("subprocess.run")
    def test_execute_with_json_schema_adds_output_format_flags(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout=json.dumps({"status": "SUCCESS", "structured_output": {"findings": []}}),
            stderr="",
            returncode=0,
        )
        schema = {"type": "object", "properties": {"findings": {"type": "array"}}}
        self.adapter.execute("review this", cwd="/tmp", timeout=45, json_schema=schema)

        mock_run.assert_called_once_with(
            ["agy", "--output-format", "json", "--json-schema", json.dumps(schema), "--print", _HEADLESS_PREAMBLE + "review this"],
            capture_output=True,
            text=True,
            cwd="/tmp",
            timeout=45,
        )

    @patch("subprocess.run")
    def test_execute_with_json_schema_unwraps_structured_output(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout=json.dumps({"status": "SUCCESS", "structured_output": {"findings": [{"title": "Bug"}]}}),
            stderr="",
            returncode=0,
        )
        response = self.adapter.execute("prompt", json_schema={"type": "object"})

        self.assertEqual(json.loads(response.stdout), {"findings": [{"title": "Bug"}]})
        self.assertTrue(response.succeeded)

    @patch("subprocess.run")
    def test_execute_with_json_schema_falls_back_to_response_text(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout=json.dumps({"status": "SUCCESS", "response": "prose answer"}),
            stderr="",
            returncode=0,
        )
        response = self.adapter.execute("prompt", json_schema={"type": "object"})

        self.assertEqual(response.stdout, "prose answer")
        self.assertTrue(response.succeeded)

    @patch("subprocess.run")
    def test_execute_with_json_schema_surfaces_cli_error(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout=json.dumps({"status": "ERROR", "response": "quota exceeded"}),
            stderr="",
            returncode=1,
        )
        response = self.adapter.execute("prompt", json_schema={"type": "object"})

        self.assertFalse(response.succeeded)
        self.assertIn("quota exceeded", response.stderr)

    @patch("subprocess.run")
    def test_execute_with_json_schema_surfaces_error_field_when_response_empty(self, mock_run):
        # Hard failures (e.g. quota exhaustion) leave `response` empty and put the
        # cause in an error field — that detail must reach the user, not a generic
        # "reported an error" message.
        mock_run.return_value = MagicMock(
            stdout=json.dumps(
                {"status": "FAILED", "response": "", "error": "RESOURCE_EXHAUSTED (429): Individual quota reached"}
            ),
            stderr="",
            returncode=1,
        )
        response = self.adapter.execute("prompt", json_schema={"type": "object"})

        self.assertFalse(response.succeeded)
        self.assertIn("RESOURCE_EXHAUSTED", response.stderr)

    @patch("subprocess.run")
    def test_execute_with_json_schema_falls_back_on_unparseable_envelope(self, mock_run):
        mock_run.return_value = MagicMock(stdout="not json at all", stderr="", returncode=0)
        response = self.adapter.execute("prompt", json_schema={"type": "object"})

        self.assertEqual(response.stdout, "not json at all")
        self.assertTrue(response.succeeded)

    def test_supports_tool_restriction_is_false(self):
        self.assertFalse(self.adapter.supports_tool_restriction)

    @patch("subprocess.run")
    def test_execute_ignores_disallowed_tools(self, mock_run):
        mock_run.return_value = MagicMock(stdout="ok", stderr="", returncode=0)
        self.adapter.execute("prompt", disallowed_tools=["Bash", "Agent"])

        called_cmd = mock_run.call_args.args[0]
        self.assertNotIn("--disallowedTools", called_cmd)

    def test_supports_effort_control(self):
        self.assertTrue(self.adapter.supports_effort_control)

    @patch("subprocess.run")
    def test_execute_with_effort_adds_flag(self, mock_run):
        mock_run.return_value = MagicMock(stdout="ok", stderr="", returncode=0)
        self.adapter.execute("review this", effort="medium")

        called_cmd = mock_run.call_args.args[0]
        self.assertIn("--effort", called_cmd)
        self.assertIn("medium", called_cmd)

    def test_supports_model_selection(self):
        self.assertTrue(self.adapter.supports_model_selection)

    @patch("subprocess.run")
    def test_execute_with_model_adds_flag(self, mock_run):
        mock_run.return_value = MagicMock(stdout="ok", stderr="", returncode=0)
        self.adapter.execute("prompt", model="gemini-3-pro")

        called_cmd = mock_run.call_args.args[0]
        self.assertIn("--model", called_cmd)
        self.assertIn("gemini-3-pro", called_cmd)

    # ── read-permission provisioning ──────────────────────────────────────────

    @patch("subprocess.run")
    def test_execute_creates_settings_with_read_rules_when_absent(self, mock_run):
        mock_run.return_value = MagicMock(stdout="ok", stderr="", returncode=0)
        self.adapter.execute("prompt")

        settings = json.loads(self.settings_path.read_text())
        self.assertIn("read_file(*)", settings["permissions"]["allow"])

    @patch("subprocess.run")
    def test_execute_merges_rules_preserving_existing_settings(self, mock_run):
        mock_run.return_value = MagicMock(stdout="ok", stderr="", returncode=0)
        self.settings_path.write_text(json.dumps({
            "colorScheme": "dark",
            "permissions": {"allow": ["command(git status)"]},
        }))

        self.adapter.execute("prompt")

        settings = json.loads(self.settings_path.read_text())
        self.assertEqual(settings["colorScheme"], "dark")
        self.assertIn("command(git status)", settings["permissions"]["allow"])
        self.assertIn("read_file(*)", settings["permissions"]["allow"])

    @patch("subprocess.run")
    def test_execute_does_not_rewrite_settings_when_rules_present(self, mock_run):
        mock_run.return_value = MagicMock(stdout="ok", stderr="", returncode=0)
        from titan_cli.external_cli.adapters.antigravity import _READ_ONLY_PERMISSIONS

        original = json.dumps({"permissions": {"allow": list(_READ_ONLY_PERMISSIONS)}})
        self.settings_path.write_text(original)

        self.adapter.execute("prompt")

        self.assertEqual(self.settings_path.read_text(), original)

    @patch("subprocess.run")
    def test_execute_leaves_malformed_settings_alone_and_still_runs(self, mock_run):
        mock_run.return_value = MagicMock(stdout="ok", stderr="", returncode=0)
        self.settings_path.write_text("{not valid json")

        response = self.adapter.execute("prompt")

        self.assertEqual(self.settings_path.read_text(), "{not valid json")
        self.assertEqual(response.stdout, "ok")
        mock_run.assert_called_once()


# ── GrokHeadlessAdapter ───────────────────────────────────────────────────────

_GROK_BASE_CMD = [
    "grok",
    "--no-auto-update",
    "--output-format",
    "streaming-messages-json",
    "--permission-mode",
    _GROK_PERMISSION_MODE,
]


def _grok_stream(result="pong", *, narration="I'll look into this first.", **extra):
    """One NDJSON run: an assistant narration turn, then the terminal result line.

    The narration is what `--output-format json` would concatenate onto the answer,
    so every parsing test carries one.
    """
    lines = [
        json.dumps({"type": "system", "subtype": "init", "session_id": "abc"}),
        json.dumps(
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [
                        {"type": "thinking", "thinking": "hidden reasoning"},
                        {"type": "text", "text": narration},
                    ],
                },
            }
        ),
        json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": result, **extra}),
    ]
    return "\n".join(lines) + "\n"


class TestGrokHeadlessAdapter(unittest.TestCase):

    def setUp(self):
        self.adapter = GrokHeadlessAdapter()

    def test_cli_name(self):
        self.assertEqual(self.adapter.cli_name, SupportedCLI.GROK)

    def test_capabilities(self):
        # Structured output is off on purpose: grok's --json-schema ends the run at
        # the first text output, coercing the narration into the schema.
        self.assertFalse(self.adapter.supports_structured_output)
        self.assertTrue(self.adapter.supports_tool_restriction)
        self.assertTrue(self.adapter.supports_effort_control)
        self.assertTrue(self.adapter.supports_model_selection)

    @patch("shutil.which", return_value="/usr/local/bin/grok")
    def test_is_available_true(self, _):
        self.assertTrue(self.adapter.is_available())

    @patch("shutil.which", return_value=None)
    def test_is_available_false(self, _):
        self.assertFalse(self.adapter.is_available())

    @patch("subprocess.run")
    def test_execute_success(self, mock_run):
        mock_run.return_value = MagicMock(stdout=_grok_stream(), stderr="", returncode=0)

        response = self.adapter.execute("review this", cwd="/tmp", timeout=30)

        mock_run.assert_called_once_with(
            _GROK_BASE_CMD + ["-p", _GROK_PREAMBLE + "review this"],
            capture_output=True,
            text=True,
            cwd="/tmp",
            timeout=30,
        )
        self.assertEqual(response.stdout, "pong")
        self.assertTrue(response.succeeded)

    @patch("subprocess.run")
    def test_execute_pins_permission_mode_so_headless_never_waits_for_approval(self, mock_run):
        # grok's default mode is "ask", which cannot prompt without a TTY.
        mock_run.return_value = MagicMock(stdout=_grok_stream(), stderr="", returncode=0)

        self.adapter.execute("prompt")

        called_cmd = mock_run.call_args.args[0]
        self.assertIn("--permission-mode", called_cmd)
        self.assertEqual(called_cmd[called_cmd.index("--permission-mode") + 1], "dontAsk")

    @patch("subprocess.run")
    def test_prompt_flag_is_last_and_immediately_precedes_prompt(self, mock_run):
        mock_run.return_value = MagicMock(stdout=_grok_stream(), stderr="", returncode=0)

        self.adapter.execute(
            "the prompt",
            json_schema={"type": "object"},
            disallowed_tools=["Bash"],
            effort="high",
            model="grok-build-0.1",
        )

        called_cmd = mock_run.call_args.args[0]
        self.assertEqual(called_cmd[-2:], ["-p", _GROK_PREAMBLE + "the prompt"])

    @patch("subprocess.run")
    def test_execute_with_model_and_effort(self, mock_run):
        mock_run.return_value = MagicMock(stdout=_grok_stream(), stderr="", returncode=0)

        self.adapter.execute("prompt", effort="low", model="grok-4.6")

        called_cmd = mock_run.call_args.args[0]
        self.assertEqual(
            called_cmd,
            _GROK_BASE_CMD
            + ["--effort", "low", "-m", "grok-4.6", "-p", _GROK_PREAMBLE + "prompt"],
        )

    @patch("subprocess.run")
    def test_disallowed_tools_become_deny_rules(self, mock_run):
        mock_run.return_value = MagicMock(stdout=_grok_stream(), stderr="", returncode=0)

        self.adapter.execute("prompt", disallowed_tools=["Bash", "Write", "WebSearch"])

        called_cmd = mock_run.call_args.args[0]
        self.assertEqual(
            [called_cmd[i + 1] for i, tok in enumerate(called_cmd) if tok == "--deny"],
            ["Bash(*)", "Write(**)", "WebSearch(*)"],
        )

    @patch("subprocess.run")
    def test_agent_restriction_disables_subagents(self, mock_run):
        # "Agent" has no permission-rule equivalent; grok blocks subagents with a flag.
        mock_run.return_value = MagicMock(stdout=_grok_stream(), stderr="", returncode=0)

        self.adapter.execute("prompt", disallowed_tools=["Agent"])

        called_cmd = mock_run.call_args.args[0]
        self.assertIn("--no-subagents", called_cmd)
        self.assertNotIn("--deny", called_cmd)

    @patch("subprocess.run")
    def test_edit_and_notebook_edit_collapse_to_one_rule(self, mock_run):
        mock_run.return_value = MagicMock(stdout=_grok_stream(), stderr="", returncode=0)

        self.adapter.execute("prompt", disallowed_tools=["Edit", "NotebookEdit"])

        called_cmd = mock_run.call_args.args[0]
        self.assertEqual(called_cmd.count("--deny"), 1)
        self.assertIn("Edit(**)", called_cmd)

    @patch("subprocess.run")
    def test_unknown_tool_names_are_dropped(self, mock_run):
        mock_run.return_value = MagicMock(stdout=_grok_stream(), stderr="", returncode=0)

        self.adapter.execute("prompt", disallowed_tools=["Telepathy"])

        self.assertNotIn("--deny", mock_run.call_args.args[0])

    @patch("subprocess.run")
    def test_json_schema_is_never_passed_to_the_cli(self, mock_run):
        # supports_structured_output is False, so Titan should not be sending a
        # schema — and even if a caller does, the flag must stay off the command
        # line: it would cut the run short at the narration turn.
        mock_run.return_value = MagicMock(stdout=_grok_stream(), stderr="", returncode=0)

        self.adapter.execute("prompt", json_schema={"type": "object"})

        self.assertNotIn("--json-schema", mock_run.call_args.args[0])

    @patch("subprocess.run")
    def test_error_result_line_becomes_failed_response(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout=json.dumps(
                {
                    "type": "result",
                    "subtype": "error_during_execution",
                    "is_error": True,
                    "errors": ["Couldn't start session: no auth"],
                }
            ),
            stderr="",
            returncode=1,
        )

        response = self.adapter.execute("prompt")

        self.assertFalse(response.succeeded)
        self.assertEqual(response.stdout, "")
        self.assertIn("no auth", response.stderr)

    @patch("subprocess.run")
    def test_error_result_line_on_zero_exit_still_fails(self, mock_run):
        # grok exits 0 on some failed runs (observed with an unknown model id),
        # so is_error - not the exit code - decides.
        mock_run.return_value = MagicMock(
            stdout=json.dumps({"type": "result", "is_error": True, "errors": ["boom"]}),
            stderr="",
            returncode=0,
        )

        response = self.adapter.execute("prompt")

        self.assertEqual(response.exit_code, 1)
        self.assertIn("boom", response.stderr)
        self.assertEqual(response.stdout, "")

    @patch("subprocess.run")
    def test_non_json_stdout_is_passed_through_sanitized(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout="\x1b[32mplain output\x1b[0m\n", stderr="", returncode=0
        )

        response = self.adapter.execute("prompt")

        self.assertEqual(response.stdout, "plain output")

    @patch("subprocess.run")
    def test_execute_strips_ansi_codes_inside_result(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout=_grok_stream(result="\x1b[32mGreen text\x1b[0m\n"), stderr="", returncode=0
        )

        response = self.adapter.execute("prompt")

        self.assertEqual(response.stdout, "Green text")

    @patch("subprocess.run")
    def test_narration_is_not_part_of_the_answer(self, mock_run):
        # The whole reason for streaming-messages-json: --output-format json glues
        # every assistant turn together, so a commit-message run came back as
        # "I'll read the adapter first.feat: ..." (observed live).
        mock_run.return_value = MagicMock(
            stdout=_grok_stream(
                narration="I'll read the new adapter first.",
                result="feat: Add Grok Build CLI headless adapter",
            ),
            stderr="",
            returncode=0,
        )

        response = self.adapter.execute("write a commit message")

        self.assertEqual(response.stdout, "feat: Add Grok Build CLI headless adapter")

    @patch("subprocess.run")
    def test_stream_without_result_line_falls_back_to_last_assistant_text(self, mock_run):
        # A run killed mid-stream never emits the terminal line; the last assistant
        # message beats returning an empty success.
        stream = _grok_stream().splitlines()[:-1]
        mock_run.return_value = MagicMock(stdout="\n".join(stream), stderr="", returncode=0)

        response = self.adapter.execute("prompt")

        self.assertEqual(response.stdout, "I'll look into this first.")

    @patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="grok", timeout=60))
    def test_execute_timeout(self, _):
        response = self.adapter.execute("prompt", timeout=60)
        self.assertEqual(response.exit_code, 124)
        self.assertIn("timed out", response.stderr)

    @patch("subprocess.run", side_effect=FileNotFoundError)
    def test_execute_cli_not_found(self, _):
        response = self.adapter.execute("prompt")
        self.assertEqual(response.exit_code, 127)
        self.assertIn("not found", response.stderr)


# ── Registry ──────────────────────────────────────────────────────────────────

class TestHeadlessAdapterRegistry(unittest.TestCase):

    def test_registry_has_all_supported_clis(self):
        self.assertIn(SupportedCLI.CLAUDE, HEADLESS_ADAPTER_REGISTRY)
        self.assertIn(SupportedCLI.GEMINI, HEADLESS_ADAPTER_REGISTRY)
        self.assertIn(SupportedCLI.CODEX, HEADLESS_ADAPTER_REGISTRY)
        self.assertIn(SupportedCLI.OPENCODE, HEADLESS_ADAPTER_REGISTRY)
        self.assertIn(SupportedCLI.ANTIGRAVITY, HEADLESS_ADAPTER_REGISTRY)
        self.assertIn(SupportedCLI.GROK, HEADLESS_ADAPTER_REGISTRY)

    def test_get_headless_adapter_opencode(self):
        adapter = get_headless_adapter(SupportedCLI.OPENCODE)
        self.assertIsInstance(adapter, OpenCodeHeadlessAdapter)

    def test_get_headless_adapter_antigravity_plain_string(self):
        # StrEnum compatibility: "agy" == SupportedCLI.ANTIGRAVITY
        adapter = get_headless_adapter("agy")
        self.assertIsInstance(adapter, AntigravityHeadlessAdapter)

    def test_get_headless_adapter_grok(self):
        adapter = get_headless_adapter(SupportedCLI.GROK)
        self.assertIsInstance(adapter, GrokHeadlessAdapter)

    def test_get_headless_adapter_claude(self):
        adapter = get_headless_adapter(SupportedCLI.CLAUDE)
        self.assertIsInstance(adapter, ClaudeHeadlessAdapter)

    def test_get_headless_adapter_gemini(self):
        adapter = get_headless_adapter(SupportedCLI.GEMINI)
        self.assertIsInstance(adapter, GeminiHeadlessAdapter)

    def test_get_headless_adapter_plain_string(self):
        # StrEnum compatibility: "claude" == SupportedCLI.CLAUDE
        adapter = get_headless_adapter("claude")
        self.assertIsInstance(adapter, ClaudeHeadlessAdapter)

    def test_get_headless_adapter_unknown_raises(self):
        with self.assertRaises(ValueError) as ctx:
            get_headless_adapter("unknown_cli")
        self.assertIn("unknown_cli", str(ctx.exception))

    def test_get_headless_adapter_returns_new_instance_each_call(self):
        a1 = get_headless_adapter(SupportedCLI.CLAUDE)
        a2 = get_headless_adapter(SupportedCLI.CLAUDE)
        self.assertIsNot(a1, a2)


# ── Model listing ────────────────────────────────────────────────────────────

class TestModelListing(unittest.TestCase):
    """Each adapter answers "what can you run?" its own way, or says nothing."""

    def _stdout(self, text, returncode=0):
        return MagicMock(stdout=text, stderr="", returncode=returncode)

    def test_opencode_lists_qualified_ids_from_its_own_subcommand(self):
        listing = "anthropic/claude-sonnet-5\nopencode/big-pickle\n"
        with patch("subprocess.run", return_value=self._stdout(listing)) as run:
            models = OpenCodeHeadlessAdapter().list_models()

        self.assertEqual(run.call_args[0][0], ["opencode", "models"])
        self.assertEqual(
            [m.identifier for m in models],
            ["anthropic/claude-sonnet-5", "opencode/big-pickle"],
        )

    def test_antigravity_splits_identifier_from_its_human_label(self):
        listing = "Fetching available models...\ngemini-3.1-pro-high\tGemini 3.1 Pro (High)\n"
        with patch("subprocess.run", return_value=self._stdout(listing)):
            models = AntigravityHeadlessAdapter().list_models()

        self.assertEqual(len(models), 1)
        self.assertEqual(models[0].identifier, "gemini-3.1-pro-high")
        self.assertEqual(models[0].label, "Gemini 3.1 Pro (High)")

    def test_grok_keeps_only_the_bulleted_models_not_the_prose_around_them(self):
        listing = (
            "You are not authenticated.\n"
            "Default model: grok-4.6\n"
            "Available models:\n"
            "  * grok-4.6 (default)\n"
            "  * grok-code\n"
        )
        with patch("subprocess.run", return_value=self._stdout(listing)):
            models = GrokHeadlessAdapter().list_models()

        self.assertEqual([m.identifier for m in models], ["grok-4.6", "grok-code"])

    def test_a_failed_listing_is_no_models_rather_than_an_error(self):
        # A CLI that is not logged in, is offline, or has no such subcommand must leave
        # the caller with an empty list to fall back from, never an exception.
        for failure in (
            self._stdout("boom", returncode=1),
            subprocess.TimeoutExpired(cmd="opencode", timeout=20),
            FileNotFoundError("opencode"),
        ):
            with self.subTest(failure=failure):
                side_effect = None if not isinstance(failure, Exception) else failure
                with patch(
                    "subprocess.run",
                    return_value=failure if side_effect is None else None,
                    side_effect=side_effect,
                ):
                    self.assertEqual(OpenCodeHeadlessAdapter().list_models(), [])

    def test_claude_offers_aliases_without_shelling_out(self):
        with patch("subprocess.run") as run:
            models = ClaudeHeadlessAdapter().list_models()

        run.assert_not_called()
        self.assertIn("opus", [m.identifier for m in models])
        self.assertIn("sonnet", [m.identifier for m in models])

    def test_a_cli_that_publishes_nothing_returns_nothing(self):
        """Gemini alone now: codex reads its own cache file (see TestCodexModelListing).

        Codex used to belong here, and leaving it would have made this test depend on
        whether the machine running it happens to have a populated ~/.codex.
        """
        with patch("subprocess.run") as run:
            self.assertEqual(GeminiHeadlessAdapter().list_models(), [])
        run.assert_not_called()

    def test_codex_reads_its_cache_without_shelling_out(self):
        # The cache path is patched, not just subprocess: `codex_models_cache_path()`
        # reads Path.home() at call time, so without this the test depends on whether
        # the machine running it happens to have a populated ~/.codex.
        from titan_cli.external_cli.adapters import codex as codex_module

        with patch.object(codex_module, "codex_models_cache_path", lambda: Path("/nope")):
            with patch("subprocess.run") as run:
                CodexHeadlessAdapter().list_models()
        run.assert_not_called()

    def test_every_registered_adapter_can_be_asked(self):
        # The picker calls this on whichever CLI the user highlighted, so an adapter that
        # never implemented it would fail only for that one CLI, at the worst moment.
        for cli_name in HEADLESS_ADAPTER_REGISTRY:
            with self.subTest(cli=cli_name):
                adapter = get_headless_adapter(cli_name)
                with patch("subprocess.run", return_value=self._stdout("")):
                    self.assertIsInstance(adapter.list_models(), list)


class TestCodexModelListing:
    """
    Codex publishes its catalogue in a cache file it maintains itself (air-011).

    It has no listing subcommand - `codex --help` shows none and documents `-m/--model` as
    a free-form string - so this adapter used to offer nothing and every user typed the
    identifier by hand. It does keep `~/.codex/models_cache.json`, fetched and etagged by
    codex, which is a better source than a list hardcoded from the docs: on the machine
    this was written for, the docs' `gpt-5.3-codex` was not among the models the install
    actually offered.
    """

    @staticmethod
    def _cache(tmp_path, payload):
        path = tmp_path / "models_cache.json"
        path.write_text(json.dumps(payload))
        return path

    def _models(self, monkeypatch, path):
        from titan_cli.external_cli.adapters import codex as codex_module

        monkeypatch.setattr(codex_module, "codex_models_cache_path", lambda: path)
        return codex_module.CodexHeadlessAdapter().list_models()

    def test_listed_models_are_offered_with_their_description(self, tmp_path, monkeypatch):
        path = self._cache(
            tmp_path,
            {
                "models": [
                    {
                        "slug": "gpt-5.6-terra",
                        "display_name": "GPT-5.6-Terra",
                        "description": "Balanced agentic coding model.",
                        "visibility": "list",
                    }
                ]
            },
        )

        models = self._models(monkeypatch, path)

        assert [(m.identifier, m.label) for m in models] == [
            ("gpt-5.6-terra", "Balanced agentic coding model.")
        ]

    def test_hidden_models_are_not_offered(self, tmp_path, monkeypatch):
        """`codex-auto-review` and `gpt-reserve` are codex's own internals, not choices."""
        path = self._cache(
            tmp_path,
            {
                "models": [
                    {"slug": "gpt-5.6-sol", "visibility": "list"},
                    {"slug": "codex-auto-review", "visibility": "hide"},
                ]
            },
        )

        assert [m.identifier for m in self._models(monkeypatch, path)] == ["gpt-5.6-sol"]

    def test_a_missing_cache_offers_nothing_rather_than_failing(self, tmp_path, monkeypatch):
        """Codex may never have run. Typing an id by hand still works, as it does today."""
        assert self._models(monkeypatch, tmp_path / "absent.json") == []

    def test_a_corrupt_cache_offers_nothing_rather_than_failing(self, tmp_path, monkeypatch):
        path = tmp_path / "models_cache.json"
        path.write_text("{ not json")

        assert self._models(monkeypatch, path) == []

    def test_an_unexpected_shape_is_skipped_entry_by_entry(self, tmp_path, monkeypatch):
        """The file is codex's private format, not a contract: parse defensively."""
        path = self._cache(
            tmp_path,
            {
                "models": [
                    "not-a-dict",
                    {"display_name": "No slug", "visibility": "list"},
                    {"slug": "gpt-5.5", "visibility": "list"},
                ]
            },
        )

        assert [m.identifier for m in self._models(monkeypatch, path)] == ["gpt-5.5"]

    def test_the_label_falls_back_to_the_display_name(self, tmp_path, monkeypatch):
        path = self._cache(
            tmp_path,
            {"models": [{"slug": "gpt-5.5", "display_name": "GPT-5.5", "visibility": "list"}]},
        )

        assert self._models(monkeypatch, path)[0].label == "GPT-5.5"


class TestListingIsDecodeSafe(unittest.TestCase):
    """
    A CLI emitting non-UTF-8 must not raise through `model_listing_lines` (review).

    `text=True` decodes with the platform encoding, so a stray byte raises
    UnicodeDecodeError - a ValueError, which the old handler did not catch - through a
    function whose entire contract is that every failure flattens to "nothing to offer".
    """

    def test_the_subprocess_is_asked_to_replace_undecodable_bytes(self):
        from titan_cli.external_cli.adapters.base import model_listing_lines

        with patch("subprocess.run") as run:
            run.return_value = MagicMock(stdout="a\nb\n", returncode=0)
            model_listing_lines(["x", "models"])

        self.assertEqual(run.call_args.kwargs.get("errors"), "replace")

    def test_a_decode_error_still_yields_nothing(self):
        from titan_cli.external_cli.adapters.base import model_listing_lines

        error = UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")
        with patch("subprocess.run", side_effect=error):
            self.assertEqual(model_listing_lines(["x", "models"]), [])


class TestCodexSlugIsTypeChecked(unittest.TestCase):
    """A slug becomes a Textual option id, so a non-string must be skipped, not crash."""

    def test_a_non_string_slug_is_skipped(self):
        import json as _json
        import tempfile
        from pathlib import Path as _Path

        from titan_cli.external_cli.adapters import codex as codex_module

        with tempfile.TemporaryDirectory() as tmp:
            path = _Path(tmp) / "models_cache.json"
            path.write_text(
                _json.dumps(
                    {
                        "models": [
                            {"slug": 5, "visibility": "list"},
                            {"slug": "gpt-5.5", "visibility": "list"},
                        ]
                    }
                )
            )
            with patch.object(codex_module, "codex_models_cache_path", lambda: path):
                models = codex_module.CodexHeadlessAdapter().list_models()

        self.assertEqual([m.identifier for m in models], ["gpt-5.5"])


class TestCodexListingDegradesRatherThanDisappearing(unittest.TestCase):
    """
    `visibility` is read as a DENY-list (review, 2026-09-18).

    The only thing codex's private format guarantees is that its internals are marked
    `hide`. Requiring the positive `list` value would turn a future format that drops
    the key into "codex has no models" - indistinguishable from codex never having run.
    """

    @staticmethod
    def _models(payload):
        import json as _json
        import tempfile
        from pathlib import Path as _Path

        from titan_cli.external_cli.adapters import codex as codex_module

        with tempfile.TemporaryDirectory() as tmp:
            path = _Path(tmp) / "models_cache.json"
            path.write_text(_json.dumps(payload))
            with patch.object(codex_module, "codex_models_cache_path", lambda: path):
                return codex_module.CodexHeadlessAdapter().list_models()

    def test_an_entry_without_a_visibility_key_is_still_offered(self):
        models = self._models({"models": [{"slug": "gpt-6", "description": "new"}]})

        self.assertEqual([m.identifier for m in models], ["gpt-6"])

    def test_hidden_entries_are_still_excluded(self):
        models = self._models(
            {
                "models": [
                    {"slug": "gpt-5.6-sol", "visibility": "list"},
                    {"slug": "codex-auto-review", "visibility": "hide"},
                ]
            }
        )

        self.assertEqual([m.identifier for m in models], ["gpt-5.6-sol"])

    def test_a_repeated_slug_is_offered_once(self):
        """The slug is a Textual option id, and Textual raises on a duplicate."""
        models = self._models(
            {"models": [{"slug": "gpt-5.5"}, {"slug": "gpt-5.5"}, {"slug": "gpt-6"}]}
        )

        self.assertEqual([m.identifier for m in models], ["gpt-5.5", "gpt-6"])




class TestListingCannotStealTheTerminal(unittest.TestCase):
    """
    A CLI that prompts must not read the TUI's keystrokes (review, 2026-09-18).

    This runs under Textual, so a child inheriting stdin - a CLI that is not logged in,
    or opens a pager - swallows the user's typing and only relents at the 20s timeout.
    Listing models is explicitly "never a precondition", so the child gets EOF.
    """

    def test_stdin_is_closed_for_the_child(self):
        from titan_cli.external_cli.adapters.base import model_listing_lines

        with patch("subprocess.run") as run:
            run.return_value = MagicMock(stdout="", returncode=0)
            model_listing_lines(["grok", "models"])

        self.assertEqual(run.call_args.kwargs.get("stdin"), subprocess.DEVNULL)


if __name__ == "__main__":
    unittest.main()


# ── CliUsage and per-CLI usage reporting ─────────────────────────────────────
#
# Payload shapes below are not invented: each was captured 2026-09-22 by running the
# real CLI on this machine with a one-word prompt. That matters, because the whole
# point of these fields is to report what the CLI said rather than what Titan guessed.

class TestCliUsage(unittest.TestCase):

    def test_total_prefers_the_clis_own_figure(self):
        usage = CliUsage(input_tokens=10, output_tokens=2, reported_total_tokens=99)
        self.assertEqual(usage.total_tokens, 99)

    def test_total_falls_back_to_input_plus_output(self):
        self.assertEqual(CliUsage(input_tokens=10, output_tokens=2).total_tokens, 12)

    def test_total_is_none_when_a_side_is_missing(self):
        """A half-known total is worse than no total: it would silently understate."""
        self.assertIsNone(CliUsage(input_tokens=10).total_tokens)
        self.assertIsNone(CliUsage().total_tokens)

    def test_computed_total_excludes_cache_and_reasoning(self):
        """Each CLI folds these into its own figure differently, so summing them here
        would double-count on some CLIs and not others."""
        usage = CliUsage(
            input_tokens=10, output_tokens=2, cache_read_tokens=500,
            cache_write_tokens=700, reasoning_tokens=300,
        )
        self.assertEqual(usage.total_tokens, 12)

    def test_absent_figures_are_omitted_from_log_fields(self):
        """None means "the CLI did not say" — it must never be logged as a zero."""
        fields = CliUsage(input_tokens=10, source="probe").as_log_fields()
        self.assertEqual(fields, {"input_tokens": 10, "usage_source": "probe"})

    def test_log_fields_can_be_prefixed(self):
        fields = CliUsage(cost_usd=0.25).as_log_fields(prefix="call_")
        self.assertEqual(fields, {"call_cost_usd": 0.25})

    def test_has_cost_distinguishes_zero_from_unknown(self):
        self.assertTrue(CliUsage(cost_usd=0.0).has_cost)
        self.assertFalse(CliUsage().has_cost)


class TestClaudeUsageReporting(unittest.TestCase):
    """claude reports usage only inside the --output-format json envelope."""

    ENVELOPE = {
        "result": "ok",
        "is_error": False,
        "total_cost_usd": 0.25971625,
        "usage": {
            "input_tokens": 4597,
            "cache_creation_input_tokens": 37861,
            "cache_read_input_tokens": 0,
            "output_tokens": 4,
        },
        "modelUsage": {"claude-opus-5[1m]": {"costUSD": 0.25971625}},
    }

    def setUp(self):
        self.adapter = ClaudeHeadlessAdapter()

    @patch("subprocess.run")
    def test_plain_call_reports_usage_and_answer(self, mock_run):
        mock_run.return_value = MagicMock(stdout=json.dumps(self.ENVELOPE), stderr="", returncode=0)
        response = self.adapter.execute("prompt")

        self.assertEqual(response.stdout, "ok")
        self.assertEqual(response.usage.input_tokens, 4597)
        self.assertEqual(response.usage.output_tokens, 4)
        self.assertEqual(response.usage.cache_write_tokens, 37861)
        self.assertEqual(response.usage.cost_usd, 0.25971625)
        self.assertEqual(response.usage.model_reported, "claude-opus-5[1m]")

    @patch("subprocess.run")
    def test_thinking_is_reported_apart_from_the_answer(self, mock_run):
        """Thinking is counted inside output_tokens, and it is the part of the output
        that never reaches the parsed answer — so it is the only way to tell where a
        call's output went."""
        usage = dict(self.ENVELOPE["usage"], output_tokens=470, output_tokens_details={"thinking_tokens": 400})
        envelope = dict(self.ENVELOPE, usage=usage)
        mock_run.return_value = MagicMock(stdout=json.dumps(envelope), stderr="", returncode=0)
        response = self.adapter.execute("prompt")
        self.assertEqual(response.usage.output_tokens, 470)
        self.assertEqual(response.usage.reasoning_tokens, 400)

    @patch("subprocess.run")
    def test_reports_the_model_that_actually_ran_not_the_one_requested(self, mock_run):
        """A CLI silently falls back to its own default when a pin is unavailable, and
        that substitution is exactly what makes two runs incomparable."""
        mock_run.return_value = MagicMock(stdout=json.dumps(self.ENVELOPE), stderr="", returncode=0)
        response = self.adapter.execute("prompt", model="haiku")
        self.assertEqual(response.usage.model_reported, "claude-opus-5[1m]")

    @patch("subprocess.run")
    def test_several_models_report_none_rather_than_an_arbitrary_one(self, mock_run):
        envelope = dict(self.ENVELOPE, modelUsage={"claude-opus-5": {}, "claude-haiku-4-5": {}})
        mock_run.return_value = MagicMock(stdout=json.dumps(envelope), stderr="", returncode=0)
        response = self.adapter.execute("prompt")
        self.assertIsNone(response.usage.model_reported)
        self.assertEqual(response.usage.input_tokens, 4597)

    @patch("subprocess.run")
    def test_failed_call_still_reports_what_it_consumed(self, mock_run):
        """A failed turn costs money; hiding it would understate every review with a retry."""
        envelope = dict(self.ENVELOPE, is_error=True, result="overloaded")
        mock_run.return_value = MagicMock(stdout=json.dumps(envelope), stderr="", returncode=1)
        response = self.adapter.execute("prompt")

        self.assertFalse(response.succeeded)
        self.assertEqual(response.usage.cost_usd, 0.25971625)

    @patch("subprocess.run")
    def test_non_json_stdout_keeps_the_answer_and_reports_no_usage(self, mock_run):
        """A claude too old to emit the envelope must still return its answer."""
        mock_run.return_value = MagicMock(stdout="plain answer\n", stderr="", returncode=0)
        response = self.adapter.execute("prompt")

        self.assertEqual(response.stdout, "plain answer")
        self.assertIsNone(response.usage)

    @patch("subprocess.run")
    def test_structured_call_reports_usage_alongside_the_schema_answer(self, mock_run):
        envelope = dict(self.ENVELOPE, structured_output={"findings": []})
        mock_run.return_value = MagicMock(stdout=json.dumps(envelope), stderr="", returncode=0)
        response = self.adapter.execute("prompt", json_schema={"type": "object"})

        self.assertEqual(json.loads(response.stdout), {"findings": []})
        self.assertEqual(response.usage.cost_usd, 0.25971625)


class TestGrokUsageReporting(unittest.TestCase):
    """grok closes its stream with the same envelope shape claude emits."""

    def setUp(self):
        self.adapter = GrokHeadlessAdapter()

    def _stream(self, **overrides) -> str:
        result_event = {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": "ok",
            "total_cost_usd": 0.080964,
            "usage": {
                "input_tokens": 39966,
                "output_tokens": 76,
                "cache_read_input_tokens": 1152,
                "cache_creation_input_tokens": 0,
            },
            "modelUsage": {"grok-4.7": {"costUSD": 0.080964}},
        }
        result_event.update(overrides)
        return "\n".join([json.dumps({"type": "system", "model": "grok-4.7"}), json.dumps(result_event)])

    @patch("subprocess.run")
    def test_reports_usage_from_the_terminal_event(self, mock_run):
        mock_run.return_value = MagicMock(stdout=self._stream(), stderr="", returncode=0)
        response = self.adapter.execute("prompt")

        self.assertEqual(response.stdout, "ok")
        self.assertEqual(response.usage.input_tokens, 39966)
        self.assertEqual(response.usage.cache_read_tokens, 1152)
        self.assertEqual(response.usage.cost_usd, 0.080964)
        self.assertEqual(response.usage.model_reported, "grok-4.7")

    @patch("subprocess.run")
    def test_failed_run_still_reports_usage(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout=self._stream(is_error=True, errors=["rate limited"]), stderr="", returncode=0
        )
        response = self.adapter.execute("prompt")

        self.assertFalse(response.succeeded)
        self.assertEqual(response.usage.cost_usd, 0.080964)

    @patch("subprocess.run")
    def test_stream_without_a_terminal_event_reports_no_usage(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout=json.dumps({"type": "system", "model": "grok-4.7"}), stderr="", returncode=0
        )
        self.assertIsNone(self.adapter.execute("prompt").usage)


class TestCodexUsageReporting(unittest.TestCase):
    """codex reports counts on `turn.completed` and never reports a price."""

    def setUp(self):
        self.adapter = CodexHeadlessAdapter()

    STREAM = "\n".join([
        json.dumps({"type": "thread.started", "thread_id": "t1"}),
        json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": "ok"}}),
        json.dumps({"type": "turn.completed", "usage": {
            "input_tokens": 16783,
            "cached_input_tokens": 5888,
            "cache_write_input_tokens": 0,
            "output_tokens": 5,
            "reasoning_output_tokens": 0,
        }}),
    ])

    @patch("subprocess.run")
    def test_reports_counts_but_no_cost(self, mock_run):
        mock_run.return_value = MagicMock(stdout=self.STREAM, stderr="", returncode=0)
        response = self.adapter.execute("prompt")

        self.assertEqual(response.stdout, "ok")
        self.assertEqual(response.usage.input_tokens, 16783)
        self.assertEqual(response.usage.output_tokens, 5)
        self.assertEqual(response.usage.cache_read_tokens, 5888)
        self.assertIsNone(response.usage.cost_usd)
        self.assertFalse(response.usage.has_cost)

    @patch("subprocess.run")
    def test_stream_without_turn_completed_reports_no_usage(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout=json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": "ok"}}),
            stderr="", returncode=0,
        )
        response = self.adapter.execute("prompt")
        self.assertEqual(response.stdout, "ok")
        self.assertIsNone(response.usage)


class TestOpenCodeUsageReporting(unittest.TestCase):
    """opencode reports both counts and a resolved price on `step_finish`."""

    def setUp(self):
        self.adapter = OpenCodeHeadlessAdapter()

    def _stream(self, cost=0.0042) -> str:
        return "\n".join([
            json.dumps({"type": "text", "part": {"text": "ok"}}),
            json.dumps({"type": "step_finish", "part": {
                "tokens": {"total": 31582, "input": 31484, "output": 1, "reasoning": 97,
                           "cache": {"write": 0, "read": 12}},
                "cost": cost,
            }}),
        ])

    @patch("subprocess.run")
    def test_reports_counts_and_cost(self, mock_run):
        mock_run.return_value = MagicMock(stdout=self._stream(), stderr="", returncode=0)
        response = self.adapter.execute("prompt")

        self.assertEqual(response.stdout, "ok")
        self.assertEqual(response.usage.total_tokens, 31582)
        self.assertEqual(response.usage.reasoning_tokens, 97)
        self.assertEqual(response.usage.cache_read_tokens, 12)
        self.assertEqual(response.usage.cost_usd, 0.0042)

    @patch("subprocess.run")
    def test_a_reported_zero_cost_is_kept_as_zero(self, mock_run):
        """On a local or free model that zero is the true price, and turning it into
        None would make a free run indistinguishable from a silent CLI."""
        mock_run.return_value = MagicMock(stdout=self._stream(cost=0), stderr="", returncode=0)
        usage = self.adapter.execute("prompt").usage

        self.assertEqual(usage.cost_usd, 0.0)
        self.assertTrue(usage.has_cost)

    @patch("subprocess.run")
    def test_stream_without_step_finish_reports_no_usage(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout=json.dumps({"type": "text", "part": {"text": "ok"}}), stderr="", returncode=0
        )
        self.assertIsNone(self.adapter.execute("prompt").usage)


class TestAntigravityUsageReporting(unittest.TestCase):
    """agy reports counts in its envelope and never reports a price."""

    ENVELOPE = {
        "status": "SUCCESS",
        "response": "ok\n",
        "duration_seconds": 4.41,
        "num_turns": 1,
        "usage": {
            "input_tokens": 13520,
            "output_tokens": 278,
            "thinking_tokens": 277,
            "cache_read_tokens": 0,
            "total_tokens": 13798,
        },
    }

    def setUp(self):
        self.adapter = AntigravityHeadlessAdapter()

    @patch("titan_cli.external_cli.adapters.antigravity.AntigravityHeadlessAdapter._ensure_read_permissions")
    @patch("subprocess.run")
    def test_plain_call_reports_usage_and_answer(self, mock_run, _perms):
        mock_run.return_value = MagicMock(stdout=json.dumps(self.ENVELOPE), stderr="", returncode=0)
        response = self.adapter.execute("prompt")

        self.assertEqual(response.stdout, "ok")
        self.assertEqual(response.usage.total_tokens, 13798)
        self.assertEqual(response.usage.reasoning_tokens, 277)
        self.assertIsNone(response.usage.cost_usd)

    @patch("titan_cli.external_cli.adapters.antigravity.AntigravityHeadlessAdapter._ensure_read_permissions")
    @patch("subprocess.run")
    def test_non_json_stdout_keeps_the_answer_and_reports_no_usage(self, mock_run, _perms):
        mock_run.return_value = MagicMock(stdout="plain answer\n", stderr="", returncode=0)
        response = self.adapter.execute("prompt")

        self.assertEqual(response.stdout, "plain answer")
        self.assertIsNone(response.usage)


class TestGeminiReportsNoUsage(unittest.TestCase):
    """gemini emits no machine-readable output at all, so there is nothing to read.

    Asserted rather than assumed: `usage is None` is what makes a gemini review show
    up as cost-unknown instead of cost-free.
    """

    @patch("subprocess.run")
    def test_usage_is_absent(self, mock_run):
        mock_run.return_value = MagicMock(stdout="ok", stderr="", returncode=0)
        self.assertIsNone(GeminiHeadlessAdapter().execute("prompt").usage)
