"""
Unit tests for model mappers

Tests the transformation from Network models (raw API) to UI models (pre-formatted).
"""

from titan_plugin_jira.models import (
    NetworkJiraIssue,
    NetworkJiraFields,
    NetworkJiraStatus,
    NetworkJiraStatusCategory,
    NetworkJiraIssueType,
    NetworkJiraPriority,
    NetworkJiraProject,
    from_network_issue,
    from_network_project,
)


def test_from_network_issue_basic(sample_network_issue):
    """Test basic issue mapping from Network to UI model"""
    ui_issue = from_network_issue(sample_network_issue)

    # Basic fields
    assert ui_issue.key == "TEST-123"
    assert ui_issue.id == "10123"
    assert ui_issue.summary == "Sample test issue"
    assert ui_issue.description == "This is a test issue description"

    # Status
    assert ui_issue.status == "In Progress"
    assert ui_issue.status_category == "In Progress"
    assert ui_issue.status_icon in ["🔵", "🟡", "⚪"]  # Valid status icons

    # Issue type
    assert ui_issue.issue_type == "Bug"
    assert ui_issue.issue_type_icon == "🐛"

    # Priority
    assert ui_issue.priority == "High"
    assert ui_issue.priority_icon == "🟠"  # High → 🟠 (not 🔴)

    # Users
    assert ui_issue.assignee == "John Doe"
    assert ui_issue.assignee_email == "john.doe@example.com"
    assert ui_issue.reporter == "Jane Doe"

    # Lists
    assert ui_issue.labels == ["test", "bug"]
    assert ui_issue.components == []
    assert ui_issue.fix_versions == []

    # Metadata
    assert ui_issue.is_subtask is False
    assert ui_issue.parent_key is None
    assert ui_issue.subtask_count == 0


def test_from_network_issue_formatted_dates(sample_network_issue):
    """Test that dates are formatted correctly"""
    ui_issue = from_network_issue(sample_network_issue)

    # Should be formatted as DD/MM/YYYY HH:MM:SS
    assert ui_issue.formatted_created_at is not None
    assert "/" in ui_issue.formatted_created_at
    assert ":" in ui_issue.formatted_created_at

    assert ui_issue.formatted_updated_at is not None
    assert "/" in ui_issue.formatted_updated_at


def test_from_network_issue_status_icons():
    """Test that status icons are mapped correctly"""

    # Test "To Do" status
    status_category_todo = NetworkJiraStatusCategory(
        id="2",
        name="To Do",
        key="new",
        colorName="blue-gray"
    )
    status_todo = NetworkJiraStatus(
        id="1",
        name="To Do",
        statusCategory=status_category_todo
    )
    fields_todo = NetworkJiraFields(
        summary="Test",
        status=status_todo
    )
    issue_todo = NetworkJiraIssue(key="TEST-1", id="1", fields=fields_todo)
    ui_todo = from_network_issue(issue_todo)
    assert ui_todo.status_icon == "🟡"  # key="new" → 🟡

    # Test "In Progress" status
    status_category_progress = NetworkJiraStatusCategory(
        id="4",
        name="In Progress",
        key="indeterminate",
        colorName="yellow"
    )
    status_progress = NetworkJiraStatus(
        id="3",
        name="In Progress",
        statusCategory=status_category_progress
    )
    fields_progress = NetworkJiraFields(
        summary="Test",
        status=status_progress
    )
    issue_progress = NetworkJiraIssue(key="TEST-2", id="2", fields=fields_progress)
    ui_progress = from_network_issue(issue_progress)
    assert ui_progress.status_icon == "🔵"

    # Test "Done" status
    status_category_done = NetworkJiraStatusCategory(
        id="3",
        name="Done",
        key="done",
        colorName="green"
    )
    status_done = NetworkJiraStatus(
        id="10",
        name="Done",
        statusCategory=status_category_done
    )
    fields_done = NetworkJiraFields(
        summary="Test",
        status=status_done
    )
    issue_done = NetworkJiraIssue(key="TEST-3", id="3", fields=fields_done)
    ui_done = from_network_issue(issue_done)
    assert ui_done.status_icon == "🟢"


def test_from_network_issue_issue_type_icons():
    """Test that issue type icons are mapped correctly"""

    # Test Bug icon
    issue_type_bug = NetworkJiraIssueType(id="1", name="Bug", subtask=False)
    fields_bug = NetworkJiraFields(summary="Test", issuetype=issue_type_bug)
    issue_bug = NetworkJiraIssue(key="TEST-1", id="1", fields=fields_bug)
    ui_bug = from_network_issue(issue_bug)
    assert ui_bug.issue_type_icon == "🐛"

    # Test Story icon
    issue_type_story = NetworkJiraIssueType(id="2", name="Story", subtask=False)
    fields_story = NetworkJiraFields(summary="Test", issuetype=issue_type_story)
    issue_story = NetworkJiraIssue(key="TEST-2", id="2", fields=fields_story)
    ui_story = from_network_issue(issue_story)
    assert ui_story.issue_type_icon == "📖"

    # Test Task icon
    issue_type_task = NetworkJiraIssueType(id="3", name="Task", subtask=False)
    fields_task = NetworkJiraFields(summary="Test", issuetype=issue_type_task)
    issue_task = NetworkJiraIssue(key="TEST-3", id="3", fields=fields_task)
    ui_task = from_network_issue(issue_task)
    assert ui_task.issue_type_icon == "✅"


