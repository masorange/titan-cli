"""The prompt that asks an AI what an issue asks for."""
from titan_plugin_jira.models.view import UIJiraComment
from titan_plugin_jira.operations import build_issue_summary_prompt


def test_the_summary_prompt_carries_the_issue_and_its_comments_in_the_issues_language(sample_ui_issue):
    comment = UIJiraComment("1", "Ana", None, "Mejor solo en Android", "01/01/2026 10:00:00", None)

    prompt, system = build_issue_summary_prompt(sample_ui_issue, [comment])

    assert sample_ui_issue.key in prompt and sample_ui_issue.summary in prompt
    assert "Mejor solo en Android" in prompt
    assert "latest word wins" in prompt
    assert "same language the issue is written in" in system
