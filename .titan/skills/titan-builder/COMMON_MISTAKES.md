# Common Mistakes & Anti-Patterns

**Critical errors to avoid when building Titan CLI plugins**

This document catalogs the 11 most common mistakes found during code reviews. Use this as a checklist when generating code to ensure architectural compliance.

---

## 📚 Quick Reference: Layer Return Types

**Know what each layer should return to avoid architectural violations**

| Layer | Returns | Example | Pattern |
|-------|---------|---------|---------|
| **Client (Facade)** | `ClientResult[UIModel]` | `ClientResult[UIJiraIssue]` | Public API - always UI models |
| **Service (Internal)** | `ClientResult[UIModel]` | `ClientResult[List[UIJiraStatus]]` | Network → UI transformation |
| **Operations** | `UIModel` or raises | `UIJiraIssue` or `raise OperationError` | Pure business logic |
| **Mappers** | `UIModel` | `from_network_issue() -> UIJiraIssue` | Network → UI conversion |
| **Network/API** | Raw `dict` | `{"id": "1", "name": "Bug"}` | HTTP response parsing |
| **Steps** | `WorkflowResult` | `Success()` / `Error()` / `Skip()` | UI orchestration |

### Key Rules

1. **Client & Services**: Always return `ClientResult[UIModel]`
   - ✅ `ClientResult[UIJiraIssue]`
   - ❌ `ClientResult[NetworkJiraIssue]` (exposes internal structure)
   - ❌ `ClientResult[dict]` (not type-safe)

2. **Operations**: Return data directly or raise exceptions
   - ✅ `def get_issue(...) -> UIJiraIssue:`
   - ❌ `def get_issue(...) -> ClientResult[UIJiraIssue]:` (wrong layer)

3. **Network Models**: Internal only, never exposed
   - ✅ Used inside Services to parse API responses
   - ✅ Passed to Mappers for UI transformation
   - ❌ Never returned from Client/Service public methods

4. **UI Models**: Public contract
   - ✅ Returned by all Client methods
   - ✅ Returned by all Service methods
   - ✅ Used by Steps for display
   - ✅ Pre-formatted (icons, labels, display strings)

### Flow Example

```
HTTP Response → Network Layer → Service → Client → Step
     ↓              ↓             ↓         ↓        ↓
   JSON          dict      NetworkModel  UIModel  Display
                           → UIModel

Detailed:
1. Network.make_request() → dict {"id": "1", "status": {"name": "To Do"}}
2. Service parses → NetworkJiraIssue(id="1", status=NetworkStatus(...))
3. Service maps → UIJiraIssue(id="1", status_display="🟡 To Do")
4. Client returns → ClientResult[UIJiraIssue]
5. Step displays → ctx.textual.text("🟡 To Do")
```

---

## ❌ Mistake #1: Operations Returning ClientResult

**Severity**: CRITICAL

### The Problem

Operations are returning `ClientResult[T]` instead of returning the actual data type or raising exceptions.

### ❌ WRONG

```python
# operations/issue_operations.py
from titan_cli.core.result import ClientResult, ClientSuccess, ClientError

def get_available_transitions(
    client: JiraClient,
    issue_key: str
) -> ClientResult[List[UITransition]]:  # ❌ Operations should NOT return ClientResult
    """Get available transitions."""
    result = client.get_transitions(issue_key)

    match result:
        case ClientSuccess(data=transitions):
            return ClientSuccess(data=transitions)  # ❌ Just wrapping and re-returning
        case ClientError(error_message=err):
            return ClientError(error_message=err)   # ❌ Should raise instead
```

### ✅ CORRECT

```python
# operations/issue_operations.py
from typing import List
from ..clients import JiraClient
from ..models import UITransition
from ..exceptions import OperationError

def get_available_transitions(
    client: JiraClient,
    issue_key: str
) -> List[UITransition]:  # ✅ Returns actual data type
    """
    Get available transitions for issue.

    Args:
        client: JiraClient instance
        issue_key: Issue key (e.g., "PROJ-123")

    Returns:
        List of available transitions

    Raises:
        OperationError: If transitions cannot be retrieved
    """
    result = client.get_transitions(issue_key)

    match result:
        case ClientSuccess(data=transitions):
            return transitions  # ✅ Returns data directly
        case ClientError(error_message=err):
            raise OperationError(f"Failed to get transitions: {err}")  # ✅ Raises exception
```

### Why This Matters

- **Operations layer** = pure business logic (returns data or raises)
- **Client/Services layer** = data access (returns `ClientResult`)
- Mixing these patterns breaks separation of concerns

---

## ❌ Mistake #2: Client Returning Network Models

**Severity**: CRITICAL

### The Problem

Client methods are returning `ClientResult[NetworkModel]` instead of `ClientResult[UIModel]`.

### ❌ WRONG

```python
# clients/jira_client.py
def get_issue_types(
    self,
    project_key: str
) -> ClientResult[List[NetworkJiraIssueType]]:  # ❌ Network model exposed
    """Get issue types."""
    return self._metadata_service.get_issue_types(project_key)
```

### ✅ CORRECT

```python
# clients/jira_client.py
def get_issue_types(
    self,
    project_key: str
) -> ClientResult[List[UIJiraIssueType]]:  # ✅ UI model (public API)
    """Get issue types for project."""
    return self._metadata_service.get_issue_types(project_key)
```

**And in the service**:

```python
# clients/services/metadata_service.py
def get_issue_types(
    self,
    project_key: str
) -> ClientResult[List[UIJiraIssueType]]:
    """Get issue types (internal)."""
    try:
        data = self.network.make_request("GET", f"project/{project_key}/issuetypes")

        # Parse to Network models
        network_types = [NetworkJiraIssueType(**item) for item in data]

        # Map to UI models
        ui_types = [from_network_issue_type(nt) for nt in network_types]

        return ClientSuccess(data=ui_types, message=f"Found {len(ui_types)} types")

    except JiraAPIError as e:
        return ClientError(error_message=str(e), error_code="API_ERROR")
```