def test_from_network_issue_priority_icons():
    """Test that priority icons are mapped correctly"""

    # Test High priority
    priority_high = NetworkJiraPriority(id="2", name="High")
    fields_high = NetworkJiraFields(summary="Test", priority=priority_high)
    issue_high = NetworkJiraIssue(key="TEST-1", id="1", fields=fields_high)
    ui_high = from_network_issue(issue_high)
    assert ui_high.priority_icon == "🟠"  # High → 🟠

    # Test Medium priority
    priority_medium = NetworkJiraPriority(id="3", name="Medium")
    fields_medium = NetworkJiraFields(summary="Test", priority=priority_medium)
    issue_medium = NetworkJiraIssue(key="TEST-2", id="2", fields=fields_medium)
    ui_medium = from_network_issue(issue_medium)
    assert ui_medium.priority_icon == "🟡"

    # Test Low priority
    priority_low = NetworkJiraPriority(id="4", name="Low")
    fields_low = NetworkJiraFields(summary="Test", priority=priority_low)
    issue_low = NetworkJiraIssue(key="TEST-3", id="3", fields=fields_low)
    ui_low = from_network_issue(issue_low)
    assert ui_low.priority_icon == "🟢"


def test_from_network_issue_unassigned():
    """Test issue with no assignee"""

    fields = NetworkJiraFields(
        summary="Unassigned issue",
        assignee=None
    )
    issue = NetworkJiraIssue(key="TEST-1", id="1", fields=fields)
    ui_issue = from_network_issue(issue)

    assert ui_issue.assignee == "Unassigned"
    assert ui_issue.assignee_email is None


def test_from_network_issue_no_description():
    """Test issue with no description"""

    fields = NetworkJiraFields(
        summary="Issue with no description",
        description=None
    )
    issue = NetworkJiraIssue(key="TEST-1", id="1", fields=fields)
    ui_issue = from_network_issue(issue)

    assert ui_issue.description == "No description"


def test_from_network_issue_subtask():
    """Test subtask mapping"""

    issue_type = NetworkJiraIssueType(id="5", name="Sub-task", subtask=True)
    fields = NetworkJiraFields(
        summary="A subtask",
        issuetype=issue_type,
        parent={"key": "TEST-100", "fields": {"summary": "Parent issue"}}
    )
    issue = NetworkJiraIssue(key="TEST-101", id="101", fields=fields)
    ui_issue = from_network_issue(issue)

    assert ui_issue.is_subtask is True
    assert ui_issue.parent_key == "TEST-100"


def test_from_network_issue_with_subtasks():
    """Test issue with subtasks"""

    fields = NetworkJiraFields(
        summary="Parent issue",
        subtasks=[
            {"key": "TEST-101"},
            {"key": "TEST-102"},
            {"key": "TEST-103"}
        ]
    )
    issue = NetworkJiraIssue(key="TEST-100", id="100", fields=fields)
    ui_issue = from_network_issue(issue)

    assert ui_issue.subtask_count == 3


def test_from_network_project_basic(sample_network_project):
    """Test basic project mapping from Network to UI model"""
    ui_project = from_network_project(sample_network_project)

    # Basic fields
    assert ui_project.id == "10000"
    assert ui_project.key == "TEST"
    assert ui_project.name == "Test Project"
    assert ui_project.description == "A test project"
    assert ui_project.project_type == "software"

    # Lead
    assert ui_project.lead_name == "Project Lead"

    # Issue types (just names)
    assert ui_project.issue_types == ["Bug", "Story"]


def test_from_network_project_no_description():
    """Test project with no description"""

    project = NetworkJiraProject(
        id="10000",
        key="TEST",
        name="Test Project",
        description=None
    )
    ui_project = from_network_project(project)

    assert ui_project.description == "No description"


def test_from_network_project_no_lead():
    """Test project with no lead"""

    project = NetworkJiraProject(
        id="10000",
        key="TEST",
        name="Test Project",
        lead=None
    )
    ui_project = from_network_project(project)

    assert ui_project.lead_name == "Unknown"


def test_from_network_project_no_issue_types():
    """Test project with no issue types"""

    project = NetworkJiraProject(
        id="10000",
        key="TEST",
        name="Test Project",
        issueTypes=None
    )
    ui_project = from_network_project(project)

    assert ui_project.issue_types == []


def test_adf_to_plain_text():
    """Test ADF (Atlassian Document Format) to plain text conversion"""
    from titan_plugin_jira.models.formatting import extract_text_from_adf

    # Simple paragraph
    adf = {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "Hello world"}
                ]
            }
        ]
    }
    result = extract_text_from_adf(adf)
    assert "Hello world" in result

    # Multiple paragraphs
    adf_multi = {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": "First paragraph"}]
            },
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": "Second paragraph"}]
            }
        ]
    }
    result_multi = extract_text_from_adf(adf_multi)
    assert "First paragraph" in result_multi
    assert "Second paragraph" in result_multi

    # Invalid/empty ADF
    assert extract_text_from_adf(None) == ""
    assert extract_text_from_adf({}) == ""
    assert extract_text_from_adf("not a dict") == "not a dict"  # Returns as-is for strings
