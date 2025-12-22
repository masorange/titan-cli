# tests/engine/steps/test_ai_assistant_step.py
import unittest
from unittest.mock import patch, MagicMock
from titan_cli.utils.cli_launcher import CLILauncher

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

from titan_cli.engine.results import Skip, Success
from titan_cli.engine.steps.ai_assistant_step import execute_ai_assistant_step

class TestExecuteAIAssistantStep(unittest.TestCase):

    def setUp(self):
        self.mock_ctx = MagicMock()
        self.mock_ctx.data = {'test_failures': 'some error'}
        self.mock_step = MagicMock()
        self.mock_step.params = {'context_key': 'test_failures'}

    @patch('titan_cli.utils.cli_launcher.CLILauncher.is_available', return_value=False)
    def test_no_cli_available(self, mock_is_available):
        result = execute_ai_assistant_step(self.mock_step, self.mock_ctx)
        self.assertIsInstance(result, Skip)
        self.mock_ctx.ui.text.warning.assert_called_with("No AI coding assistant CLI found")

    @patch('titan_cli.utils.cli_launcher.CLILauncher.is_available', side_effect=lambda cli: cli == 'claude')
    @patch('titan_cli.utils.cli_launcher.CLILauncher.launch', return_value=0)
    def test_one_cli_available(self, mock_launch, mock_is_available):
        result = execute_ai_assistant_step(self.mock_step, self.mock_ctx)
        self.assertIsInstance(result, Success)
        mock_launch.assert_called_once()
        # Check that it launched claude
        self.assertEqual(mock_launch.call_args[1]['prompt'], 'some error')


    @patch('titan_cli.utils.cli_launcher.CLILauncher.is_available', return_value=True)
    @patch('titan_cli.utils.cli_launcher.CLILauncher.launch', return_value=0)
    def test_multiple_clis_available_select_one(self, mock_launch, mock_is_available):
        # Mock user selection
        mock_choice = MagicMock()
        mock_choice.action = 'gemini'
        self.mock_ctx.views.prompts.ask_menu.return_value = mock_choice

        result = execute_ai_assistant_step(self.mock_step, self.mock_ctx)
        self.assertIsInstance(result, Success)
        
        # Check that the menu was shown
        self.mock_ctx.views.prompts.ask_menu.assert_called_once()
        
        # Check that the launching message for Gemini was displayed
        from titan_cli.messages import msg
        self.mock_ctx.ui.text.info.assert_called_with(msg.AIAssistant.LAUNCHING_ASSISTANT.format(cli_name="Gemini CLI"))
        
        # Check that launch was called once
        mock_launch.assert_called_once()


    @patch('titan_cli.utils.cli_launcher.CLILauncher.is_available', return_value=True)
    def test_multiple_clis_available_cancel(self, mock_is_available):
        # Mock user cancelling selection
        self.mock_ctx.views.prompts.ask_menu.return_value = None

        result = execute_ai_assistant_step(self.mock_step, self.mock_ctx)
        self.assertIsInstance(result, Skip)
        self.mock_ctx.views.prompts.ask_menu.assert_called_once()