### Why This Matters

- **Network models** = internal implementation detail
- **UI models** = public API contract
- Exposing network models couples consumers to API structure

---

## ❌ Mistake #3: Business Logic in Client

**Severity**: HIGH

### The Problem

Client facade contains business logic (searching, filtering, validation).

### ❌ WRONG

```python
# clients/jira_client.py
def create_issue(self, project_key: str, issue_type: str, ...) -> ClientResult[UIJiraIssue]:
    """Create issue."""

    # ❌ Business logic: searching for issue type
    issue_types_result = self._metadata_service.get_issue_types(project_key)
    if isinstance(issue_types_result, ClientError):  # ❌ isinstance instead of match
        return issue_types_result

    issue_type_obj = None
    for it in issue_types_result.data:  # ❌ Search logic in Client
        if it.name.lower() == issue_type.lower():
            issue_type_obj = it
            break

    if not issue_type_obj:  # ❌ Validation logic in Client
        return ClientError(error_message=f"Issue type '{issue_type}' not found")

    # ... rest of creation logic
```

### ✅ CORRECT

**Option A: Move to Service**

```python
# clients/services/issue_service.py
def create_issue(
    self,
    project_key: str,
    issue_type_name: str,
    ...
) -> ClientResult[UIJiraIssue]:
    """Create issue (internal)."""

    # Get issue types
    types_data = self.metadata_service.get_issue_types(project_key)

    match types_data:
        case ClientSuccess(data=types):
            # Find matching type
            issue_type = None
            for t in types:
                if t.name.lower() == issue_type_name.lower():
                    issue_type = t
                    break

            if not issue_type:
                return ClientError(
                    error_message=f"Issue type '{issue_type_name}' not found",
                    error_code="INVALID_TYPE"
                )

            # Continue with creation...

        case ClientError() as err:
            return err

# clients/jira_client.py
def create_issue(self, ...) -> ClientResult[UIJiraIssue]:
    """Create issue."""
    return self._issue_service.create_issue(...)  # Simple delegation
```

**Option B: Move to Operation**

```python
# operations/issue_operations.py
def create_issue_with_validation(
    client: JiraClient,
    project_key: str,
    issue_type_name: str,
    ...
) -> UIJiraIssue:
    """
    Create issue with type validation.

    Raises:
        OperationError: If type invalid or creation fails
    """
    # Get types
    types_result = client.get_issue_types(project_key)

    match types_result:
        case ClientSuccess(data=types):
            # Find type
            issue_type = next(
                (t for t in types if t.name.lower() == issue_type_name.lower()),
                None
            )

            if not issue_type:
                raise OperationError(f"Issue type '{issue_type_name}' not found")

            # Create issue
            result = client.create_issue(project_key, issue_type.id, ...)

            match result:
                case ClientSuccess(data=issue):
                    return issue
                case ClientError(error_message=err):
                    raise OperationError(f"Failed to create issue: {err}")

        case ClientError(error_message=err):
            raise OperationError(f"Failed to get issue types: {err}")
```

### Why This Matters

- **Client** = thin facade (just delegation)
- **Service** = data access + transformation
- **Operation** = complex multi-step business logic

---

## ❌ Mistake #4: Mapping in Client

**Severity**: HIGH

### The Problem

Client method is doing data transformation/mapping.

### ❌ WRONG

```python
# clients/jira_client.py
def get_priorities(self) -> ClientResult[List[UIPriority]]:
    """Get priorities."""
    result = self._metadata_service.list_priorities()

    # ❌ Mapping in Client
    match result:
        case ClientSuccess(data=priorities):
            mapped = [self._map_priority(p) for p in priorities]  # ❌ NO!
            return ClientSuccess(data=mapped)
        case ClientError() as err:
            return err

def _map_priority(self, network: NetworkPriority) -> UIPriority:  # ❌ Helper in Client
    """Map priority."""
    return UIPriority(...)
```

### ✅ CORRECT

```python
# clients/services/metadata_service.py
def list_priorities(self) -> ClientResult[List[UIPriority]]:
    """List all priorities (internal)."""
    try:
        data = self.network.make_request("GET", "priority")

        # Parse to Network models
        network_priorities = [NetworkPriority(**item) for item in data]

        # Map to UI models (mapping happens in Service)
        ui_priorities = [from_network_priority(p) for p in network_priorities]

        return ClientSuccess(
            data=ui_priorities,
            message=f"Found {len(ui_priorities)} priorities"
        )

    except JiraAPIError as e:
        return ClientError(error_message=str(e), error_code="API_ERROR")

# clients/jira_client.py
def get_priorities(self) -> ClientResult[List[UIPriority]]:
    """Get all priorities."""
    return self._metadata_service.list_priorities()  # ✅ Simple delegation
```

### Why This Matters

- **Services** handle all data transformation
- **Client** only delegates
- Keeps Client as a thin, testable facade

---

## ❌ Mistake #5: try/except in Steps for ClientResult

**Severity**: HIGH

### The Problem

Steps using `try/except` instead of pattern matching for `ClientResult`.

### ❌ WRONG

```python
# steps/select_issue_priority_step.py
def select_issue_priority_step(ctx: WorkflowContext) -> WorkflowResult:
    """Select priority."""
    ctx.textual.begin_step("Select Priority")

    try:  # ❌ try/except for ClientResult
        result = ctx.jira.get_priorities()

        if isinstance(result, ClientError):  # ❌ isinstance check
            ctx.textual.error_text(result.error_message)
            return Error(result.error_message)

        priorities = result.data  # ❌ Direct .data access (assumes success)

        # ... rest of step

    except Exception as e:  # ❌ Catching generic exceptions
        ctx.textual.error_text(str(e))
        return Error(str(e))
```

### ✅ CORRECT

