---
name: titan-operations
description: Extract business logic to operations layer - pure functions that work with UI models. Use when refactoring steps or creating reusable business logic.
keywords: operations, business logic, pure functions, refactoring, extract logic
---

# Titan Operations Skill

Complete guide for implementing the Operations Pattern in Titan CLI plugins.

## When to Use This Skill

Invoke this skill when the user requests:
- **Extract business logic**: "Extract this logic to operations", "Move this to operations"
- **Refactor step**: "This step has too much logic", "Make this step cleaner"
- **Create reusable logic**: "I need to reuse this logic in multiple steps"
- **Testing**: "I need to test this business logic", "How do I test this?"

## What Are Operations?

**Operations** are pure business logic functions that:
- ✅ Work with UI models (not dicts or network models)
- ✅ Return data directly or raise exceptions
- ✅ Are UI-agnostic (no `ctx.textual` calls)
- ✅ Are easily testable with unit tests
- ✅ Can be reused across multiple steps

### Why Operations?

**Before Operations:**
```python
# ❌ BAD: Business logic mixed with UI
def my_step(ctx):
    ctx.textual.begin_step("Process Data")

    # Business logic mixed with UI
    data = ctx.get("input")
    if not data:
        ctx.textual.error_text("No data")
        return Error("No data")

    # Complex parsing logic
    items = []
    for line in data.split('\n'):
        if '|' in line:
            parts = line.split('|')
            items.append(parts[0].strip())

    # More business logic...
    filtered = [x for x in items if len(x) > 5]

    ctx.textual.success_text(f"Processed {len(filtered)} items")
    return Success("Done", metadata={"items": filtered})
```

**After Operations:**
```python
# ✅ GOOD: Clean separation
def my_step(ctx):
    ctx.textual.begin_step("Process Data")

    data = ctx.get("input")
    if not data:
        ctx.textual.error_text("No data")
        return Error("No data")

    # Call tested business logic
    items = parse_data(data)
    filtered = filter_items(items, min_length=5)

    ctx.textual.success_text(f"Processed {len(filtered)} items")
    return Success("Done", metadata={"items": filtered})
```

## Architecture Overview

### Directory Structure

```
plugins/titan-plugin-{name}/
├── titan_plugin_{name}/
│   ├── operations/              # Pure business logic
│   │   ├── __init__.py         # Export all operations
│   │   ├── {domain}_operations.py
│   │   └── ...
│   ├── steps/                   # UI orchestration only
│   ├── clients/                 # Data access
│   └── ...
├── tests/
│   ├── operations/              # Unit tests for operations
│   │   └── test_{domain}_operations.py
│   └── ...
```

### Layer Responsibilities

| Layer | Returns | Responsibility | Can Import | Cannot Import |
|-------|---------|----------------|------------|---------------|
| **Operations** | `UIModel` or raises | Business logic, pure functions | Client facade only | Services, Network, ctx.textual |
| **Steps** | `WorkflowResult` | UI orchestration | Operations, ctx.textual | Services, Network |
| **Client** | `ClientResult[UIModel]` | Public API facade | Services, Network | Should not call operations |
| **Services** | `ClientResult[UIModel]` | Data access | Network, Models | Operations, Steps |

## What Operations Can Do

Operations are for **pure business logic**:

### ✅ Extract to Operations

1. **Data parsing and transformation**
   ```python
   def parse_comma_separated_list(input_string: str) -> List[str]:
       """Parse comma-separated string into list of trimmed items."""
       if not input_string or not input_string.strip():
           return []
       return [item.strip() for item in input_string.split(",") if item.strip()]
   ```

2. **Validation logic**
   ```python
   def validate_issue_fields(
       summary: str,
       description: str,
       issue_type: str
   ) -> Tuple[bool, Optional[str]]:
       """Validate issue fields. Returns (is_valid, error_message)."""
       if not summary or len(summary) < 3:
           return False, "Summary must be at least 3 characters"
       if issue_type not in ["Bug", "Task", "Story"]:
           return False, f"Invalid issue type: {issue_type}"
       return True, None
   ```

