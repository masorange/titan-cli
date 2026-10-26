from unittest.mock import Mock

from titan_cli.core.result import ClientError
from titan_cli.engine.results import Error
from titan_plugin_git.steps.push_step import create_git_push_step


def test_a_failure_before_the_push_is_shown_inside_the_step():
    ctx = Mock()
    ctx.get.return_value = None
    ctx.git.get_current_branch.return_value = ClientError(error_message="fatal: ambiguous argument 'HEAD'")

    result = create_git_push_step(ctx)

    assert isinstance(result, Error)
    ctx.textual.error_text.assert_called_once_with(result.message)
    assert "ambiguous argument 'HEAD'" in result.message
    ctx.textual.end_step.assert_called_once_with("error")