```python
# steps/select_issue_priority_step.py
def select_issue_priority_step(ctx: WorkflowContext) -> WorkflowResult:
    """Select priority."""
    ctx.textual.begin_step("Select Priority")

    # Get priorities
    result = ctx.jira.get_priorities()

    # ✅ Pattern matching is MANDATORY
    match result:
        case ClientSuccess(data=priorities, message=msg):
            ctx.textual.success_text(msg)

            # Build selection table
            table_data = []
            for priority in priorities:
                table_data.append({
                    "icon": priority.icon,
                    "name": priority.name,
                    "description": priority.description
                })

            # Show selection
            selected_index = ctx.textual.ask_selection(
                prompt="Select priority:",
                options=[p["name"] for p in table_data],
                default_index=2  # Medium
            )

            if selected_index is None:
                ctx.textual.end_step("success")
                return Success("Cancelled")

            selected = priorities[selected_index]

            ctx.textual.info_text(f"Selected: {selected.icon} {selected.name}")
            ctx.textual.end_step("success")

            return Success(
                f"Priority selected: {selected.name}",
                metadata={"priority_id": selected.id, "priority_name": selected.name}
            )

        case ClientError(error_message=err, error_code=code):
            ctx.textual.error_text(f"Failed to get priorities: {err}")
            if code == "NOT_AUTHENTICATED":
                ctx.textual.text("Check your Jira credentials in config")
            ctx.textual.end_step("error")
            return Error(err)
```

### Why This Matters

- **Pattern matching** = type-safe, compiler-checked
- **try/except** = runtime errors, missed cases
- Forces explicit handling of success and error paths

---

## ❌ Mistake #6: Doctest Examples in Docstrings

**Severity**: MEDIUM

### The Problem

Docstrings contain `>>>` examples (doctest format) that aren't executed.

### ❌ WRONG

```python
def validate_positive_integer(value: str, field_name: str) -> int:
    """
    Validate that a string is a positive integer.

    Args:
        value: String to validate
        field_name: Field name for error messages

    Returns:
        Validated integer

    Raises:
        ValueError: If not a valid positive integer

    Examples:  # ❌ Doctest examples not run
        >>> validate_positive_integer("123", "count")
        123
        >>> validate_positive_integer("0", "count")
        Traceback (most recent call last):
            ...
        ValueError: count must be a positive integer
        >>> validate_positive_integer("-5", "count")
        Traceback (most recent call last):
            ...
        ValueError: count must be a positive integer
    """
    try:
        num = int(value)
        if num <= 0:
            raise ValueError(f"{field_name} must be a positive integer")
        return num
    except ValueError:
        raise ValueError(f"{field_name} must be a valid integer")
```

### ✅ CORRECT

```python
def validate_positive_integer(value: str, field_name: str) -> int:
    """
    Validate that a string is a positive integer.

    Args:
        value: String to validate
        field_name: Field name for error messages

    Returns:
        Validated positive integer

    Raises:
        ValueError: If not a valid positive integer or not numeric
    """
    try:
        num = int(value)
        if num <= 0:
            raise ValueError(f"{field_name} must be a positive integer")
        return num
    except ValueError as e:
        if "invalid literal" in str(e):
            raise ValueError(f"{field_name} must be a valid integer")
        raise
```

**Write actual tests instead**:

```python
# tests/utils/test_input_validation.py
def test_validate_positive_integer_success():
    """Should accept valid positive integers."""
    assert validate_positive_integer("123", "count") == 123
    assert validate_positive_integer("1", "count") == 1

def test_validate_positive_integer_zero():
    """Should reject zero."""
    with pytest.raises(ValueError, match="count must be a positive integer"):
        validate_positive_integer("0", "count")

def test_validate_positive_integer_negative():
    """Should reject negative numbers."""
    with pytest.raises(ValueError, match="count must be a positive integer"):
        validate_positive_integer("-5", "count")

def test_validate_positive_integer_not_numeric():
    """Should reject non-numeric strings."""
    with pytest.raises(ValueError, match="count must be a valid integer"):
        validate_positive_integer("abc", "count")
```

### Why This Matters

- Titan CLI doesn't run doctests
- Examples in docstrings get stale
- Real tests in `/tests` are executed and maintained

---

## ❌ Mistake #7: Calling API Multiple Times

**Severity**: MEDIUM

### The Problem

Step calls the client API twice to get the same data.

### ❌ WRONG

```python
# steps/create_generic_issue_step.py
def create_generic_issue_step(ctx: WorkflowContext) -> WorkflowResult:
    """Create issue."""
    ctx.textual.begin_step("Create Issue")

    # ... gather inputs ...

    # Create issue - FIRST API CALL
    result = ctx.jira.create_issue(
        project_key=project,
        issue_type=issue_type,
        summary=summary,
        description=description
    )

    match result:
        case ClientSuccess(data=issue):
            ctx.textual.success_text(f"Issue created: {issue.key}")

            # ❌ SECOND API CALL - just to get the URL
            issue_details = ctx.jira.get_issue(issue.key)

            match issue_details:
                case ClientSuccess(data=details):
                    ctx.textual.text(f"URL: {details.url}")  # ❌ Already had this!

            ctx.textual.end_step("success")
            return Success("Issue created")

        case ClientError(error_message=err):
            return Error(err)
```

### ✅ CORRECT

**Option A: Include URL in create_issue response**

```python
# models/view.py
@dataclass
class UIJiraIssue:
    """UI model for Jira issue."""
    key: str
    summary: str
    url: str  # ✅ URL included in model
    status_icon: str
    status_display: str
    # ... other fields

# clients/services/issue_service.py
def create_issue(...) -> ClientResult[UIJiraIssue]:
    """Create issue."""
    try:
        data = self.network.make_request("POST", "issue", json=payload)

        # Parse response
        network_issue = NetworkJiraIssue(**data)

        # Map to UI (includes URL)
        ui_issue = from_network_issue(network_issue)

        return ClientSuccess(data=ui_issue, message=f"Issue {ui_issue.key} created")

    except JiraAPIError as e:
        return ClientError(error_message=str(e))

# steps/create_generic_issue_step.py
def create_generic_issue_step(ctx: WorkflowContext) -> WorkflowResult:
    """Create issue."""
    ctx.textual.begin_step("Create Issue")

    # ... gather inputs ...

    # Single API call
    result = ctx.jira.create_issue(...)

    match result:
        case ClientSuccess(data=issue):
            ctx.textual.success_text(f"Issue created: {issue.key}")
            ctx.textual.text(f"URL: {issue.url}")  # ✅ URL from first call
            ctx.textual.end_step("success")
            return Success("Issue created", metadata={"issue_key": issue.key})

        case ClientError(error_message=err):
            ctx.textual.error_text(f"Failed: {err}")
            ctx.textual.end_step("error")
            return Error(err)
```

