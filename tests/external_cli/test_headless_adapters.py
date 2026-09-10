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
from titan_cli.external_cli.adapters.base import HeadlessResponse, SupportedCLI
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
            ["claude", "--print", "review this"],
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
            ["claude", "--print", "--output-format", "json", "--json-schema", json.dumps(schema), "review this"],
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
    def test_execute_with_disallowed_tools_adds_flag(self, mock_run):
        mock_run.return_value = MagicMock(stdout="ok", stderr="", returncode=0)
        self.adapter.execute(
            "review this", cwd="/tmp", timeout=45, disallowed_tools=["Bash", "Agent"]
        )

        mock_run.assert_called_once_with(
            ["claude", "--print", "--disallowedTools=Bash,Agent", "review this"],
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
            ["claude", "--print", "--effort", "medium", "review this"],
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
            ["agy", "--print", _HEADLESS_PREAMBLE + "review this"],
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


if __name__ == "__main__":
    unittest.main()
