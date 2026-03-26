"""
Tests for external_cli.adapters — HeadlessCliAdapter implementations and registry.
"""

import subprocess
import unittest
from unittest.mock import MagicMock, patch

from titan_cli.external_cli.adapters.base import HeadlessResponse, SupportedCLI
from titan_cli.external_cli.adapters.claude import ClaudeHeadlessAdapter
from titan_cli.external_cli.adapters.gemini import GeminiHeadlessAdapter
from titan_cli.external_cli.adapters.registry import (
    HEADLESS_ADAPTER_REGISTRY,
    get_headless_adapter,
)


# ── SupportedCLI ─────────────────────────────────────────────────────────────

class TestSupportedCLI(unittest.TestCase):

    def test_values_match_cli_commands(self):
        self.assertEqual(SupportedCLI.CLAUDE, "claude")
        self.assertEqual(SupportedCLI.GEMINI, "gemini")

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

    @patch("subprocess.run")
    def test_execute_passes_prompt_with_flag(self, mock_run):
        mock_run.return_value = MagicMock(stdout="response\n", stderr="", returncode=0)
        self.adapter.execute("my prompt", cwd="/repo", timeout=45)

        mock_run.assert_called_once_with(
            ["gemini", "-i", "my prompt"],
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            cwd="/repo",
            timeout=45,
        )

    @patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="gemini", timeout=60))
    def test_execute_timeout(self, _):
        response = self.adapter.execute("prompt", timeout=60)
        self.assertEqual(response.exit_code, 124)

    @patch("subprocess.run", side_effect=FileNotFoundError)
    def test_execute_cli_not_found(self, _):
        response = self.adapter.execute("prompt")
        self.assertEqual(response.exit_code, 127)


# ── Registry ──────────────────────────────────────────────────────────────────

class TestHeadlessAdapterRegistry(unittest.TestCase):

    def test_registry_has_claude_and_gemini(self):
        self.assertIn(SupportedCLI.CLAUDE, HEADLESS_ADAPTER_REGISTRY)
        self.assertIn(SupportedCLI.GEMINI, HEADLESS_ADAPTER_REGISTRY)

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