**Option B: Add URL to ClientSuccess message**

```python
# clients/services/issue_service.py
def create_issue(...) -> ClientResult[UIJiraIssue]:
    """Create issue."""
    try:
        data = self.network.make_request("POST", "issue", json=payload)
        network_issue = NetworkJiraIssue(**data)
        ui_issue = from_network_issue(network_issue)

        # Include URL in message
        return ClientSuccess(
            data=ui_issue,
            message=f"Issue {ui_issue.key} created: {ui_issue.url}"  # ✅ URL in message
        )

    except JiraAPIError as e:
        return ClientError(error_message=str(e))

# steps/create_generic_issue_step.py
match result:
    case ClientSuccess(data=issue, message=msg):
        ctx.textual.success_text(msg)  # ✅ Shows "Issue PROJ-123 created: https://..."
```

### Why This Matters

- Performance: Reduces API calls
- Reliability: Fewer network requests = fewer failure points
- Consistency: First call returns complete data

---

## ❌ Mistake #8: Markdown for Simple Text

**Severity**: LOW

### The Problem

Using `ctx.textual.markdown()` for simple headers/titles instead of `bold_text()`.

### ❌ WRONG

```python
# steps/prompt_issue_description_step.py
def prompt_issue_description_step(ctx: WorkflowContext) -> WorkflowResult:
    """Prompt for description."""
    ctx.textual.begin_step("Issue Description")

    # ❌ Markdown for simple title
    ctx.textual.markdown("## Describe the Issue")

    description = ctx.textual.ask_text(
        prompt="Description:",
        multiline=True
    )

    # ...
```

### ✅ CORRECT

```python
# steps/prompt_issue_description_step.py
def prompt_issue_description_step(ctx: WorkflowContext) -> WorkflowResult:
    """Prompt for description."""
    ctx.textual.begin_step("Issue Description")

    # ✅ bold_text for simple headers
    ctx.textual.bold_text("Describe the Issue")

    description = ctx.textual.ask_text(
        prompt="Description:",
        multiline=True,
        hint="Be specific about the problem or requirement"
    )

    if not description or not description.strip():
        ctx.textual.info_text("No description provided")
        ctx.textual.end_step("success")
        return Success("Skipped")

    ctx.textual.success_text(f"Description captured: {len(description)} characters")
    ctx.textual.end_step("success")

    return Success(
        f"Brief description captured: {len(description)} characters",
        metadata={"description": description}
    )
```

### When to Use What

| Use Case | Method | Example |
|----------|--------|---------|
| Simple header/title | `bold_text()` | "Select Priority" |
| Important message | `success_text()`, `warning_text()`, `error_text()` | "✓ Issue created" |
| Plain info | `text()` | "Found 5 issues" |
| Dimmed/secondary | `dim_text()` | "(optional)" |
| Long formatted content | `markdown()` | Multi-paragraph help text, lists, code blocks |

### Why This Matters

- Performance: Markdown rendering is heavier
- Consistency: Use semantic methods for their intended purpose
- Readability: Simpler code for simple text

---

## ❌ Mistake #9: Incomplete Input Validation

**Severity**: MEDIUM

### The Problem

Validation functions not checking all constraints.

### ❌ WRONG

```python
def validate_integer_in_range(
    value: str,
    max_value: int,  # ❌ Only validates max
    field_name: str
) -> int:
    """
    Validate integer is in valid range.

    Args:
        value: String to validate
        max_value: Maximum allowed value
        field_name: Field name for errors

    Returns:
        Validated integer
    """
    try:
        num = int(value)
    except ValueError:
        raise ValueError(f"{field_name} must be a valid integer")

    if num > max_value:  # ❌ No min_value check
        raise ValueError(f"{field_name} must be <= {max_value}")

    return num
```

### ✅ CORRECT

```python
def validate_integer_in_range(
    value: str,
    min_value: int,  # ✅ Validate both bounds
    max_value: int,
    field_name: str
) -> int:
    """
    Validate integer is in valid range.

    Args:
        value: String to validate
        min_value: Minimum allowed value (inclusive)
        max_value: Maximum allowed value (inclusive)
        field_name: Field name for error messages

    Returns:
        Validated integer in range [min_value, max_value]

    Raises:
        ValueError: If not a valid integer or out of range
    """
    try:
        num = int(value)
    except ValueError:
        raise ValueError(f"{field_name} must be a valid integer")

    # ✅ Validate both min and max
    if num < min_value or num > max_value:
        raise ValueError(
            f"{field_name} must be between {min_value} and {max_value}"
        )

    return num
```

**With tests**:

```python
# tests/utils/test_input_validation.py
def test_validate_integer_in_range_success():
    """Should accept integers in valid range."""
    assert validate_integer_in_range("5", 1, 10, "value") == 5
    assert validate_integer_in_range("1", 1, 10, "value") == 1  # Min boundary
    assert validate_integer_in_range("10", 1, 10, "value") == 10  # Max boundary

def test_validate_integer_in_range_below_min():
    """Should reject values below minimum."""
    with pytest.raises(ValueError, match="value must be between 1 and 10"):
        validate_integer_in_range("0", 1, 10, "value")

def test_validate_integer_in_range_above_max():
    """Should reject values above maximum."""
    with pytest.raises(ValueError, match="value must be between 1 and 10"):
        validate_integer_in_range("11", 1, 10, "value")

def test_validate_integer_in_range_not_numeric():
    """Should reject non-numeric values."""
    with pytest.raises(ValueError, match="value must be a valid integer"):
        validate_integer_in_range("abc", 1, 10, "value")
```

