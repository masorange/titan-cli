# tests/engine/steps/test_ai_assistant_step.py
import unittest
from unittest.mock import patch, MagicMock
from titan_cli.external_cli.launcher import CLILauncher
from titan_cli.engine.results import Skip, Success
from titan_cli.engine.steps.ai_assistant_step import execute_ai_assistant_step

class TestCLILauncher(unittest.TestCase):

    @patch('shutil.which')
    def test_is_available_when_present(self, mock_which):
        mock_which.return_value = '/usr/bin/claude'
        launcher = CLILauncher('claude')
        self.assertTrue(launcher.is_available())

    @patch('shutil.which')
    def test_is_available_when_not_present(self, mock_which):
        mock_which.return_value = None
        launcher = CLILauncher('nonexistent')
        self.assertFalse(launcher.is_available())

    @patch('subprocess.run')
    def test_launch_no_prompt(self, mock_run):
        launcher = CLILauncher('my-cli')
        launcher.launch()
        mock_run.assert_called_once_with(
            ['my-cli'],
            stdin=unittest.mock.ANY,
            stdout=unittest.mock.ANY,
            stderr=unittest.mock.ANY,
            cwd=None
        )

    @patch('subprocess.run')
    def test_launch_with_positional_prompt(self, mock_run):
        launcher = CLILauncher('claude', prompt_flag=None)
        launcher.launch(prompt="hello")
        mock_run.assert_called_once_with(
            ['claude', 'hello'],
            stdin=unittest.mock.ANY,
            stdout=unittest.mock.ANY,
            stderr=unittest.mock.ANY,
            cwd=None
        )

    @patch('subprocess.run')
    def test_launch_with_flag_prompt(self, mock_run):
        launcher = CLILauncher('gemini', prompt_flag='-i')
        launcher.launch(prompt="world")
        mock_run.assert_called_once_with(
            ['gemini', '-i', 'world'],
            stdin=unittest.mock.ANY,
            stdout=unittest.mock.ANY,
            stderr=unittest.mock.ANY,
            cwd=None
        )

class TestExecuteAIAssistantStep(unittest.TestCase):

    def setUp(self):
        self.mock_ctx = MagicMock()
        self.mock_ctx.data = {'test_failures': 'some error'}
        self.mock_step = MagicMock()
        self.mock_step.params = {'context_key': 'test_failures'}
        # Mock textual UI components
        self.mock_ctx.textual = MagicMock()
        self.mock_ctx.textual.launch_external_cli = MagicMock(return_value=0)

    @patch('shutil.which', return_value=None)
    def test_no_cli_available(self, mock_which):
        result = execute_ai_assistant_step(self.mock_step, self.mock_ctx)
        self.assertIsInstance(result, Skip)
        # Verify that a warning panel was mounted
        self.mock_ctx.textual.mount.assert_called_once()

    @patch('shutil.which', side_effect=lambda cli: '/usr/bin/claude' if cli == 'claude' else None)
    def test_one_cli_available(self, mock_which):
        # Mock the confirmation dialog to return True
        self.mock_ctx.textual.ask_confirm = MagicMock(return_value=True)

        result = execute_ai_assistant_step(self.mock_step, self.mock_ctx)
        self.assertIsInstance(result, Success)

        # Verify launch_external_cli was called with the expected prompt
        self.mock_ctx.textual.launch_external_cli.assert_called_once()
        call_kwargs = self.mock_ctx.textual.launch_external_cli.call_args.kwargs
        self.assertEqual(call_kwargs['cli_name'], 'claude')
        self.assertIn('some error', call_kwargs['prompt'])


    @patch('shutil.which', return_value='/usr/bin/some_cli')
    def test_multiple_clis_available_select_one(self, mock_which):
        # Mock user confirming and selecting option 2 (gemini)
        self.mock_ctx.textual.ask_confirm = MagicMock(return_value=True)
        self.mock_ctx.textual.ask_text = MagicMock(return_value="2")

        result = execute_ai_assistant_step(self.mock_step, self.mock_ctx)
        self.assertIsInstance(result, Success)

        # Check that the user was asked to select an option
        self.mock_ctx.textual.ask_text.assert_called_once()

        # Check that launch_external_cli was called with gemini
        self.mock_ctx.textual.launch_external_cli.assert_called_once()
        call_kwargs = self.mock_ctx.textual.launch_external_cli.call_args.kwargs
        self.assertEqual(call_kwargs['cli_name'], 'gemini')


    @patch('shutil.which', return_value='/usr/bin/some_cli')
    def test_multiple_clis_available_cancel(self, mock_which):
        # Mock user confirming but then cancelling selection (empty input)
        self.mock_ctx.textual.ask_confirm = MagicMock(return_value=True)
        self.mock_ctx.textual.ask_text = MagicMock(return_value="")

        result = execute_ai_assistant_step(self.mock_step, self.mock_ctx)
        self.assertIsInstance(result, Skip)

        # Verify that ask_text was called to get user's selection
        self.mock_ctx.textual.ask_text.assert_called_once()

        # Verify that launch_external_cli was NOT called
        self.mock_ctx.textual.launch_external_cli.assert_not_called()

if __name__ == '__main__':
    unittest.main()