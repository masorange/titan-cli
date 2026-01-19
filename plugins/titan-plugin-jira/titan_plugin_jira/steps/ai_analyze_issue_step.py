"""
AI-powered JIRA issue analysis step
"""

from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error, Skip
from titan_cli.ui.tui.widgets import Panel
from ..messages import msg
from ..agents import JiraAgent
from ..formatters import IssueAnalysisMarkdownFormatter


def ai_analyze_issue_requirements_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Analyze JIRA issue requirements using AI.

    Provides intelligent analysis of:
    - Summary and description breakdown
    - Acceptance criteria extraction
    - Technical requirements identification
    - Potential challenges and risks
    - Implementation suggestions
    - Missing information detection

    Inputs (from ctx.data):
        jira_issue (JiraTicket): JIRA issue object to analyze
        selected_issue (JiraTicket, optional): Alternative source

    Outputs (saved to ctx.data):
        ai_analysis (str): AI-generated analysis
        analysis_sections (dict): Structured analysis breakdown
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    # Check if AI is available
    if not ctx.ai or not ctx.ai.is_available():
        ctx.textual.mount(Panel(msg.Steps.AIIssue.AI_NOT_CONFIGURED_SKIP, panel_type="info"))
        return Skip(msg.Steps.AIIssue.AI_NOT_CONFIGURED)

    # Get issue to analyze
    issue = ctx.get("jira_issue") or ctx.get("selected_issue")
    if not issue:
        ctx.textual.mount(Panel(msg.Steps.AIIssue.NO_ISSUE_FOUND, panel_type="error"))
        return Error(msg.Steps.AIIssue.NO_ISSUE_FOUND)

    # Create JiraAgent instance and analyze issue with loading indicator
    with ctx.textual.loading(msg.Steps.AIIssue.ANALYZING):
        jira_agent = JiraAgent(ctx.ai, ctx.jira)
        analysis = jira_agent.analyze_issue(
            issue_key=issue.key,
            include_subtasks=True,
            include_comments=False,
            include_linked_issues=False
        )

    # Build formatted analysis for display
    # Use template from config if specified, otherwise use built-in formatter
    template_name = jira_agent.config.template if jira_agent.config.template else None
    formatter = IssueAnalysisMarkdownFormatter(template_path=template_name)
    ai_analysis = formatter.format(analysis)

    # Display analysis
    ctx.textual.text("")
    ctx.textual.text("AI Analysis Results", markup="bold cyan")
    ctx.textual.text("")

    # Show issue header
    ctx.textual.text(f"{issue.key}: {issue.summary}", markup="bold")
    ctx.textual.text(f"Type: {issue.issue_type} | Status: {issue.status} | Priority: {issue.priority}", markup="dim")
    ctx.textual.text("")

    # Show AI analysis as markdown
    ctx.textual.markdown(ai_analysis)

    # Show token usage
    if analysis.total_tokens_used > 0:
        ctx.textual.text(f"Tokens used: {analysis.total_tokens_used}", markup="dim")

    # Save structured analysis to context
    ctx.set("ai_analysis_structured", {
        "functional_requirements": analysis.functional_requirements,
        "non_functional_requirements": analysis.non_functional_requirements,
        "acceptance_criteria": analysis.acceptance_criteria,
        "technical_approach": analysis.technical_approach,
        "dependencies": analysis.dependencies,
        "risks": analysis.risks,
        "edge_cases": analysis.edge_cases,
        "suggested_subtasks": analysis.suggested_subtasks,
        "complexity_score": analysis.complexity_score,
        "estimated_effort": analysis.estimated_effort
    })

    return Success(
        "AI analysis completed",
        metadata={
            "ai_analysis": ai_analysis,
            "analyzed_issue_key": issue.key,
            "tokens_used": analysis.total_tokens_used,
            "complexity": analysis.complexity_score,
            "effort": analysis.estimated_effort
        }
    )


__all__ = ["ai_analyze_issue_requirements_step"]
