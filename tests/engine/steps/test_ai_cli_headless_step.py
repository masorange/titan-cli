"""
Tests for engine.steps.ai_cli_headless_step.
"""

import unittest
from unittest.mock import MagicMock, patch

from titan_cli.engine.results import Error, Skip, Success
from titan_cli.engine.steps.ai_cli_headless_step import execute_ai_cli_headless_step
from titan_cli.external_cli.adapters.base import HeadlessResponse, SupportedCLI


def _make_ctx(data: dict | None = None, with_textual: bool = True) -> MagicMock:
    ctx = MagicMock()
    ctx.data = data or {}
    ctx.textual = MagicMock() if with_textual else None
    ctx.get = lambda key, default=None: ctx.data.get(key, default)
    return ctx


def _make_step(params: dict) -> MagicMock:
    step = MagicMock()
    step.name = "Test Headless Step"
    step.params = params
    return step


def _make_adapter(stdout: str = "result", exit_code: int = 0, available: bool = True) -> MagicMock:
    adapter = MagicMock()
    adapter.cli_name = SupportedCLI.CLAUDE
    adapter.is_available.return_value = available
    adapter.execute.return_value = HeadlessResponse(
        stdout=stdout,
        stderr="",
        exit_code=exit_code,
    )
    return adapter


# ── Parameter validation ──────────────────────────────────────────────────────

class TestParamValidation(unittest.TestCase):

    def test_missing_context_key_returns_error(self):
        ctx = _make_ctx({"stuff": "data"})
        step = _make_step({})
        result = execute_ai_cli_headless_step(step, ctx)
        self.assertIsInstance(result, Error)

    def test_invalid_cli_preference_returns_error(self):
        ctx = _make_ctx({"ctx": "data"})
        step = _make_step({"context_key": "ctx", "cli_preference": "openai"})
        result = execute_ai_cli_headless_step(step, ctx)
        self.assertIsInstance(result, Error)

    def test_empty_context_data_returns_skip(self):
        ctx = _make_ctx({})
        step = _make_step({"context_key": "missing_key"})
        result = execute_ai_cli_headless_step(step, ctx)
        self.assertIsInstance(result, Skip)

    def test_none_context_data_returns_skip(self):
        ctx = _make_ctx({"ctx": None})
        step = _make_step({"context_key": "ctx"})
        result = execute_ai_cli_headless_step(step, ctx)
        self.assertIsInstance(result, Skip)


# ── Auto mode ─────────────────────────────────────────────────────────────────

class TestAutoMode(unittest.TestCase):

    @patch("titan_cli.engine.steps.ai_cli_headless_step.get_headless_adapter")
    @patch("titan_cli.engine.steps.ai_cli_headless_step.HEADLESS_ADAPTER_REGISTRY",
           {SupportedCLI.CLAUDE: None, SupportedCLI.GEMINI: None})
    def test_auto_uses_first_available(self, mock_get_adapter):
        adapter = _make_adapter(stdout="AI analysis", exit_code=0)
        mock_get_adapter.return_value = adapter

        ctx = _make_ctx({"pr": "diff content"})
        step = _make_step({"context_key": "pr", "cli_preference": "auto"})
        result = execute_ai_cli_headless_step(step, ctx)

        self.assertIsInstance(result, Success)
        self.assertEqual(ctx.data["ai_cli_stdout"], "AI analysis")
        self.assertEqual(ctx.data["ai_cli_exit_code"], 0)

    @patch("titan_cli.engine.steps.ai_cli_headless_step.get_headless_adapter")
    @patch("titan_cli.engine.steps.ai_cli_headless_step.HEADLESS_ADAPTER_REGISTRY",
           {SupportedCLI.CLAUDE: None, SupportedCLI.GEMINI: None})
    def test_auto_skips_unavailable_clis(self, mock_get_adapter):
        unavailable = _make_adapter(available=False)
        available = _make_adapter(stdout="result", exit_code=0, available=True)
        available.cli_name = SupportedCLI.GEMINI
        mock_get_adapter.side_effect = [unavailable, available]

        ctx = _make_ctx({"pr": "diff"})
        step = _make_step({"context_key": "pr", "cli_preference": "auto"})
        result = execute_ai_cli_headless_step(step, ctx)

        self.assertIsInstance(result, Success)

    @patch("titan_cli.engine.steps.ai_cli_headless_step.get_headless_adapter")
    @patch("titan_cli.engine.steps.ai_cli_headless_step.HEADLESS_ADAPTER_REGISTRY",
           {SupportedCLI.CLAUDE: None})
    def test_auto_returns_error_if_none_available(self, mock_get_adapter):
        mock_get_adapter.return_value = _make_adapter(available=False)

        ctx = _make_ctx({"pr": "diff"})
        step = _make_step({"context_key": "pr", "cli_preference": "auto"})
        result = execute_ai_cli_headless_step(step, ctx)

        self.assertIsInstance(result, Error)