### Why This Matters

- Security: Prevents invalid inputs from reaching services
- UX: Clear error messages for users
- Correctness: All constraints enforced

---

## ❌ Mistake #10: dict.pop() with None Values

**Severity**: HIGH

### The Problem

Using `dict.pop(key, default)` doesn't work if `key` exists with value `None`.

### ❌ WRONG

```python
def _parse_ai_response(response: str) -> dict:
    """Parse AI-generated response."""
    sections = {
        "title": "",
        "description": "",
        "acceptance_criteria": []
    }

    # ... parsing logic ...

    # Cleanup: set empty strings to None
    for key in ["title", "description"]:
        if not sections[key]:
            sections[key] = None  # ❌ Sets to None

    return sections

def process_response(response: str) -> str:
    """Process response."""
    parsed = _parse_ai_response(response)

    # ❌ pop() with default doesn't work if key exists with None value
    title = parsed.pop("title", "Untitled")  # Returns None (key exists!)

    # ❌ This crashes: TypeError: object of type 'NoneType' has no len()
    if len(title) > 100:
        title = title[:100]

    return title
```

### ✅ CORRECT

**Option A: Don't set to None, check for falsy**

```python
def _parse_ai_response(response: str) -> dict:
    """Parse AI-generated response."""
    sections = {
        "title": "",
        "description": "",
        "acceptance_criteria": []
    }

    # ... parsing logic ...

    # ✅ Keep empty strings (or remove the key entirely)
    return sections

def process_response(response: str) -> str:
    """Process response."""
    DEFAULT_TITLE = "Untitled"

    parsed = _parse_ai_response(response)

    # ✅ Get and validate in one step
    title = parsed.get("title", DEFAULT_TITLE) or DEFAULT_TITLE

    # Now safe to use
    if len(title) > 100:
        title = title[:100]

    return title
```

**Option B: Explicit check before using**

```python
def process_response(response: str) -> str:
    """Process response."""
    DEFAULT_TITLE = "Untitled"

    parsed = _parse_ai_response(response)

    # ✅ Explicit None check
    title = parsed.get("title")
    if title is None or not title:
        title = DEFAULT_TITLE

    if len(title) > 100:
        title = title[:100]

    return title
```

**Option C: Use dataclass instead of dict**

```python
from dataclasses import dataclass
from typing import List

@dataclass
class ParsedIssue:
    """Parsed issue data."""
    title: str = "Untitled"  # ✅ Default value
    description: str = ""
    acceptance_criteria: List[str] = None

    def __post_init__(self):
        if self.acceptance_criteria is None:
            self.acceptance_criteria = []

def _parse_ai_response(response: str) -> ParsedIssue:
    """Parse AI-generated response."""
    # ... parse sections ...

    return ParsedIssue(
        title=sections.get("title", "Untitled") or "Untitled",
        description=sections.get("description", ""),
        acceptance_criteria=sections.get("acceptance_criteria", [])
    )

def process_response(response: str) -> str:
    """Process response."""
    parsed = _parse_ai_response(response)

    # ✅ Guaranteed to be a string (never None)
    title = parsed.title

    if len(title) > 100:
        title = title[:100]

    return title
```

### Why This Matters

- **dict.pop(key, default)**: default only applies if key **doesn't exist**
- **dict.get(key, default)**: default applies if key doesn't exist **or** value is falsy (with `or` operator)
- Use dataclasses for structured data instead of dicts

---

## ❌ Mistake #11: Hardcoded Default Values & TYPE_CHECKING

**Severity**: HIGH

### The Problem

Services hardcode default values in `.get()` calls and use `TYPE_CHECKING` to avoid circular imports.

### ❌ WRONG

```python
# clients/services/metadata_service.py
from typing import TYPE_CHECKING  # ❌ NEVER use TYPE_CHECKING

if TYPE_CHECKING:  # ❌ PROHIBITED - resolves circular imports incorrectly
    from ...models.mappers import from_network_version

def list_statuses(self, project_key: str) -> ClientResult[List["UIJiraStatus"]]:
    """List statuses."""
    from ...models.mappers import from_network_status  # ❌ Import inside function

    try:
        data = self.network.make_request("GET", f"project/{project_key}/statuses")

        for status_data in data.get("statuses", []):
            status_category_data = status_data.get("statusCategory", {})

            # ❌ HARDCODED default values
            status_category = NetworkJiraStatusCategory(
                id=status_category_data.get("id", ""),
                name=status_category_data.get("name", "To Do"),  # ❌ "To Do" hardcoded
                key=status_category_data.get("key", "new"),      # ❌ "new" hardcoded
                colorName=status_category_data.get("colorName")
            )

def list_project_versions(self, project_key: str) -> ClientResult[List["UIJiraVersion"]]:
    """List versions."""
    from ...models.mappers import from_network_version  # ❌ Import inside function

    try:
        project_data = self.network.make_request("GET", f"project/{project_key}")

        for v_data in project_data.get("versions", []):
            # ❌ HARDCODED default values
            network_versions.append(NetworkJiraVersion(
                id=v_data.get("id", ""),           # ❌ "" hardcoded
                name=v_data.get("name", ""),       # ❌ "" hardcoded
                released=v_data.get("released", False),  # ❌ False hardcoded
                releaseDate=v_data.get("releaseDate")
            ))
```

### 📋 Real Example from This Project

**File**: `plugins/titan-plugin-jira/titan_plugin_jira/clients/services/metadata_service.py`

