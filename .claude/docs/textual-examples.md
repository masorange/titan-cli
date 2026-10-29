# Textual Step Examples

Read this when you want a worked step to copy: panel, input, AI with loading, table, error handling, plus the real steps to imitate. API: [textual-api.md](textual-api.md).

---

## Complete Examples

### Example 1: Simple Step with Panel

```python
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error, Skip, Exit

def simple_step(ctx: WorkflowContext) -> WorkflowResult:
    """A simple step that shows a message."""
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    message = ctx.get("message", "Hello, World!")

    ctx.textual.panel(message, panel_type="success")

    return Success("Message displayed")
```

### Example 2: Step with User Input

```python
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error, Skip, Exit, Skip

def prompt_for_title_step(ctx: WorkflowContext) -> WorkflowResult:
    """Prompt user for a title."""
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    # Skip if already exists
    if ctx.get("title"):
        return Skip("Title already provided")

    try:
        title = ctx.textual.ask_text("Enter title:", default="")

        if not title:
            return Error("Title cannot be empty")

        ctx.textual.panel(f"Title set: {title}", panel_type="success")

        return Success("Title captured", metadata={"title": title})

    except (KeyboardInterrupt, EOFError):
        return Error("User cancelled")
```

### Example 3: Step with AI and Loading Indicator

```python
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error, Skip, Exit, Skip

def ai_analyze_step(ctx: WorkflowContext) -> WorkflowResult:
    """Analyze content using AI."""
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    # Check AI availability
    if not ctx.ai or not ctx.ai.is_available():
        ctx.textual.panel("AI not configured", panel_type="info")
        return Skip("AI not configured")

    content = ctx.get("content")
    if not content:
        ctx.textual.panel("No content to analyze", panel_type="error")
        return Error("No content to analyze")

    # Analyze with loading indicator
    from titan_cli.ai.models import AIMessage

    with ctx.textual.loading("Analyzing content with AI..."):
        response = ctx.ai.generate([
            AIMessage(role="user", content=f"Analyze this: {content}")
        ])

    analysis = response.content.strip()

    # Show result
    ctx.textual.text("")
    ctx.textual.bold_primary_text("AI Analysis:")
    ctx.textual.text("")
    ctx.textual.markdown(analysis)

    # Confirm usage
    use_analysis = ctx.textual.ask_confirm(
        "Use this analysis?",
        default=True
    )

    if not use_analysis:
        ctx.textual.warning_text("Analysis rejected")
        return Skip("User rejected analysis")

    ctx.textual.panel("Analysis accepted", panel_type="success")

    return Success("Analysis completed", metadata={"analysis": analysis})
```

### Example 4: Step with Table Results

```python
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error, Skip, Exit

def search_issues_step(ctx: WorkflowContext) -> WorkflowResult:
    """Search and display issues."""
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    if not ctx.jira:
        ctx.textual.panel("JIRA client not available", panel_type="error")
        return Error("JIRA client not available")

    query = ctx.get("query", "status = Open")

    # Search with loading
    with ctx.textual.loading("Searching issues..."):
        issues = ctx.jira.search_tickets(jql=query, max_results=50)

    if not issues:
        ctx.textual.panel("No issues found", panel_type="info")
        return Success("No issues found", metadata={"issues": []})

    # Show result
    ctx.textual.panel(f"Found {len(issues)} issues", panel_type="success")
    ctx.textual.text("")

    # Prepare table
    headers = ["#", "Key", "Status", "Summary"]
    rows = []
    for i, issue in enumerate(issues, 1):
        rows.append([
            str(i),
            issue.key,
            issue.status or "Unknown",
            (issue.summary or "No summary")[:60]
        ])

    # Render table
    ctx.textual.table(headers=headers, rows=rows, title="Issues")

    return Success(
        f"Found {len(issues)} issues",
        metadata={"issues": issues}
    )
```

### Example 5: Step with Error Handling

```python
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error, Skip, Exit
import requests

def fetch_data_step(ctx: WorkflowContext) -> WorkflowResult:
    """Fetch data from API."""
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    url = ctx.get("url")
    if not url:
        ctx.textual.panel("URL is required", panel_type="error")
        return Error("URL is required")

    try:
        # Show info
        ctx.textual.dim_text(f"Fetching from: {url}")

        # Fetch with loading
        with ctx.textual.loading(f"Fetching data from {url}..."):
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()

        # Success
        ctx.textual.panel(
            f"Successfully fetched {len(data)} records",
            panel_type="success"
        )

        return Success("Data fetched", metadata={"data": data})

    except requests.RequestException as e:
        error_msg = f"Failed to fetch data: {e}"
        ctx.textual.panel(error_msg, panel_type="error")
        return Error(error_msg)
    except ValueError as e:
        error_msg = f"Invalid JSON response: {e}"
        ctx.textual.panel(error_msg, panel_type="error")
        return Error(error_msg)
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        error_msg = f"Unexpected error: {e}\n\n{error_detail}"
        ctx.textual.panel(error_msg, panel_type="error")
        return Error(error_msg)
```

---

## Reference Files

### Core Components
- **TextualComponents API**: `/titan_cli/ui/tui/textual_components.py`
- **Widgets**: `/titan_cli/ui/tui/widgets/`
- **Executor**: `/titan_cli/ui/tui/textual_workflow_executor.py`
- **Execution Screen**: `/titan_cli/ui/tui/screens/workflow_execution.py`

### Real Step Examples

**GitHub Plugin**:
- `/plugins/titan-plugin-github/titan_plugin_github/steps/github_prompt_steps.py`
- `/plugins/titan-plugin-github/titan_plugin_github/steps/ai_pr_step.py`
- `/plugins/titan-plugin-github/titan_plugin_github/steps/create_pr_step.py`

**Git Plugin**:
- `/plugins/titan-plugin-git/titan_plugin_git/steps/ai_commit_message_step.py`
- `/plugins/titan-plugin-git/titan_plugin_git/steps/commit_step.py`

**Jira Plugin**:
- `/plugins/titan-plugin-jira/titan_plugin_jira/steps/search_saved_query_step.py`
- `/plugins/titan-plugin-jira/titan_plugin_jira/steps/prompt_select_issue_step.py`
- `/plugins/titan-plugin-jira/titan_plugin_jira/steps/get_issue_step.py`
- `/plugins/titan-plugin-jira/titan_plugin_jira/steps/ai_analyze_issue_step.py`