3. **Calculations and algorithms**
   ```python
   def calculate_priority_score(
       issue: UIJiraIssue,
       priority_weights: Dict[str, int]
   ) -> int:
       """Calculate priority score based on issue fields."""
       base_score = priority_weights.get(issue.priority_name, 0)
       if issue.is_blocked:
           base_score -= 10
       if issue.is_overdue:
           base_score += 20
       return max(0, base_score)
   ```

4. **Filtering and sorting**
   ```python
   def filter_active_resources(
       resources: List[UIResource]
   ) -> List[UIResource]:
       """Filter and sort active resources by name."""
       active = [r for r in resources if r.status_display == "Active"]
       return sorted(active, key=lambda r: r.name)
   ```

5. **Complex client orchestration**
   ```python
   def fetch_pr_threads(
       client: GitHubClient,
       pr_number: int
   ) -> List[UIReviewThread]:
       """
       Fetch all review threads for PR with comments.

       Args:
           client: GitHub client instance
           pr_number: PR number

       Returns:
           List of review threads with comments

       Raises:
           OperationError: If fetch fails
       """
       # Fetch PR review threads
       threads_result = client.get_review_threads(pr_number)
       match threads_result:
           case ClientSuccess(data=threads):
               return threads
           case ClientError(error_message=err):
               raise OperationError(f"Failed to fetch threads: {err}")
   ```

### ❌ Keep in Steps

These should **NOT** be in operations:

1. **UI display calls**
   ```python
   # ❌ NO - stays in step
   ctx.textual.text("Processing...")
   ctx.textual.success_text("Done!")
   ```

2. **User prompts**
   ```python
   # ❌ NO - stays in step
   name = ctx.textual.ask_text("Enter name:")
   confirmed = ctx.textual.ask_confirm("Proceed?")
   ```

3. **Widget mounting**
   ```python
   # ❌ NO - stays in step
   ctx.textual.mount(Panel("Info"))
   ctx.textual.mount(Table(headers, rows))
   ```

4. **Workflow context access**
   ```python
   # ❌ NO - stays in step
   value = ctx.get("param")
   ctx.data["key"] = value
   ```

## Return Types: Operations vs Client

**CRITICAL**: Operations and Client/Services return different types.

### Operations Return Types

Operations return **data directly** or **raise exceptions**:

```python
# ✅ CORRECT: Returns UIModel
def get_available_transitions(
    client: JiraClient,
    issue_key: str
) -> List[UITransition]:
    """Get available transitions."""
    result = client.get_transitions(issue_key)

    match result:
        case ClientSuccess(data=transitions):
            return transitions  # ✅ Returns data directly
        case ClientError(error_message=err):
            raise OperationError(f"Failed: {err}")  # ✅ Raises exception
```

```python
# ❌ WRONG: Operations should NOT return ClientResult
def get_available_transitions(
    client: JiraClient,
    issue_key: str
) -> ClientResult[List[UITransition]]:  # ❌ Wrong return type
    """Get available transitions."""
    result = client.get_transitions(issue_key)

    match result:
        case ClientSuccess(data=transitions):
            return ClientSuccess(data=transitions)  # ❌ Just wrapping
        case ClientError(error_message=err):
            return ClientError(error_message=err)  # ❌ Should raise
```

### Client/Services Return Types

Client and Services return `ClientResult[UIModel]`:

```python
# ✅ CORRECT: Client returns ClientResult
def get_transitions(
    self,
    issue_key: str
) -> ClientResult[List[UITransition]]:
    """Get transitions for issue."""
    return self._transition_service.get_transitions(issue_key)
```

### Quick Reference

| Layer | Returns | Example |
|-------|---------|---------|
| **Operations** | `T` or raises | `List[UIJiraIssue]` or `raise OperationError` |
| **Client** | `ClientResult[T]` | `ClientResult[List[UIJiraIssue]]` |
| **Services** | `ClientResult[T]` | `ClientResult[UIJiraIssue]` |

## Implementation Guide

### Step 1: Identify Business Logic in Step