**Found Issues** (PR #166, feat/create-issue-jira branch):

1. **TYPE_CHECKING import** (Line 8):
   ```python
   from typing import TYPE_CHECKING, List  # ❌ PROHIBITED
   ```

2. **TYPE_CHECKING block** (Lines 24-31):
   ```python
   if TYPE_CHECKING:  # ❌ PROHIBITED
       from ...models.view import (
           UIJiraIssueType,
           UIJiraStatus,
           UIJiraUser,
           UIJiraVersion,
           UIPriority
       )
   ```

3. **Imports inside functions** (5 occurrences):
   - Line 56: `from ...models.mappers import from_network_issue_type`
   - Line 99: `from ...models.mappers import from_network_status`
   - Line 152: `from ...models.mappers import from_network_user`
   - Line 193: `from ...models.mappers import from_network_version`
   - Line 232: `from ...models.mappers import from_network_priority`

**Impact**: All 5 functions import their mappers inside the function body instead of at module level.

**Why this happened**: Developer tried to avoid circular imports by using TYPE_CHECKING and function-level imports, which is the **wrong solution**.

**Correct fix**: Move all mapper imports to module level (see solution below).

---

### ✅ CORRECT

**Step 1: Fix circular imports at module level**

```python
# clients/services/metadata_service.py
from typing import List

from titan_cli.core.result import ClientResult, ClientSuccess, ClientError
from titan_cli.core.logging import log_client_operation

from ..network import JiraNetwork
from ...models.network.rest import (
    NetworkJiraStatus,
    NetworkJiraStatusCategory,
    NetworkJiraVersion
)
from ...models.mappers import (  # ✅ Import at module level
    from_network_status,
    from_network_version
)
from ...exceptions import JiraAPIError
```

**Step 2: Define defaults in dataclass models**

```python
# models/network/rest/status.py
from dataclasses import dataclass
from typing import Optional

@dataclass
class NetworkJiraStatusCategory:
    """Network model for status category."""
    id: str = ""              # ✅ Default in model
    name: str = "To Do"       # ✅ Default in model
    key: str = "new"          # ✅ Default in model
    colorName: Optional[str] = None

# models/network/rest/version.py
@dataclass
class NetworkJiraVersion:
    """Network model for version."""
    id: str = ""              # ✅ Default in model
    name: str = ""            # ✅ Default in model
    description: Optional[str] = None
    released: bool = False    # ✅ Default in model
    releaseDate: Optional[str] = None
```

**Step 3: Use models without hardcoded defaults**

```python
# clients/services/metadata_service.py
def list_statuses(self, project_key: str) -> ClientResult[List[UIJiraStatus]]:
    """List statuses."""
    try:
        data = self.network.make_request("GET", f"project/{project_key}/statuses")

        network_statuses = []
        for status_data in data.get("statuses", []):
            status_category_data = status_data.get("statusCategory", {})

            # ✅ Model provides defaults
            status_category = NetworkJiraStatusCategory(
                id=status_category_data.get("id"),
                name=status_category_data.get("name"),
                key=status_category_data.get("key"),
                colorName=status_category_data.get("colorName")
            )

            network_statuses.append(NetworkJiraStatus(
                id=status_data.get("id", ""),
                name=status_data.get("name", ""),
                description=status_data.get("description"),
                statusCategory=status_category
            ))

        # ✅ Map at module level (imported at top)
        ui_statuses = [from_network_status(s) for s in network_statuses]

        return ClientSuccess(
            data=ui_statuses,
            message=f"Found {len(ui_statuses)} statuses"
        )

    except JiraAPIError as e:
        return ClientError(error_message=str(e), error_code="API_ERROR")

def list_project_versions(self, project_key: str) -> ClientResult[List[UIJiraVersion]]:
    """List versions."""
    try:
        project_data = self.network.make_request("GET", f"project/{project_key}")

        network_versions = []
        for v_data in project_data.get("versions", []):
            # ✅ Model provides defaults
            network_versions.append(NetworkJiraVersion(
                id=v_data.get("id"),
                name=v_data.get("name"),
                description=v_data.get("description"),
                released=v_data.get("released"),
                releaseDate=v_data.get("releaseDate")
            ))

        # ✅ Map at module level
        ui_versions = [from_network_version(v) for v in network_versions]

        return ClientSuccess(
            data=ui_versions,
            message=f"Found {len(ui_versions)} versions"
        )

    except JiraAPIError as e:
        return ClientError(error_message=str(e), error_code="API_ERROR")
```

### Alternative 1: Use Constants File

```python
# constants.py
"""Default values for Jira models."""

# Status defaults
DEFAULT_STATUS_CATEGORY_ID = ""
DEFAULT_STATUS_CATEGORY_NAME = "To Do"
DEFAULT_STATUS_CATEGORY_KEY = "new"

# Version defaults
DEFAULT_VERSION_ID = ""
DEFAULT_VERSION_NAME = ""
DEFAULT_VERSION_RELEASED = False

# clients/services/metadata_service.py
from ...constants import (
    DEFAULT_STATUS_CATEGORY_NAME,
    DEFAULT_STATUS_CATEGORY_KEY,
    DEFAULT_VERSION_RELEASED
)

# Use constants instead of hardcoded values
status_category = NetworkJiraStatusCategory(
    id=status_category_data.get("id", ""),
    name=status_category_data.get("name", DEFAULT_STATUS_CATEGORY_NAME),
    key=status_category_data.get("key", DEFAULT_STATUS_CATEGORY_KEY)
)
```

### Alternative 2: Use StrEnum for Typed Constants

**For fixed sets of values** (like priority names, status categories), use `StrEnum`:

```python
# constants.py
from enum import StrEnum

class PriorityName(StrEnum):
    """Jira priority names."""
    HIGHEST = "Highest"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    LOWEST = "Lowest"

class PriorityIcon(StrEnum):
    """Priority icons."""
    HIGHEST = "🔴"
    HIGH = "🟠"
    MEDIUM = "🟡"
    LOW = "🟢"
    LOWEST = "🔵"

class StatusCategoryKey(StrEnum):
    """Status category keys."""
    NEW = "new"
    IN_PROGRESS = "indeterminate"
    DONE = "done"

class StatusCategoryName(StrEnum):
    """Status category display names."""
    TO_DO = "To Do"
    IN_PROGRESS = "In Progress"
    DONE = "Done"

# ❌ BEFORE - hardcoded strings in list
DEFAULT_PRIORITIES = [
    UIPriority(id="1", name="Highest", icon="🔴", label="🔴 Highest"),
    UIPriority(id="2", name="High", icon="🟠", label="🟠 High"),
    UIPriority(id="3", name="Medium", icon="🟡", label="🟡 Medium"),
    UIPriority(id="4", name="Low", icon="🟢", label="🟢 Low"),
    UIPriority(id="5", name="Lowest", icon="🔵", label="🔵 Lowest"),
]

# ✅ AFTER - using StrEnum
DEFAULT_PRIORITIES = [
    UIPriority(
        id="1",
        name=PriorityName.HIGHEST,
        icon=PriorityIcon.HIGHEST,
        label=f"{PriorityIcon.HIGHEST} {PriorityName.HIGHEST}"
    ),
    UIPriority(
        id="2",
        name=PriorityName.HIGH,
        icon=PriorityIcon.HIGH,
        label=f"{PriorityIcon.HIGH} {PriorityName.HIGH}"
    ),
    UIPriority(
        id="3",
        name=PriorityName.MEDIUM,
        icon=PriorityIcon.MEDIUM,
        label=f"{PriorityIcon.MEDIUM} {PriorityName.MEDIUM}"
    ),
    UIPriority(
        id="4",
        name=PriorityName.LOW,
        icon=PriorityIcon.LOW,
        label=f"{PriorityIcon.LOW} {PriorityName.LOW}"
    ),
    UIPriority(
        id="5",
        name=PriorityName.LOWEST,
        icon=PriorityIcon.LOWEST,
        label=f"{PriorityIcon.LOWEST} {PriorityName.LOWEST}"
    ),
]

# clients/services/metadata_service.py
from ...constants import StatusCategoryName, StatusCategoryKey

status_category = NetworkJiraStatusCategory(
    id=status_category_data.get("id"),
    name=status_category_data.get("name", StatusCategoryName.TO_DO),  # ✅ Type-safe enum
    key=status_category_data.get("key", StatusCategoryKey.NEW),        # ✅ Type-safe enum
    colorName=status_category_data.get("colorName")
)
```

**Benefits of StrEnum:**
- ✅ Type-safe: IDE autocomplete and mypy validation
- ✅ Centralized: Single source of truth
- ✅ Refactorable: Rename in one place
- ✅ Discoverable: `PriorityName.` shows all options
- ✅ No typos: `PriorityName.HGIHEST` → error at type-check time

### Why This Matters

**Hardcoded Defaults:**
- Makes values hard to change (scattered across codebase)
- No single source of truth
- Difficult to test different scenarios
- Violates DRY principle

**TYPE_CHECKING:**
- **PROHIBITED** in this codebase
- Hides circular import problems instead of fixing them
- Makes imports inconsistent (some at top, some in functions)
- Breaks IDE autocomplete and type checking at runtime

**Circular Imports:**
- Resolve by restructuring imports, NOT hiding with TYPE_CHECKING
- Import at module level, not inside functions
- If circular import exists, it's an architecture smell

**Correct Resolution:**
1. Define defaults in dataclass models (preferred)
2. OR use a constants file
3. Import mappers at module level
4. NEVER use `TYPE_CHECKING` or function-level imports

---

## ❌ MISTAKE #12: Using Dict Constants Instead of StrEnum

**Problem**: Using dictionary constants for mappings that could be type-safe enums.

**Impact**: No type safety, no IDE autocomplete, scattered logic, harder to maintain.

### Where This Happens

**Icon/Label Mappings** - When mapping names to icons, labels, or display values:

```python
# ❌ WRONG: Dict constant
PRIORITY_ICONS = {
    "highest": "🔴",
    "high": "🟠",
    "medium": "🟡",
    "low": "🟢",
    "lowest": "⚪",
}

def map_priority(name: str) -> str:
    return PRIORITY_ICONS.get(name.lower(), "⚫")
```

**Status/Category Mappings** - When mapping status keys to icons:

```python
# ❌ WRONG: Dict constant
STATUS_CATEGORY_ICONS = {
    "to do": "🟡",
    "new": "🟡",
    "in progress": "🔵",
    "done": "🟢",
}
```

**Type Mappings** - When mapping type names to icons:

```python
# ❌ WRONG: Dict constant
ISSUE_TYPE_ICONS = {
    "bug": "🐛",
    "story": "📖",
    "task": "✅",
    "epic": "🎯",
}
```

### Why This Is Wrong

1. **No Type Safety**
   - String keys are error-prone (typos, case sensitivity)
   - No IDE autocomplete for valid values
   - No compile-time validation

2. **Scattered Logic**
   - Icon mapping in one file
   - Label formatting in another
   - Business logic spread across codebase

3. **Hard to Extend**
   - Adding new values requires updating multiple places
   - No central source of truth
   - Aliases/variations require duplicate entries

4. **No Runtime Validation**
   - Invalid values silently fall back to defaults
   - No way to validate before use

### ✅ CORRECT: Use StrEnum with Properties

**Create enum with properties:**

```python
from enum import StrEnum

class JiraPriority(StrEnum):
    """Standard Jira priority levels with type safety."""

    HIGHEST = "Highest"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    LOWEST = "Lowest"

    @property
    def icon(self) -> str:
        """Get icon for this priority."""
        icons = {
            JiraPriority.HIGHEST: "🔴",
            JiraPriority.HIGH: "🟠",
            JiraPriority.MEDIUM: "🟡",
            JiraPriority.LOW: "🟢",
            JiraPriority.LOWEST: "🔵",
        }
        return icons[self]

    @property
    def label(self) -> str:
        """Get formatted label with icon."""
        return f"{self.icon} {self.value}"

    @classmethod
    def get_icon(cls, priority_name: str) -> str:
        """
        Get icon for any priority name (handles aliases).

        Handles standard priorities + common aliases:
        - Blocker → 🚨
        - Critical → Highest icon
        - Major → High icon
        """
        priority_lower = priority_name.lower()

        # Handle aliases
        aliases = {
            "blocker": "🚨",
            "critical": cls.HIGHEST.icon,
            "major": cls.HIGH.icon,
            "minor": cls.LOW.icon,
            "trivial": cls.LOWEST.icon,
        }

        if priority_lower in aliases:
            return aliases[priority_lower]

        # Try exact match
        try:
            priority = cls(priority_name)
            return priority.icon
        except ValueError:
            return "⚫"  # Unknown priority
```

**Usage in mappers:**

```python
from ..enums import JiraPriority

def from_network_priority(network_priority: NetworkJiraPriority) -> UIPriority:
    """Map NetworkJiraPriority to UIPriority."""
    # ✅ CORRECT: Use enum class method
    icon = JiraPriority.get_icon(network_priority.name)
    label = f"{icon} {network_priority.name}"

    return UIPriority(
        id=network_priority.id,
        name=network_priority.name,
        icon=icon,
        label=label
    )
```

**Usage in code:**

```python
# ✅ Type-safe access
priority = JiraPriority.HIGH
print(priority.icon)        # "🟠"
print(priority.label)       # "🟠 High"
print(priority.value)       # "High"

# ✅ IDE autocomplete works
priority = JiraPriority.  # <-- IDE shows all options

# ✅ Handles unknown values gracefully
icon = JiraPriority.get_icon("Custom Priority")  # "⚫"

# ✅ Handles aliases
icon = JiraPriority.get_icon("Blocker")  # "🚨"
icon = JiraPriority.get_icon("Critical")  # "🔴"
```

### Pattern for All Enum Mappings

**1. Define enum with standard values:**

```python
class JiraStatusCategory(StrEnum):
    TO_DO = "new"
    IN_PROGRESS = "indeterminate"
    DONE = "done"
```

**2. Add icon property:**

```python
    @property
    def icon(self) -> str:
        icons = {
            JiraStatusCategory.TO_DO: "🟡",
            JiraStatusCategory.IN_PROGRESS: "🔵",
            JiraStatusCategory.DONE: "🟢",
        }
        return icons[self]
```

**3. Add class method for flexible lookup:**

```python
    @classmethod
    def get_icon(cls, category_key: str) -> str:
        """Handle both keys and name aliases."""
        category_lower = category_key.lower()

        # Name aliases
        name_to_key = {
            "to do": cls.TO_DO,
            "in progress": cls.IN_PROGRESS,
        }

        if category_lower in name_to_key:
            return name_to_key[category_lower].icon

        try:
            category = cls(category_lower)
            return category.icon
        except ValueError:
            return "⚫"
```

**4. Use in mappers:**

```python
def from_network_status(network_status: NetworkJiraStatus) -> UIJiraStatus:
    """Map NetworkJiraStatus to UIJiraStatus."""
    category_key = network_status.statusCategory.key if network_status.statusCategory else "new"

    # ✅ CORRECT: Use enum class method
    icon = JiraStatusCategory.get_icon(category_key)

    return UIJiraStatus(
        id=network_status.id,
        name=network_status.name,
        icon=icon,
        category=category_name
    )
```

### When to Use StrEnum vs Dict

**Use StrEnum when:**
- ✅ Values are known at design time
- ✅ Values are standard/predictable (priorities, types, statuses)
- ✅ You need type safety and IDE support
- ✅ Logic is associated with values (icons, labels, formatting)

**Use Dict when:**
- ✅ Values are dynamic/user-configurable
- ✅ Values come from external config/database
- ✅ Simple key-value lookup with no associated logic

### Real-World Example (From PR #166)

**Before (3 separate dicts):**

```python
# priority_mapper.py
PRIORITY_ICONS = {
    "highest": "🔴", "high": "🟠", "medium": "🟡",
    "low": "🟢", "lowest": "⚪",
    "blocker": "🚨", "critical": "🔴", ...
}

# issue_type_mapper.py
ISSUE_TYPE_ICONS = {
    "bug": "🐛", "story": "📖", "task": "✅", ...
}

# status_mapper.py
STATUS_CATEGORY_ICONS = {
    "to do": "🟡", "new": "🟡", ...
}
```

**After (centralized enums):**

```python
# models/enums.py
class JiraPriority(StrEnum):
    HIGHEST = "Highest"
    # ... with .icon, .label properties and .get_icon() method

class JiraIssueType(StrEnum):
    BUG = "Bug"
    # ... with .icon property and .get_icon() method

class JiraStatusCategory(StrEnum):
    TO_DO = "new"
    # ... with .icon property and .get_icon() method
```

**Benefits:**
- Single source of truth for all icon mappings
- Type-safe access with IDE autocomplete
- Centralized alias handling
- Easy to extend with new properties
- Self-documenting (enum members show all valid values)

---

## Summary Checklist

When generating code, verify:

- [ ] **Operations** return `T` or raise (NOT `ClientResult[T]`)
- [ ] **Client** returns `ClientResult[UIModel]` (NOT `ClientResult[NetworkModel]`)
- [ ] **Client** has no business logic (search, filter, validate)
- [ ] **Client** has no mapping logic (only delegates to Services)
- [ ] **Steps** use `match`/`case` for `ClientResult` (NO `try`/`except` or `isinstance`)
- [ ] **Docstrings** have no `>>>` examples (write real tests instead)
- [ ] **Steps** call API once per data need (include all data in response)
- [ ] **Steps** use `bold_text()` for headers (NOT `markdown()`)
- [ ] **Validation** checks all constraints (min, max, format, etc.)
- [ ] **None handling** uses explicit checks (NOT `dict.pop()` with None values)
- [ ] **NO hardcoded defaults** - use dataclass defaults or constants file
- [ ] **NO TYPE_CHECKING** - resolve circular imports correctly
- [ ] **Imports at module level** - never import inside functions
- [ ] **Use StrEnum for constants** - NOT dicts for icon/label mappings

---

**Last Updated**: 2026-03-27 (Added Mistake #12: Dict Constants vs StrEnum)
**Source**: Production code review patterns (PR #166)
**Status**: Active Reference

**Total Mistakes**: 12 critical anti-patterns
