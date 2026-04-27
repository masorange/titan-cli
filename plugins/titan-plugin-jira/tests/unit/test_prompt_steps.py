from types import SimpleNamespace
from unittest.mock import MagicMock

from titan_cli.engine import Error, Success, WorkflowContext
from titan_plugin_jira.steps.prompt_select_issue_step import prompt_select_issue_step


def test_prompt_select_issue_step_uses_interaction_port():
    issue = SimpleNamespace(key="ECAPP-123", summary="Improve login flow")
    ctx = WorkflowContext(secrets=MagicMock(), data={"jira_issues": [issue]})
    ctx.textual = None
    ctx.interaction = MagicMock()
    ctx.interaction.ask_text.return_value = "1"

    result = prompt_select_issue_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata["jira_issue_key"] == "ECAPP-123"
    assert result.metadata["selected_issue"] is issue
    ctx.interaction.begin_step.assert_called_once()
    ctx.interaction.end_step.assert_called_once_with("success")


def test_prompt_select_issue_step_rejects_invalid_interaction_input():
    issue = SimpleNamespace(key="ECAPP-123", summary="Improve login flow")
    ctx = WorkflowContext(secrets=MagicMock(), data={"jira_issues": [issue]})
    ctx.textual = None
    ctx.interaction = MagicMock()
    ctx.interaction.ask_text.return_value = "abc"

    result = prompt_select_issue_step(ctx)

    assert isinstance(result, Error)
    assert "not a number" in result.message
    ctx.interaction.end_step.assert_called_once_with("error")