Look for code that does NOT involve UI:

```python
# Example step with mixed concerns
def create_issue_step(ctx):
    ctx.textual.begin_step("Create Issue")

    # Business logic (EXTRACT THIS)
    labels_input = ctx.get("labels", "")
    labels = [l.strip() for l in labels_input.split(",") if l.strip()]  # ← Extract

    # More business logic (EXTRACT THIS)
    available_labels = ctx.jira.list_labels()
    valid_labels = []
    invalid_labels = []
    for label in labels:  # ← Extract
        if label in available_labels:
            valid_labels.append(label)
        else:
            invalid_labels.append(label)

    # UI (KEEP IN STEP)
    if invalid_labels:
        ctx.textual.warning_text(f"Invalid: {', '.join(invalid_labels)}")

    # ... rest of step
```

### Step 2: Create Operations Module

```python
# plugins/titan-plugin-jira/titan_plugin_jira/operations/label_operations.py
"""
Label Operations

Pure business logic for label functionality.
"""

from typing import List, Tuple


def parse_comma_separated_labels(labels_input: str) -> List[str]:
    """
    Parse comma-separated labels string.

    Args:
        labels_input: Comma-separated string (e.g., "bug, feature")

    Returns:
        List of trimmed non-empty labels
    """
    if not labels_input or not labels_input.strip():
        return []

    labels = [label.strip() for label in labels_input.split(",") if label.strip()]
    return labels


def filter_valid_labels(
    selected_labels: List[str],
    available_labels: List[str]
) -> Tuple[List[str], List[str]]:
    """
    Filter selected labels to separate valid and invalid ones.

    Args:
        selected_labels: Labels selected by user
        available_labels: Labels that exist in Jira

    Returns:
        Tuple of (valid_labels, invalid_labels)
    """
    valid = []
    invalid = []

    for label in selected_labels:
        if label in available_labels:
            valid.append(label)
        else:
            invalid.append(label)

    return valid, invalid


__all__ = [
    "parse_comma_separated_labels",
    "filter_valid_labels",
]
```

### Step 3: Export from __init__.py

```python
# plugins/titan-plugin-jira/titan_plugin_jira/operations/__init__.py
"""
Jira Plugin Operations

Pure business logic functions that can be used in steps or called programmatically.
All functions here are UI-agnostic and can be unit tested independently.
"""

from .label_operations import (
    parse_comma_separated_labels,
    filter_valid_labels,
)

from .issue_operations import (
    get_available_transitions,
    validate_issue_fields,
)

__all__ = [
    # Label operations
    "parse_comma_separated_labels",
    "filter_valid_labels",

    # Issue operations
    "get_available_transitions",
    "validate_issue_fields",
]
```

### Step 4: Write Unit Tests

```python
# plugins/titan-plugin-jira/tests/operations/test_label_operations.py
"""
Tests for Label Operations
"""

from titan_plugin_jira.operations import (
    parse_comma_separated_labels,
    filter_valid_labels,
)


class TestParseCommaSeparatedLabels:
    """Tests for parse_comma_separated_labels function."""

    def test_parse_simple_list(self):
        """Should parse simple comma-separated list."""
        result = parse_comma_separated_labels("bug, feature, enhancement")
        assert result == ["bug", "feature", "enhancement"]

    def test_parse_with_extra_spaces(self):
        """Should trim extra spaces."""
        result = parse_comma_separated_labels("  bug  ,  feature  ")
        assert result == ["bug", "feature"]

    def test_parse_empty_string(self):
        """Should return empty list for empty string."""
        result = parse_comma_separated_labels("")
        assert result == []

    def test_parse_whitespace_only(self):
        """Should return empty list for whitespace."""
        result = parse_comma_separated_labels("   ")
        assert result == []


class TestFilterValidLabels:
    """Tests for filter_valid_labels function."""

    def test_all_labels_valid(self):
        """Should return all labels as valid."""
        valid, invalid = filter_valid_labels(
            selected_labels=["bug", "feature"],
            available_labels=["bug", "feature", "enhancement"]
        )
        assert valid == ["bug", "feature"]
        assert invalid == []

    def test_some_labels_invalid(self):
        """Should separate valid and invalid labels."""
        valid, invalid = filter_valid_labels(
            selected_labels=["bug", "invalid", "feature"],
            available_labels=["bug", "feature"]
        )
        assert valid == ["bug", "feature"]
        assert invalid == ["invalid"]

    def test_all_labels_invalid(self):
        """Should return all labels as invalid."""
        valid, invalid = filter_valid_labels(
            selected_labels=["wrong1", "wrong2"],
            available_labels=["bug", "feature"]
        )
        assert valid == []
        assert invalid == ["wrong1", "wrong2"]
```