# ── Specific CLI mode ─────────────────────────────────────────────────────────

class TestSpecificCLIMode(unittest.TestCase):

    @patch("titan_cli.engine.steps.ai_cli_headless_step.get_headless_adapter")
    def test_specific_cli_success(self, mock_get_adapter):
        mock_get_adapter.return_value = _make_adapter(stdout="response", exit_code=0)

        ctx = _make_ctx({"pr": "diff"})
        step = _make_step({"context_key": "pr", "cli_preference": "claude"})
        result = execute_ai_cli_headless_step(step, ctx)

        self.assertIsInstance(result, Success)
        mock_get_adapter.assert_called_once_with("claude")

    @patch("titan_cli.engine.steps.ai_cli_headless_step.get_headless_adapter")
    def test_specific_cli_not_installed_returns_error(self, mock_get_adapter):
        mock_get_adapter.return_value = _make_adapter(available=False)

        ctx = _make_ctx({"pr": "diff"})
        step = _make_step({"context_key": "pr", "cli_preference": "claude"})
        result = execute_ai_cli_headless_step(step, ctx)

        self.assertIsInstance(result, Error)

    @patch("titan_cli.engine.steps.ai_cli_headless_step.get_headless_adapter",
           side_effect=ValueError("No headless adapter registered for 'ollama'"))
    def test_specific_cli_not_in_registry_returns_error(self, _):
        ctx = _make_ctx({"pr": "diff"})
        step = _make_step({"context_key": "pr", "cli_preference": "ollama"})
        result = execute_ai_cli_headless_step(step, ctx)

        self.assertIsInstance(result, Error)


# ── Output storage ────────────────────────────────────────────────────────────

class TestOutputStorage(unittest.TestCase):

    @patch("titan_cli.engine.steps.ai_cli_headless_step.get_headless_adapter")
    @patch("titan_cli.engine.steps.ai_cli_headless_step.HEADLESS_ADAPTER_REGISTRY",
           {SupportedCLI.CLAUDE: None})
    def test_default_output_key_prefix(self, mock_get_adapter):
        mock_get_adapter.return_value = _make_adapter(stdout="out", exit_code=0)

        ctx = _make_ctx({"pr": "diff"})
        step = _make_step({"context_key": "pr"})
        execute_ai_cli_headless_step(step, ctx)

        self.assertIn("ai_cli_stdout", ctx.data)
        self.assertIn("ai_cli_stderr", ctx.data)
        self.assertIn("ai_cli_exit_code", ctx.data)

    @patch("titan_cli.engine.steps.ai_cli_headless_step.get_headless_adapter")
    @patch("titan_cli.engine.steps.ai_cli_headless_step.HEADLESS_ADAPTER_REGISTRY",
           {SupportedCLI.CLAUDE: None})
    def test_custom_output_key_prefix(self, mock_get_adapter):
        mock_get_adapter.return_value = _make_adapter(stdout="review", exit_code=0)

        ctx = _make_ctx({"pr": "diff"})
        step = _make_step({"context_key": "pr", "output_key": "review"})
        execute_ai_cli_headless_step(step, ctx)

        self.assertIn("review_stdout", ctx.data)
        self.assertEqual(ctx.data["review_stdout"], "review")
        self.assertEqual(ctx.data["review_exit_code"], 0)

    @patch("titan_cli.engine.steps.ai_cli_headless_step.get_headless_adapter")
    @patch("titan_cli.engine.steps.ai_cli_headless_step.HEADLESS_ADAPTER_REGISTRY",
           {SupportedCLI.CLAUDE: None})
    def test_failed_response_still_stored(self, mock_get_adapter):
        adapter = _make_adapter(stdout="partial", exit_code=1)
        adapter.execute.return_value = HeadlessResponse(stdout="partial", stderr="err", exit_code=1)
        mock_get_adapter.return_value = adapter

        ctx = _make_ctx({"pr": "diff"})
        step = _make_step({"context_key": "pr"})
        result = execute_ai_cli_headless_step(step, ctx)

        self.assertIsInstance(result, Error)
        self.assertEqual(ctx.data["ai_cli_exit_code"], 1)
        self.assertEqual(ctx.data["ai_cli_stdout"], "partial")


