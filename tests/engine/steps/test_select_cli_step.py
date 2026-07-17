# tests/engine/steps/test_select_cli_step.py
import unittest
from unittest.mock import patch, MagicMock

from titan_cli.engine.results import Success
from titan_cli.engine.steps.select_cli_step import execute_select_cli_step


class TestExecuteSelectCliStep(unittest.TestCase):

    def setUp(self):
        self.mock_step = MagicMock()
        self.mock_step.params = {}
        self.mock_ctx = MagicMock()
        self.mock_ctx.textual = MagicMock()

    @patch('shutil.which', return_value=None)
    def test_no_cli_available(self, mock_which):
        result = execute_select_cli_step(self.mock_step, self.mock_ctx)

        self.assertIsInstance(result, Success)
        self.assertEqual(result.metadata['cli_preference'], "")
        self.mock_ctx.textual.begin_step.assert_called_once()
        self.mock_ctx.textual.end_step.assert_called_once_with("skip")

    @patch('shutil.which', side_effect=lambda cli: '/usr/bin/gemini' if cli == 'gemini' else None)
    def test_offers_only_available_clis(self, mock_which):
        self.mock_ctx.textual.ask_option = MagicMock(return_value="gemini")

        result = execute_select_cli_step(self.mock_step, self.mock_ctx)

        self.assertIsInstance(result, Success)
        self.assertEqual(result.metadata['cli_preference'], "gemini")

        self.mock_ctx.textual.ask_option.assert_called_once()
        call_kwargs = self.mock_ctx.textual.ask_option.call_args.kwargs
        option_values = [opt.value for opt in call_kwargs['options']]
        self.assertEqual(option_values, ["gemini"])

    @patch('shutil.which', return_value='/usr/bin/some_cli')
    def test_user_cancels_selection(self, mock_which):
        self.mock_ctx.textual.ask_option = MagicMock(return_value=None)

        result = execute_select_cli_step(self.mock_step, self.mock_ctx)

        self.assertIsInstance(result, Success)
        self.assertEqual(result.metadata['cli_preference'], "")
        self.mock_ctx.textual.end_step.assert_called_once_with("skip")

    @patch('shutil.which', return_value='/usr/bin/some_cli')
    def test_uses_custom_question_param(self, mock_which):
        self.mock_step.params = {"question": "Pick your assistant:"}
        self.mock_ctx.textual.ask_option = MagicMock(return_value="claude")

        result = execute_select_cli_step(self.mock_step, self.mock_ctx)

        self.assertIsInstance(result, Success)
        call_args = self.mock_ctx.textual.ask_option.call_args.args
        self.assertEqual(call_args[0], "Pick your assistant:")


if __name__ == '__main__':
    unittest.main()