**Target: 100% test coverage on operations**

### Step 5: Refactor Step to Use Operations

```python
# plugins/titan-plugin-jira/titan_plugin_jira/steps/issue_steps.py
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
from ..operations import parse_comma_separated_labels, filter_valid_labels


def create_issue_step(ctx: WorkflowContext) -> WorkflowResult:
    """Create Jira issue."""
    ctx.textual.begin_step("Create Issue")

    # Get data from context
    labels_input = ctx.get("labels", "")

    # Use operation for parsing
    labels = parse_comma_separated_labels(labels_input)

    # Use operation for validation
    if labels:
        available_labels = ctx.jira.list_labels()
        valid_labels, invalid_labels = filter_valid_labels(labels, available_labels)

        # UI only: Display results
        if invalid_labels:
            ctx.textual.warning_text(f"Skipping invalid: {', '.join(invalid_labels)}")

        labels = valid_labels

    # Continue with issue creation...
    ctx.textual.end_step("success")
    return Success("Issue created")
```

## Best Practices

### ✅ DO

1. **Write comprehensive docstrings**
   ```python
   def my_operation(data: str, threshold: int) -> List[str]:
       """
       Brief description.

       Args:
           data: Description of data parameter
           threshold: Description of threshold

       Returns:
           Description of return value

       Raises:
           OperationError: When operation fails
       """
   ```

2. **Make operations pure functions** (no side effects)
   ```python
   # ✅ GOOD: Pure function
   def calculate_total(items: List[int]) -> int:
       return sum(items)

   # ❌ BAD: Side effects
   def calculate_total(items: List[int]) -> int:
       print("Calculating...")  # Side effect!
       return sum(items)
   ```

3. **Return tuples for multiple values**
   ```python
   def split_data(text: str) -> Tuple[List[str], List[str]]:
       valid = []
       invalid = []
       # ... processing
       return valid, invalid
   ```

4. **Handle edge cases**
   ```python
   def parse_list(text: str) -> List[str]:
       if not text or not text.strip():
           return []  # Handle empty input
       return text.split(",")
   ```

5. **Use type hints**
   ```python
   from typing import List, Tuple, Optional, Dict

   def my_operation(
       items: List[str],
       config: Dict[str, any]
   ) -> Optional[str]:
       ...
   ```

### ❌ DON'T

1. **Don't access UI in operations**
   ```python
   # ❌ BAD
   def process_data(ctx, data):
       ctx.textual.text("Processing...")  # NO!
       return data

   # ✅ GOOD
   def process_data(data: str) -> str:
       return data.strip()
   ```

2. **Don't pass WorkflowContext to operations**
   ```python
   # ❌ BAD
   def my_operation(ctx: WorkflowContext):
       data = ctx.get("data")  # NO!

   # ✅ GOOD
   def my_operation(data: str):
       # Explicit parameters
   ```

3. **Don't duplicate logic**
   ```python
   # ❌ BAD: Same logic in multiple places
   # step1.py
   items = [x.strip() for x in data.split(",") if x.strip()]

   # step2.py
   items = [x.strip() for x in data.split(",") if x.strip()]  # Duplicate!

   # ✅ GOOD: Extract to operation
   from ..operations import parse_comma_separated_list
   items = parse_comma_separated_list(data)
   ```