# ── Prompt building ───────────────────────────────────────────────────────────

class TestPromptBuilding(unittest.TestCase):

    @patch("titan_cli.engine.steps.ai_cli_headless_step.get_headless_adapter")
    @patch("titan_cli.engine.steps.ai_cli_headless_step.HEADLESS_ADAPTER_REGISTRY",
           {SupportedCLI.CLAUDE: None})
    def test_prompt_template_interpolated(self, mock_get_adapter):
        adapter = _make_adapter(stdout="ok", exit_code=0)
        mock_get_adapter.return_value = adapter

        ctx = _make_ctx({"pr": "my diff"})
        step = _make_step({
            "context_key": "pr",
            "prompt_template": "Review:\n{context}",
        })
        execute_ai_cli_headless_step(step, ctx)

        call_args = adapter.execute.call_args
        prompt_used = call_args[0][0]
        self.assertIn("Review:\n", prompt_used)
        self.assertIn("my diff", prompt_used)

    @patch("titan_cli.engine.steps.ai_cli_headless_step.get_headless_adapter")
    @patch("titan_cli.engine.steps.ai_cli_headless_step.HEADLESS_ADAPTER_REGISTRY",
           {SupportedCLI.CLAUDE: None})
    def test_dict_context_serialized_as_json(self, mock_get_adapter):
        adapter = _make_adapter(stdout="ok", exit_code=0)
        mock_get_adapter.return_value = adapter

        ctx = _make_ctx({"pr": {"key": "value"}})
        step = _make_step({"context_key": "pr"})
        execute_ai_cli_headless_step(step, ctx)

        call_args = adapter.execute.call_args
        prompt_used = call_args[0][0]
        self.assertIn('"key"', prompt_used)
        self.assertIn('"value"', prompt_used)


# ── Works without textual ─────────────────────────────────────────────────────

class TestWithoutTextual(unittest.TestCase):

    @patch("titan_cli.engine.steps.ai_cli_headless_step.get_headless_adapter")
    @patch("titan_cli.engine.steps.ai_cli_headless_step.HEADLESS_ADAPTER_REGISTRY",
           {SupportedCLI.CLAUDE: None})
    def test_succeeds_without_textual(self, mock_get_adapter):
        mock_get_adapter.return_value = _make_adapter(stdout="result", exit_code=0)

        ctx = _make_ctx({"pr": "diff"}, with_textual=False)
        step = _make_step({"context_key": "pr"})
        result = execute_ai_cli_headless_step(step, ctx)

        self.assertIsInstance(result, Success)

    @patch("titan_cli.engine.steps.ai_cli_headless_step.get_headless_adapter")
    @patch("titan_cli.engine.steps.ai_cli_headless_step.HEADLESS_ADAPTER_REGISTRY",
           {SupportedCLI.CLAUDE: None})
    def test_fails_without_textual(self, mock_get_adapter):
        mock_get_adapter.return_value = _make_adapter(available=False)

        ctx = _make_ctx({"pr": "diff"}, with_textual=False)
        step = _make_step({"context_key": "pr"})
        result = execute_ai_cli_headless_step(step, ctx)

        self.assertIsInstance(result, Error)


if __name__ == "__main__":
    unittest.main()
