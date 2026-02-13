# Plugin Architecture (5-Layer Pattern)

**Version**: 2.0
**Last Updated**: 2026-02-13
**Status**: Official architecture for all Titan plugins

Complete architectural guide for official Titan CLI plugins (Jira, GitHub, Git).

> **Note**: This architecture is for **official plugins only**. Custom user steps can use any pattern they want - the only requirement is `WorkflowContext → WorkflowResult`.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture Layers](#architecture-layers)
3. [Nomenclature & Naming](#nomenclature--naming)
4. [Result Wrapper Pattern](#result-wrapper-pattern)
5. [Data Flow Examples](#data-flow-examples)
6. [When to Use What](#when-to-use-what)
7. [Implementation Rules](#implementation-rules)
8. [Testing Guidelines](#testing-guidelines)
9. [Migration Guide](#migration-guide)

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
│ 5. NETWORK (*API classes)                                   │
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
from .network import JiraAPI
from ..models import UIJiraIssue, UIJiraProject


class JiraClient:
    """
    Jira Client Facade.

    Public API for Jira plugin.
    """

    def __init__(self, base_url: str, email: str, api_token: str):
        # Internal (private) dependencies
        self._network = JiraAPI(base_url, email, api_token)
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

**Example**:
```python
# clients/services/issue_service.py
from titan_cli.core.result import ClientResult, ClientSuccess, ClientError
from ..network import JiraAPI
from ...models import NetworkJiraIssue, UIJiraIssue, from_network_issue
from ...exceptions import JiraAPIError


class IssueService:
    """Issue service (internal)."""

    def __init__(self, network: JiraAPI):
        self.network = network

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

---

### Layer 5: Network

**Location**: `clients/network/`
**Responsibility**: Pure HTTP/CLI communication
**Returns**: Raw JSON (dict/list)

**Example**:
```python
# clients/network/jira_api.py
import requests
from ...exceptions import JiraAPIError


class JiraAPI:
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

## Nomenclature & Naming

### HTTP Clients: `*API`

```python
JiraAPI              # Jira REST API
GitHubRESTAPI        # GitHub REST API
GitHubGraphQLAPI     # GitHub GraphQL API
```

### Network Models: `Network*`

Network models are **faithful to API responses**.

**Jira (REST only)**:
```python
NetworkJiraIssue      # From REST API
NetworkJiraProject
NetworkJiraComment
```

**GitHub (GraphQL + REST - need disambiguation)**:
```python
NetworkGraphQLPullRequest       # From GraphQL
NetworkGraphQLIssueComment
NetworkRESTUser                 # From REST
NetworkRESTPullRequest
```

**Rule**: `Network` prefix identifies network model. Add `GraphQL`/`REST` if needed for disambiguation.

### View/UI Models: `UI*`

UI models are **optimized for display** (pre-formatted fields, no nested objects).

```python
UIJiraIssue
UIPullRequest
UIComment
```

### Mappers: `from_network_*`

```python
from_network_issue(NetworkJiraIssue) → UIJiraIssue
from_network_graphql_pr(NetworkGraphQLPullRequest) → UIPullRequest
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
│  JiraAPI             │
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
6. Never mix REST/GraphQL without `Network` prefix
7. Never return primitives if data is structured

---

## Testing Guidelines

### Service Tests
```python
def test_issue_service_get_success(mock_network):
    mock_network.make_request.return_value = {"key": "PROJ-1", ...}
    service = IssueService(mock_network)

    result = service.get_issue("PROJ-1")

    assert isinstance(result, ClientSuccess)
    assert result.data.key == "PROJ-1"
```

### Operation Tests
```python
def test_fetch_my_issues_filters(mock_client):
    mock_client.search_issues.return_value = ClientSuccess(data=[...])

    issues = fetch_my_pending_issues(mock_client, "user@example.com")

    assert len(issues) == 2  # Filtered
    assert all(i.status != "Done" for i in issues)
```

### Step Tests
```python
def test_get_issue_step_success(mock_context):
    mock_context.jira.get_issue.return_value = ClientSuccess(data=...)

    result = get_issue_step(mock_context)

    assert isinstance(result, Success)
```

---

## Migration Guide

### Before (Monolithic)
```python
class JiraClient:
    def get_issue(self, key):
        # HTTP call
        response = requests.get(...)
        # Parse + transform + UI logic mixed
        return JiraTicket(...)  # Mixed model
```

### After (Layered)
```python
# Network
class JiraAPI:
    def make_request(...) -> dict: ...

# Service
class IssueService:
    def get_issue(...) -> ClientResult[UIJiraIssue]:
        data = self.network.make_request(...)
        network = parse_network(data)
        ui = from_network(network)
        return ClientSuccess(data=ui)

# Client
class JiraClient:
    def get_issue(...) -> ClientResult[UIJiraIssue]:
        return self._issue_service.get_issue(...)
```

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
