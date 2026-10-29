# Plugin Architecture (5-Layer Pattern)

Read this when you add or change code in an official plugin: what each layer owns, how data flows, which layer to use. Naming, `ClientResult` and the do/don't rules: [plugin-conventions.md](plugin-conventions.md). Tests and the new-capability checklist: [plugin-testing.md](plugin-testing.md).

Official plugins: Jira, GitHub, Git. The Slack plugin is official (registered in the root `pyproject.toml`) but does not follow the full 5-layer layout; `docker` is shipped, `poeditor` and `firebase` exist under `plugins/` but are not registered.

> **Note**: This architecture is for **official plugins only**. Custom user steps can use any pattern they want - the only requirement is `WorkflowContext → WorkflowResult`.

---

## Overview

### The 5-Layer Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ 1. STEPS (UI/UX Layer)                                      │
│    Workflow execution + User interaction                    │
│    Receives: UI models or ClientResults                     │
│    Returns: WorkflowResult                                  │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. OPERATIONS (Business Logic - Optional)                   │
│    Pure functions for complex logic                         │
│    Receives: Client as parameter                            │
│    Returns: UI models (unpacks Results internally)          │
│    Raises: Exceptions on errors                             │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. CLIENT (Facade - Public API)                             │
│    Unified interface for the plugin                         │
│    Delegates to internal Services                           │
│    Returns: ClientResult[UIModel]                           │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. SERVICES (Data Access - Internal/Private)                │
│    Network → NetworkModel → UIModel → Result                │
│    PRIVATE - only Client uses them                          │
│    Returns: ClientResult[UIModel]                           │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. NETWORK (*Network classes)                               │
│    Pure HTTP/CLI communication                              │
│    Returns: Raw JSON (dict/list)                            │
│    NO parsing to models                                     │
└─────────────────────────────────────────────────────────────┘
```

### Key Principles

✅ **Separation of Concerns**: Each layer has ONE responsibility
✅ **Type Safety**: Network models ≠ UI models
✅ **Testability**: Pure functions, easy mocking
✅ **Consistency**: All plugins follow same pattern
✅ **Result Wrapper**: Errors as values, not exceptions (in Client)

---

## Architecture Layers

### Layer 1: Steps

**Location**: `steps/`
**Responsibility**: UI/UX and workflow execution
**Signature**: `(WorkflowContext) → WorkflowResult`

Public steps returned from `plugin.py -> get_steps()` are part of the plugin's public workflow API.
That means they must have canonical docstrings and must stay in sync with the plugin docs under `docs/plugins/`.

**Two patterns**:

#### Pattern A: Simple (Client direct)
```python
def get_issue_step(ctx: WorkflowContext) -> WorkflowResult:
    """Simple step - calls client, handles Result with pattern matching"""
    ctx.textual.begin_step("Get Issue")

    result = ctx.jira.get_issue(key)  # ← ClientResult[UIJiraIssue]

    match result:
        case ClientSuccess(data=issue, message=msg):
            ctx.textual.success_text(msg)
            ctx.textual.text(f"{issue.status_icon} {issue.summary}")
            ctx.textual.end_step("success")
            return Success(msg, metadata={"issue": issue})

        case ClientError(error_message=err):
            ctx.textual.error_text(err)
            ctx.textual.end_step("error")
            return Error(err)
```

#### Pattern B: Complex (Operation)
```python
def list_my_issues_step(ctx: WorkflowContext) -> WorkflowResult:
    """Complex step - uses operation, handles exceptions"""
    ctx.textual.begin_step("List My Issues")

    try:
        # Operation returns UI models directly
        issues = fetch_my_pending_issues(ctx.jira, ctx.user)

        for issue in issues:
            ctx.textual.text(f"{issue.status_icon} {issue.key}: {issue.summary}")

        ctx.textual.end_step("success")
        return Success(f"Found {len(issues)} issues")

    except OperationError as e:
        ctx.textual.error_text(str(e))
        ctx.textual.end_step("error")
        return Error(str(e))
```

### Public step documentation contract

If a step is exposed through `get_steps()`, treat it as a public API surface.

Required docstring headers:

- `Requires:`
- `Inputs (from ctx.data):`
- `Outputs (saved to ctx.data):`
- `Returns:`

Rules:

- `Returns:` is always required.
- Use these exact header names.
- If the step can return `Skip` or `Exit`, document that explicitly.
- When the public step surface changes, update `docs/plugins/`, `docs/plugins/_meta/`, and regenerate `docs/plugins/_generated/`.

For this repository, the machine-readable inventory is maintained through:

- `.titan/workflows/sync-plugin-docs.yaml`
- `.titan/workflows/validate-plugin-docs.yaml`

---

### Layer 2: Operations

**Location**: `operations/`
**Responsibility**: Pure business logic (filtering, combining, validation)
**Optional**: Only create when logic is complex

**Rules**:
- ✅ Pure functions (no side effects)
- ✅ Receives Client as parameter
- ✅ Returns UI models directly
- ✅ Raises exceptions on errors
- ❌ NO imports of Services (only Client)
- ❌ NO UI dependencies (ctx.textual)

**Example**:
```python
# operations/issue_operations.py
from typing import List
from ..clients.jira_client import JiraClient
from ..models import UIJiraIssue
from ..exceptions import OperationError


