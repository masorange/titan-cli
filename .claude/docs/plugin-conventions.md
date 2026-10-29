# Plugin Conventions

Read this when you name a model or mapper, return a `ClientResult`, or review plugin code against the rules. Layer responsibilities: [plugin-architecture.md](plugin-architecture.md). Tests and the new-capability checklist: [plugin-testing.md](plugin-testing.md).

---

## Nomenclature & Naming

### Network Executors: `*Network`

```python
JiraNetwork          # Jira REST API
GHNetwork            # GitHub REST API (gh CLI)
GraphQLNetwork       # GitHub GraphQL API
GitNetwork           # Git command executor
```

### Network Models: `Network*`

Network models are **faithful to API responses**.

**Jira (REST only)**:
```python
NetworkJiraIssue      # From REST API
NetworkJiraProject
NetworkJiraComment
```

**GitHub (GraphQL + REST - disambiguated by directory)**:
```python
# models/network/rest/
NetworkPullRequest              # From REST
NetworkUser
NetworkIssue

# models/network/graphql/
GraphQLPullRequestReviewThread  # From GraphQL
GraphQLIssueComment
GraphQLUser
```

**Rule**: REST models use the plain `Network*` prefix and live in `models/network/rest/`; GraphQL models use the `GraphQL*` prefix and live in `models/network/graphql/`. The directory (plus prefix for GraphQL) disambiguates the API source.

### View/UI Models: `UI*`

UI models are **optimized for display** (pre-formatted fields, no nested objects).

```python
UIJiraIssue
UIPullRequest
UIComment
```

### Mappers: `from_network_*` / `from_graphql_*`

```python
from_network_issue(NetworkJiraIssue) → UIJiraIssue
from_graphql_review_thread(GraphQLPullRequestReviewThread) → UICommentThread
```

---

## Result Wrapper Pattern

### Core Types

Located in `titan_cli/core/result.py`:

```python
from dataclasses import dataclass
from typing import TypeVar, Generic, Optional

T = TypeVar('T')

@dataclass
class ClientSuccess(Generic[T]):
    data: T
    message: str = ""

@dataclass
class ClientError:
    error_message: str
    error_code: Optional[str] = None
    log_level: str = "error"  # "warning" for expected/recoverable, "error" for unexpected
    details: Optional[dict] = None

ClientResult = ClientSuccess[T] | ClientError
```

### When to Use

**Client/Services → Return Result**:
```python
def get_issue(self, key: str) -> ClientResult[UIJiraIssue]:
    return ClientSuccess(data=...) | ClientError(...)
```

**Operations → Unpack Result, Return UI or Raise**:
```python
def fetch_issues(...) -> List[UIJiraIssue]:
    result = client.search_issues(...)
    match result:
        case ClientSuccess(data=issues):
            return filter_issues(issues)
        case ClientError(error_message=msg):
            raise OperationError(msg)
```

**Steps → Pattern Match Results**:
```python
result = ctx.jira.get_issue(key)
match result:
    case ClientSuccess(data=issue):
        # Handle success
    case ClientError(error_message=err):
        # Handle error
```

---

## Implementation Rules

### ✅ DO

1. Client methods **always** return `ClientResult[UIModel]`
2. Services are **private** (never exported)
3. Operations receive **Client** as parameter (not Services)
4. Network returns **raw JSON** (dict/list)
5. UI models have **all fields pre-formatted**
6. Use **pattern matching** for Results in Steps
7. **Raise exceptions** in Operations
8. Create Operation if logic > 10 lines or reused

### ❌ DON'T

1. Never return **Network models** in public API
2. Never import **Services** in Operations
3. Never put **business logic** in Services
4. Never put **UI logic** in Operations
5. Never return `None` - return Result or raise
6. Never mix REST/GraphQL models in the same directory (`models/network/rest/` vs `models/network/graphql/`)
7. Never return primitives if data is structured

---

## Advanced Patterns

### Pattern Matching in Steps (MANDATORY)

All steps MUST use pattern matching when handling `ClientResult`. Never call `.data` directly.

**❌ WRONG:**
```python
def my_step(ctx: WorkflowContext) -> WorkflowResult:
    result = ctx.jira.get_issue("PROJ-1")
    issue = result.data  # WRONG! Assumes success
    ctx.textual.text(issue.summary)
```

**✅ CORRECT:**
```python
def my_step(ctx: WorkflowContext) -> WorkflowResult:
    result = ctx.jira.get_issue("PROJ-1")
    
    match result:
        case ClientSuccess(data=issue):
            ctx.textual.text(issue.summary)
            return Success("Issue retrieved")
        case ClientError(error_message=err):
            ctx.textual.error_text(f"Failed: {err}")
            return Error(err)
```

**Why mandatory:**
- Type safety - compiler checks all cases
- Explicit error handling - no silent failures
- Consistent error messages
- Clear success/failure paths

### Operations Work with Models, Not Dicts

Operations MUST work with typed models for clarity and type safety.

**❌ BAD - Dict hell:**
```python
def process_issues(issues: List[Dict]) -> str:
    """Hard to understand, no type safety"""
    for issue in issues:
        key = issue.get("key")  # What type? Who knows!
        summary = issue.get("fields", {}).get("summary")  # Maybe?
```

**✅ GOOD - Type-safe:**
```python
def process_issues(issues: List[UIJiraIssue]) -> str:
    """Clear types, IDE autocomplete works"""
    for issue in issues:
        key = issue.key  # Type: str
        summary = issue.summary  # Type: str
```

**When to use dicts:**
- Single key-value config
- Temporary intermediate data (very short-lived)
- One-off transformations

**Rule of thumb:** If you access it more than once, make it a model.

### Docstrings - NO Examples

**DO NOT** use doctest examples in docstrings.

**❌ BAD:**
```python
def build_issues_data(issues: List[UIJiraIssue]) -> str:
    """
    Build formatted text.
    
    Examples:
        >>> from dataclasses import dataclass
        >>> @dataclass
        ... class MockIssue:
        ...     key: str
        ...     summary: str
        ...     # 20 more lines of mock setup...
        >>> build_issues_data([MockIssue(...)])
        'output'
    """
```

**✅ GOOD:**
```python
def build_issues_data(issues: List[UIJiraIssue]) -> str:
    """
    Build formatted text of issues for AI filtering.
    
    Args:
        issues: List of UIJiraIssue objects
    
    Returns:
        Formatted text with issue details for AI
    """
```

**Why:**
- Project doesn't run doctests (no value)
- Verbose mocks make docstrings unreadable
- Real tests belong in `/tests` directory
- Confusing for developers