4. **Don't return ClientResult from operations**
   ```python
   # ❌ BAD
   def my_operation(client) -> ClientResult[List[UIItem]]:
       result = client.get_items()
       return result  # NO! This is wrong layer

   # ✅ GOOD
   def my_operation(client) -> List[UIItem]:
       result = client.get_items()
       match result:
           case ClientSuccess(data=items):
               return items
           case ClientError(error_message=err):
               raise OperationError(f"Failed: {err}")
   ```

## Common Patterns

### Pattern 1: Data Transformation

```python
def format_diff_stat_display(stat_output: str) -> Tuple[List[str], List[str]]:
    """
    Format git diff --stat output for display.

    Args:
        stat_output: Raw output from git diff --stat

    Returns:
        Tuple of (formatted_files, formatted_summary)
    """
    file_lines = []
    summary_lines = []
    max_filename_len = 0

    # Parse file changes
    for line in stat_output.split('\n'):
        if not line.strip():
            continue
        if '|' in line:
            parts = line.split('|')
            filename = parts[0].strip()
            stats = '|'.join(parts[1:]) if len(parts) > 1 else ''
            file_lines.append((filename, stats))
            max_filename_len = max(max_filename_len, len(filename))

    # Format with alignment
    formatted_files = []
    for filename, stats in file_lines:
        padded_name = filename.ljust(max_filename_len)
        formatted_files.append(f"{padded_name} | {stats}")

    return formatted_files, summary_lines
```

### Pattern 2: Validation

```python
def validate_pr_fields(
    title: str,
    description: str
) -> Tuple[bool, Optional[str]]:
    """
    Validate PR fields.

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not title or len(title.strip()) < 5:
        return False, "Title must be at least 5 characters"

    if not description or len(description.strip()) < 10:
        return False, "Description must be at least 10 characters"

    return True, None
```

### Pattern 3: Complex Client Orchestration

```python
def fetch_issue_with_metadata(
    client: JiraClient,
    issue_key: str
) -> Tuple[UIJiraIssue, List[UITransition], List[str]]:
    """
    Fetch issue with all metadata (transitions, labels).

    Args:
        client: Jira client instance
        issue_key: Issue key (e.g., "PROJ-123")

    Returns:
        Tuple of (issue, transitions, labels)

    Raises:
        OperationError: If fetch fails
    """
    # Fetch issue
    issue_result = client.get_issue(issue_key)
    match issue_result:
        case ClientSuccess(data=issue):
            pass
        case ClientError(error_message=err):
            raise OperationError(f"Failed to fetch issue: {err}")

    # Fetch transitions
    transitions_result = client.get_transitions(issue_key)
    match transitions_result:
        case ClientSuccess(data=transitions):
            pass
        case ClientError(error_message=err):
            raise OperationError(f"Failed to fetch transitions: {err}")

    # Fetch labels
    labels_result = client.list_labels()
    match labels_result:
        case ClientSuccess(data=labels):
            pass
        case ClientError(error_message=err):
            raise OperationError(f"Failed to fetch labels: {err}")

    return issue, transitions, labels
```

## Testing Strategy

### Unit Tests for Operations

```bash
# Run tests
poetry run pytest plugins/titan-plugin-{name}/tests/operations/ -v

# Check coverage
poetry run pytest plugins/titan-plugin-{name}/tests/operations/ \
    --cov=plugins/titan-plugin-{name}/titan_plugin_{name}/operations \
    --cov-report=term-missing
```

**Target: 100% coverage**

### Example Test Structure

```python
class TestMyOperation:
    """Tests for my_operation function."""

    def test_normal_case(self):
        """Should handle normal input."""
        result = my_operation("test")
        assert result == expected

    def test_edge_case_empty(self):
        """Should handle empty input."""
        result = my_operation("")
        assert result == []

    def test_edge_case_none(self):
        """Should handle None input."""
        result = my_operation(None)
        assert result == default_value

    def test_raises_on_error(self):
        """Should raise OperationError on failure."""
        with pytest.raises(OperationError, match="Failed"):
            my_operation(invalid_input)
```

## Migration Checklist

When refactoring an existing step:

- [ ] Identify all business logic (parsing, validation, calculations)
- [ ] Create operations module with descriptive name
- [ ] Extract each piece of logic to a pure function
- [ ] Write docstrings with Args/Returns/Raises
- [ ] Write unit tests for each operation (aim for 100%)
- [ ] Update step to import and use operations
- [ ] Verify step syntax: `python3 -m py_compile {step_file}.py`
- [ ] Run operations tests
- [ ] Check for code duplication across other steps
- [ ] Update `operations/__init__.py` exports

## Common Mistakes to Avoid

### ❌ Mistake 1: Operations Returning ClientResult

```python
# ❌ WRONG
def get_transitions(client, issue_key) -> ClientResult[List[UITransition]]:
    result = client.get_transitions(issue_key)
    return result  # Wrong layer!

# ✅ CORRECT
def get_transitions(client, issue_key) -> List[UITransition]:
    result = client.get_transitions(issue_key)
    match result:
        case ClientSuccess(data=transitions):
            return transitions
        case ClientError(error_message=err):
            raise OperationError(f"Failed: {err}")
```

### ❌ Mistake 2: UI Code in Operations

```python
# ❌ WRONG
def process_items(ctx, items):
    ctx.textual.text("Processing...")  # NO UI in operations!
    return [item.upper() for item in items]

# ✅ CORRECT
def process_items(items: List[str]) -> List[str]:
    return [item.upper() for item in items]
```

### ❌ Mistake 3: Passing WorkflowContext

```python
# ❌ WRONG
def my_operation(ctx: WorkflowContext):
    data = ctx.get("data")  # Don't access context
    return process(data)

# ✅ CORRECT
def my_operation(data: str):
    return process(data)
```

## Quick Reference

### Operation Signature Template

```python
def operation_name(
    param1: Type1,
    param2: Type2,
    optional_param: Type3 = default_value
) -> ReturnType:
    """
    Brief description.

    Args:
        param1: Description
        param2: Description
        optional_param: Description (default: default_value)

    Returns:
        Description of return value

    Raises:
        OperationError: When operation fails
    """
    # Pure business logic here
    try:
        result = process(param1, param2)
        return result
    except Exception as e:
        raise OperationError(f"Failed to process: {e}")
```

### Common Import Pattern

```python
# In operations module
from typing import List, Tuple, Optional, Dict
from ..clients import JiraClient
from ..models import UIJiraIssue, UITransition
from ..exceptions import OperationError

# In step
from ..operations import (
    parse_comma_separated_labels,
    filter_valid_labels,
    get_available_transitions,
)
```

## Examples from Real Plugins

### GitHub Plugin

**Operations**:
- `parse_comma_separated_list()` - Parse input strings
- `filter_valid_labels()` - Validate labels
- `fetch_pr_threads()` - Complex client orchestration
- `push_and_request_review()` - Multi-step workflow logic

**Location**: `plugins/titan-plugin-github/titan_plugin_github/operations/`

### Git Plugin

**Operations**:
- `format_diff_stat_display()` - Format diff output
- `parse_commit_range()` - Parse git commit syntax
- `filter_modified_files()` - File filtering logic

**Location**: `plugins/titan-plugin-git/titan_plugin_git/operations/`

### Jira Plugin

**Operations**:
- `substitute_jql_variables()` - JQL variable substitution
- `parse_issue_fields()` - Parse Jira field inputs
- `validate_transition()` - Transition validation

**Location**: `plugins/titan-plugin-jira/titan_plugin_jira/operations/`

## Summary

**Operations are for pure business logic**:
- ✅ Data transformation, parsing, validation
- ✅ Calculations, filtering, sorting
- ✅ Complex client orchestration
- ✅ Return data or raise exceptions
- ✅ 100% unit testable

**Steps are for UI orchestration**:
- ✅ Display information (`ctx.textual`)
- ✅ Get user input (`ask_text`, `ask_confirm`)
- ✅ Call operations for logic
- ✅ Return workflow results

**Remember**: When you find yourself writing complex logic in a step, ask: "Can this be tested independently?" If yes, extract it to an operation!