def fetch_my_pending_issues(
    jira_client: JiraClient,
    user_email: str
) -> List[UIJiraIssue]:
    """
    Fetch and filter pending issues for user.

    Business logic:
    - Filter by assignee
    - Exclude Done status
    - Sort by priority

    Raises:
        OperationError: If fetch fails
    """
    # Call client (returns Result)
    result = jira_client.search_issues(f'assignee="{user_email}"')

    # Unpack Result
    match result:
        case ClientSuccess(data=issues):
            # Apply business logic
            pending = [i for i in issues if i.status_category != "Done"]
            return sorted(pending, key=lambda x: x.priority_icon)

        case ClientError(error_message=msg):
            raise OperationError(f"Failed to fetch issues: {msg}")
```

---

### Layer 3: Client (Facade)

**Location**: `clients/{name}_client.py`
**Responsibility**: Public API - delegates to Services
**Returns**: Always `ClientResult[UIModel]`

**Rules**:
- ✅ Public API of the plugin
- ✅ Delegates ALL work to Services
- ✅ Services are PRIVATE (implementation detail)
- ❌ NO business logic
- ❌ NO HTTP calls
- ❌ NO parsing

**Example**:
```python
# clients/jira_client.py
from titan_cli.core.result import ClientResult
from .services import IssueService, ProjectService
from .network import JiraNetwork
from ..models import UIJiraIssue, UIJiraProject


class JiraClient:
    """
    Jira Client Facade.

    Public API for Jira plugin.
    """

    def __init__(self, base_url: str, email: str, api_token: str):
        # Internal (private) dependencies
        self._network = JiraNetwork(base_url, email, api_token)
        self._issue_service = IssueService(self._network)
        self._project_service = ProjectService(self._network)

    # Public API - delegates to services
    def get_issue(self, key: str) -> ClientResult[UIJiraIssue]:
        """Get issue by key."""
        return self._issue_service.get_issue(key)

    def search_issues(self, jql: str, max_results: int = 50) -> ClientResult[List[UIJiraIssue]]:
        """Search issues using JQL."""
        return self._issue_service.search_issues(jql, max_results)
```

---

### Layer 4: Services

**Location**: `clients/services/`
**Responsibility**: Data access (Network → NetworkModel → UIModel → Result)
**Visibility**: PRIVATE (only Client uses them)

**Process**:
1. Call Network layer (get JSON)
2. Parse to NetworkModel
3. Map to UIModel
4. Wrap in ClientResult

This also applies to create operations. For example, a GitHub `ReleaseService`
can call `gh release create`, then `gh release view --json ...`, parse the
response into `NetworkRelease`, map it to `UIRelease`, and return
`ClientSuccess(data=ui_release, ...)`.

**Example**:
```python
# clients/services/issue_service.py
from titan_cli.core.result import ClientResult, ClientSuccess, ClientError
from titan_cli.core.logging import log_client_operation
from ..network import JiraNetwork
from ...models import NetworkJiraIssue, UIJiraIssue, from_network_issue
from ...exceptions import JiraAPIError


class IssueService:
    """Issue service (internal)."""

    def __init__(self, network: JiraNetwork):
        self.network = network

    @log_client_operation()
    def get_issue(self, key: str) -> ClientResult[UIJiraIssue]:
        """Get issue by key."""
        try:
            # 1. Network call
            data = self.network.make_request("GET", f"issue/{key}")

            # 2. Parse to Network model
            network_issue = self._parse_network_issue(data)

            # 3. Map to UI model
            ui_issue = from_network_issue(network_issue)

            # 4. Wrap in Result
            return ClientSuccess(data=ui_issue, message=f"Issue {key} retrieved")

        except JiraAPIError as e:
            error_code = "NOT_FOUND" if e.status_code == 404 else "API_ERROR"
            return ClientError(error_message=str(e), error_code=error_code)
```

**Logging convention**: Decorate public service methods with `@log_client_operation()` (from `titan_cli/core/logging/decorators.py`). It automatically logs the start and the `ClientSuccess`/`ClientError` result of each operation. This is the de-facto convention across service modules (see e.g. `titan-plugin-jira`'s `issue_service.py`).

**⚠️ CRITICAL: Exception Handling in Services**

Services MUST catch the **BASE exception class**, not specific subclasses.

❌ **WRONG**:
```python
class WorktreeService:
    def push_from_worktree(...) -> ClientResult[None]:
        try:
            self.git.run_command(args)
            return ClientSuccess(...)
        except GitCommandError as e:  # ❌ Only catches GitCommandError
            return ClientError(...)
