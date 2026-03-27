"""
Tests for titan_plugin_github.steps.ai_cli_initial_review_step.
"""

import unittest
from unittest.mock import MagicMock, patch

from titan_cli.engine.results import Error, Skip, Success
from titan_cli.external_cli.adapters.base import HeadlessResponse, SupportedCLI


_MODULE = "titan_plugin_github.steps.ai_cli_initial_review_step"


def _make_ctx(data: dict | None = None) -> MagicMock:
    ctx = MagicMock()
    ctx.data = data or {}
    ctx.get = lambda key, default=None: ctx.data.get(key, default)
    # loading() must behave as a context manager
    ctx.textual.loading.return_value.__enter__ = MagicMock(return_value=None)
    ctx.textual.loading.return_value.__exit__ = MagicMock(return_value=False)
    return ctx


def _make_adapter(stdout: str = "## Summary\nLooks good.", exit_code: int = 0, available: bool = True) -> MagicMock:
    adapter = MagicMock()
    adapter.cli_name = SupportedCLI.CLAUDE
    adapter.is_available.return_value = available
    adapter.execute.return_value = HeadlessResponse(
        stdout=stdout,
        stderr="",
        exit_code=exit_code,
    )
    return adapter


def _make_pr() -> MagicMock:
    pr = MagicMock()
    pr.number = 42
    pr.title = "Fix something"
    return pr


# ── Missing / invalid data ────────────────────────────────────────────────────

class TestMissingData(unittest.TestCase):

    def test_no_pr_returns_skip(self):
        from titan_plugin_github.steps.ai_cli_initial_review_step import ai_cli_initial_review
        ctx = _make_ctx({})
        result = ai_cli_initial_review(ctx)
        self.assertIsInstance(result, Skip)

    def test_custom_pr_key_missing_returns_skip(self):
        from titan_plugin_github.steps.ai_cli_initial_review_step import ai_cli_initial_review
        ctx = _make_ctx({"pr_key": "my_pr"})  # key set but value absent
        result = ai_cli_initial_review(ctx)
        self.assertIsInstance(result, Skip)

    def test_invalid_cli_preference_returns_error(self):
        from titan_plugin_github.steps.ai_cli_initial_review_step import ai_cli_initial_review
        ctx = _make_ctx({"selected_pr": _make_pr(), "cli_preference": "openai"})
        result = ai_cli_initial_review(ctx)
        self.assertIsInstance(result, Error)


# ── Adapter resolution ────────────────────────────────────────────────────────

class TestAdapterResolution(unittest.TestCase):

    @patch(f"{_MODULE}.get_headless_adapter")
    @patch(f"{_MODULE}.HEADLESS_ADAPTER_REGISTRY", {SupportedCLI.CLAUDE: None})
    def test_auto_uses_first_available(self, mock_get):
        from titan_plugin_github.steps.ai_cli_initial_review_step import ai_cli_initial_review
        mock_get.return_value = _make_adapter()
        ctx = _make_ctx({"selected_pr": _make_pr()})
        result = ai_cli_initial_review(ctx)
        self.assertIsInstance(result, Success)

    @patch(f"{_MODULE}.get_headless_adapter")
    @patch(f"{_MODULE}.HEADLESS_ADAPTER_REGISTRY", {SupportedCLI.CLAUDE: None})
    def test_no_adapter_available_returns_error(self, mock_get):
        from titan_plugin_github.steps.ai_cli_initial_review_step import ai_cli_initial_review
        mock_get.return_value = _make_adapter(available=False)
        ctx = _make_ctx({"selected_pr": _make_pr()})
        result = ai_cli_initial_review(ctx)
        self.assertIsInstance(result, Error)

    @patch(f"{_MODULE}.get_headless_adapter")
    def test_specific_cli_not_installed_returns_error(self, mock_get):
        from titan_plugin_github.steps.ai_cli_initial_review_step import ai_cli_initial_review
        mock_get.return_value = _make_adapter(available=False)
        ctx = _make_ctx({"selected_pr": _make_pr(), "cli_preference": "claude"})
        result = ai_cli_initial_review(ctx)
        self.assertIsInstance(result, Error)

    @patch(f"{_MODULE}.get_headless_adapter", side_effect=ValueError("unknown"))
    def test_specific_cli_not_in_registry_returns_error(self, _):
        from titan_plugin_github.steps.ai_cli_initial_review_step import ai_cli_initial_review
        ctx = _make_ctx({"selected_pr": _make_pr(), "cli_preference": "ollama"})
        result = ai_cli_initial_review(ctx)
        self.assertIsInstance(result, Error)


# ── Happy path ────────────────────────────────────────────────────────────────

class TestHappyPath(unittest.TestCase):

    @patch(f"{_MODULE}.parse_cli_review_output")
    @patch(f"{_MODULE}.build_initial_review_prompt_headless", return_value="prompt text")
    @patch(f"{_MODULE}.get_headless_adapter")
    @patch(f"{_MODULE}.HEADLESS_ADAPTER_REGISTRY", {SupportedCLI.CLAUDE: None})
    def test_stores_findings_and_markdown(self, mock_get, _build, mock_parse):
        from titan_plugin_github.steps.ai_cli_initial_review_step import ai_cli_initial_review
        from titan_plugin_github.models.view import UIReviewSuggestion

        mock_get.return_value = _make_adapter(stdout="## Summary\n\n### 🔴 CRITICAL: Bug")
        mock_parse.return_value = (
            "## Summary",
            [UIReviewSuggestion(file_path="", line=None, body="Bug", severity="critical")],
        )

        ctx = _make_ctx({"selected_pr": _make_pr(), "pr_diff": "diff text"})
        result = ai_cli_initial_review(ctx)

        self.assertIsInstance(result, Success)
        self.assertIn("initial_review_suggestions", ctx.data)
        self.assertIn("initial_review_markdown", ctx.data)
        self.assertEqual(len(ctx.data["initial_review_suggestions"]), 1)
        self.assertIn("CRITICAL", ctx.data["initial_review_markdown"])

    @patch(f"{_MODULE}.parse_cli_review_output", return_value=("", []))
    @patch(f"{_MODULE}.build_initial_review_prompt_headless", return_value="prompt")
    @patch(f"{_MODULE}.get_headless_adapter")
    @patch(f"{_MODULE}.HEADLESS_ADAPTER_REGISTRY", {SupportedCLI.CLAUDE: None})
    def test_no_findings_still_succeeds(self, mock_get, _build, _parse):
        from titan_plugin_github.steps.ai_cli_initial_review_step import ai_cli_initial_review
        mock_get.return_value = _make_adapter(stdout="All looks good.")
        ctx = _make_ctx({"selected_pr": _make_pr()})
        result = ai_cli_initial_review(ctx)
        self.assertIsInstance(result, Success)
        self.assertEqual(ctx.data["initial_review_suggestions"], [])

    @patch(f"{_MODULE}.parse_cli_review_output", return_value=("", []))
    @patch(f"{_MODULE}.build_initial_review_prompt_headless", return_value="prompt")
    @patch(f"{_MODULE}.get_headless_adapter")
    @patch(f"{_MODULE}.HEADLESS_ADAPTER_REGISTRY", {SupportedCLI.CLAUDE: None})
    def test_custom_output_key(self, mock_get, _build, _parse):
        from titan_plugin_github.steps.ai_cli_initial_review_step import ai_cli_initial_review
        mock_get.return_value = _make_adapter()
        ctx = _make_ctx({"selected_pr": _make_pr(), "output_key": "my_review"})
        ai_cli_initial_review(ctx)
        self.assertIn("my_review_suggestions", ctx.data)
        self.assertIn("my_review_markdown", ctx.data)


# ── Adapter failure ───────────────────────────────────────────────────────────

class TestAdapterFailure(unittest.TestCase):

    @patch(f"{_MODULE}.build_initial_review_prompt_headless", return_value="prompt")
    @patch(f"{_MODULE}.get_headless_adapter")
    @patch(f"{_MODULE}.HEADLESS_ADAPTER_REGISTRY", {SupportedCLI.CLAUDE: None})
    def test_failed_execution_returns_error(self, mock_get, _build):
        from titan_plugin_github.steps.ai_cli_initial_review_step import ai_cli_initial_review
        mock_get.return_value = _make_adapter(stdout="", exit_code=1)
        ctx = _make_ctx({"selected_pr": _make_pr()})
        result = ai_cli_initial_review(ctx)
        self.assertIsInstance(result, Error)


# ── Prompt building ───────────────────────────────────────────────────────────

class TestPromptBuilding(unittest.TestCase):

    @patch(f"{_MODULE}.parse_cli_review_output", return_value=("", []))
    @patch(f"{_MODULE}.build_initial_review_prompt_headless")
    @patch(f"{_MODULE}.get_headless_adapter")
    @patch(f"{_MODULE}.HEADLESS_ADAPTER_REGISTRY", {SupportedCLI.CLAUDE: None})
    def test_diff_and_threads_passed_to_prompt_builder(self, mock_get, mock_build, _parse):
        from titan_plugin_github.steps.ai_cli_initial_review_step import ai_cli_initial_review
        mock_get.return_value = _make_adapter()
        mock_build.return_value = "built prompt"

        pr = _make_pr()
        threads = [MagicMock()]
        ctx = _make_ctx({
            "selected_pr": pr,
            "pr_diff": "full diff",
            "review_threads": threads,
        })
        ai_cli_initial_review(ctx)

        mock_build.assert_called_once_with(pr=pr, diff="full diff", comments=threads, pr_template=None)

    @patch(f"{_MODULE}.build_initial_review_prompt_headless", side_effect=RuntimeError("boom"))
    @patch(f"{_MODULE}.get_headless_adapter")
    @patch(f"{_MODULE}.HEADLESS_ADAPTER_REGISTRY", {SupportedCLI.CLAUDE: None})
    def test_prompt_build_failure_returns_error(self, mock_get, _build):
        from titan_plugin_github.steps.ai_cli_initial_review_step import ai_cli_initial_review
        mock_get.return_value = _make_adapter()
        ctx = _make_ctx({"selected_pr": _make_pr()})
        result = ai_cli_initial_review(ctx)
        self.assertIsInstance(result, Error)


if __name__ == "__main__":
    unittest.main()