```

✅ **CORRECT**:
```python
class WorktreeService:
    def push_from_worktree(...) -> ClientResult[None]:
        try:
            self.git.run_command(args)
            return ClientSuccess(...)
        except GitError as e:  # ✅ Catches ALL git errors
            return ClientError(...)
```

**Why?**

Exception hierarchies have multiple sibling classes:
```
GitError (base)
├── GitCommandError (command execution failed)
├── GitClientError (git CLI not found)
├── GitNotRepositoryError (not a git repo)
└── GitMergeConflictError (merge conflict)
```

If a service only catches `GitCommandError`, then:
- `GitClientError` (git not installed) → uncaught → propagates to executor
- Result: Confusing error message: "Error executing step: Git CLI not found"
- Violates architecture: Services should return `ClientError`, not throw exceptions

**Rule**: Always catch the base exception class (`GitError`, `JiraAPIError`, `GitHubAPIError`) to ensure ALL error types are converted to `ClientResult`.

**Bug Fix Reference**: WorktreeService (2026-02-18) - changed `except GitCommandError` → `except GitError`

---

### Layer 5: Network

**Location**: `clients/network/`
**Responsibility**: Pure HTTP/CLI communication
**Returns**: Raw JSON (dict/list)

**Example**:
```python
# clients/network/jira_network.py
import requests
from ...exceptions import JiraAPIError


class JiraNetwork:
    """Jira REST API communication."""

    def __init__(self, base_url: str, email: str, api_token: str):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "Authorization": f"Bearer {api_token}"
        })

    def make_request(self, method: str, endpoint: str, **kwargs) -> dict | list:
        """
        Make HTTP request.

        Returns:
            Raw JSON response (dict or list)

        Raises:
            JiraAPIError: On HTTP error
        """
        url = f"{self.base_url}/rest/api/2/{endpoint.lstrip('/')}"

        try:
            response = self.session.request(method, url, timeout=30, **kwargs)
            response.raise_for_status()
            return response.json() if response.content else {}

        except requests.exceptions.HTTPError as e:
            raise JiraAPIError(str(e), status_code=e.response.status_code)
```

---

## Data Flow Examples

### Simple (Step → Client → Service)

```
┌──────────────────────┐
│  get_issue_step      │
│  ctx.jira.get_issue  │
└──────────┬───────────┘
           │
           ↓
┌──────────────────────┐
│  JiraClient          │
│  delegates to        │
└──────────┬───────────┘
           │
           ↓
┌──────────────────────┐
│  IssueService        │
│  1. Network call     │
│  2. Parse Network    │
│  3. Map to UI        │
│  4. Wrap Result      │
└──────────┬───────────┘
           │
           ↓
┌──────────────────────┐
│  JiraNetwork         │
│  HTTP → JSON         │
└──────────────────────┘
```

### Complex (Step → Operation → Client → Service)

```
┌────────────────────────┐
│  list_my_issues_step   │
│  calls Operation       │
└──────────┬─────────────┘
           │
           ↓
┌────────────────────────┐
│  fetch_my_issues()     │
│  (Operation)           │
│  1. Call Client        │
│  2. Unpack Result      │
│  3. Filter & sort      │
│  4. Return UI models   │
└──────────┬─────────────┘
           │
           ↓
┌────────────────────────┐
│  JiraClient            │
│  delegates to Service  │
└──────────┬─────────────┘
           │
           ↓
┌────────────────────────┐
│  IssueService          │
│  Network → UI → Result │
└────────────────────────┘
```

---

## When to Use What

| Scenario | Pattern | Reason |
|----------|---------|--------|
| Fetch single entity | Step → Client | Simple, no logic needed |
| Display list as-is | Step → Client | Just fetch and render |
| Filter/sort/combine | Step → Operation → Client | Complex logic needs testing |
| Multi-step workflow | Operation | Combines multiple calls |
| Reusable logic | Operation | DRY principle |

---

## Summary

| Layer | Returns | Responsibility |
|-------|---------|----------------|
| **Steps** | `WorkflowResult` | UI/UX |
| **Operations** | `UIModel` or raises | Business logic |
| **Client** | `ClientResult[UIModel]` | Public API |
| **Services** | `ClientResult[UIModel]` | Data access |
| **Network** | `dict`/`list` | HTTP/CLI |

**Golden Rule**: Everything flows toward UI models. Network models are internal, UI models are public.

---

**Questions?** Check implementation in:
- `titan-plugin-jira` - Reference implementation
- `titan-plugin-github` - Complex (GraphQL + REST)
- `titan-plugin-git` - Simple example
