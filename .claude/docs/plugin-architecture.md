# Plugin Architecture Guide

**Complete guide for building Titan CLI plugins with modern layered architecture**

Last updated: 2026-02-13

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture Layers](#architecture-layers)
3. [Models Layer](#models-layer)
4. [Client Layer](#client-layer)
5. [Implementation Guide](#implementation-guide)
6. [Testing Strategy](#testing-strategy)
7. [Migration from Old Plugins](#migration-from-old-plugins)

---

## Overview

Since February 2026, Titan plugins follow a **5-layer architecture** that separates concerns cleanly:

```
┌─────────────────────────────────────────┐
│          5. Workflows (YAML)            │  Declarative flows
├─────────────────────────────────────────┤
│       4. Steps (UI Orchestration)       │  Display + user interaction
├─────────────────────────────────────────┤
│     3. Operations (Business Logic)      │  Pure functions, testable
├─────────────────────────────────────────┤
│       2. Client Layer (Services)        │  API calls + model conversion
├─────────────────────────────────────────┤
│         1. Models (Data Structures)     │  Network + View + Mappers
└─────────────────────────────────────────┘
```

**Key Principles:**

- **Separation of Concerns**: Each layer has one responsibility
- **Testability**: Pure functions enable 100% test coverage
- **Faithful Models**: Network models mirror APIs exactly
- **View Optimization**: UI models pre-calculate display fields
- **Reusability**: Operations and formatters shared across steps

---

## Architecture Layers

### Layer 1: Models

```
models/
├── network/          # Faithful to external API responses
│   ├── rest/        # REST API models (gh CLI, JIRA API, etc.)
│   └── graphql/     # GraphQL models
├── view/            # UI-optimized models
├── mappers/         # network → view conversion
└── formatting.py    # Shared utilities (date formatting, icons, etc.)
```

**Purpose**: Data representation at 3 levels (network/view/mappers)

### Layer 2: Client

```
clients/
├── network/              # Low-level API executors
│   ├── rest_network.py  # Subprocess, HTTP calls
│   ├── graphql_network.py
│   └── queries.py       # Centralized GraphQL queries
├── services/            # Business logic
│   ├── resource_service.py
│   └── ...
├── protocols.py         # Interfaces for testing
└── {name}_client.py     # Public facade
```

**Purpose**: API interaction + business logic + model conversion

### Layer 3: Operations

```
operations/
├── resource_operations.py
├── validation_operations.py
└── ...
```

**Purpose**: Pure business logic (UI-agnostic, 100% testable)

### Layer 4: Steps

```
steps/
├── create_resource_step.py
├── list_resources_step.py
└── ...
```

**Purpose**: UI orchestration (calls operations, displays results)

### Layer 5: Workflows

```
workflows/
├── create-resource.yaml
└── ...
```

**Purpose**: Declarative flow definitions

---

## Models Layer

### Network Models (Faithful to APIs)

**REST Example** (`models/network/rest/pull_request.py`):

```python
@dataclass
class RESTPullRequest:
    """
    Faithful to `gh pr view --json` output.
    Field names match API exactly (camelCase preserved).
    NO transformations or computed fields.
    """
    number: int
    title: str
    baseRefName: str  # Keep API naming
    headRefName: str
    isDraft: bool
    mergeable: str    # "MERGEABLE" | "CONFLICTING" | "UNKNOWN"

    @classmethod
    def from_json(cls, data: Dict) -> 'RESTPullRequest':
        """1:1 mapping from API response"""
        return cls(**data)
```

**GraphQL Example** (`models/network/graphql/review_thread.py`):

```python
@dataclass
class GraphQLPullRequestReviewThread:
    """
    Faithful to GraphQL PullRequestReviewThread schema.
    See: https://docs.github.com/en/graphql/reference/objects#pullrequestreviewthread
    """
    id: str
    isResolved: bool  # Keep GraphQL naming
    isOutdated: bool
    comments: List[GraphQLPullRequestReviewComment]

    @classmethod
    def from_graphql(cls, data: Dict) -> 'GraphQLPullRequestReviewThread':
        """Parse GraphQL response nodes"""
        ...
```

**Rules:**
- ✅ Field names match API exactly (preserve camelCase)
- ✅ No computed fields or transformations
- ✅ Docstring links to API documentation
- ❌ No presentation logic (emojis, formatting)

### View Models (UI-Optimized)

**Example** (`models/view/view.py`):

```python
@dataclass
class UIPullRequest:
    """
    UI model for displaying a PR.
    All fields pre-formatted and ready for widgets.
    """
    number: int
    title: str
    status_icon: str       # "🟢" "🔴" "🟣" "📝" (pre-calculated)
    author_name: str       # Just username
    branch_info: str       # "feat/xyz → develop" (pre-formatted)
    stats: str             # "+123 -45" (pre-formatted)
    is_mergeable: bool     # Boolean (not string)
    review_summary: str    # "✅ 2 approved" (pre-calculated)
    formatted_created_at: str  # "DD/MM/YYYY HH:MM:SS"
```

**Rules:**
- ✅ Pre-calculated display fields (icons, formatted strings)
- ✅ Simplified for UI needs (no nested objects)
- ✅ Boolean flags instead of string enums
- ❌ No API-specific naming (user-friendly names)

### Mappers (Conversion Logic)

**Example** (`models/mappers/pr_mapper.py`):

```python
from ..formatting import format_date, get_pr_status_icon, format_branch_info

def from_rest_pr(rest_pr: RESTPullRequest) -> UIPullRequest:
    """Convert REST PR to UI PR."""
    return UIPullRequest(
        number=rest_pr.number,
        title=rest_pr.title,
        status_icon=get_pr_status_icon(rest_pr.state, rest_pr.isDraft),
        branch_info=format_branch_info(rest_pr.headRefName, rest_pr.baseRefName),
        is_mergeable=(rest_pr.mergeable == "MERGEABLE"),
        # ... all transformations here
    )
```

### Formatting Utilities

**Example** (`models/formatting.py`):

```python
def format_date(iso_date: str) -> str:
    """Format ISO 8601 date to DD/MM/YYYY HH:MM:SS."""
    try:
        date_obj = datetime.fromisoformat(iso_date.replace('Z', '+00:00'))
        return date_obj.strftime("%d/%m/%Y %H:%M:%S")
    except:
        return iso_date

def get_pr_status_icon(state: str, is_draft: bool) -> str:
    """Get emoji icon for PR state."""
    if state == "MERGED": return "🟣"
    elif state == "CLOSED": return "🔴"
    elif is_draft: return "📝"
    return "🟢"
```

**Rules:**
- ✅ Shared across all mappers
- ✅ Pure functions (no side effects)
- ✅ Well-documented with examples
- ✅ Reusable (date formatting, icons, stats, etc.)

---

## Client Layer

### Network Layer (Low-Level)

**REST Network** (`clients/network/rest_network.py`):

```python
class RESTNetwork:
    """Low-level REST API executor."""

    def run_command(self, args: List[str]) -> str:
        """Execute command and return raw output."""
        result = subprocess.run(["gh"] + args, capture_output=True, text=True, check=True)
        return result.stdout.strip()
```

**GraphQL Network** (`clients/network/graphql_network.py`):

```python
class GraphQLNetwork:
    """Low-level GraphQL executor."""

    def run_query(self, query: str, variables: Dict) -> Dict:
        """Execute GraphQL query and return raw response."""
        args = ["api", "graphql", "-f", f"query={query}"]
        # Add variables...
        output = self.rest_network.run_command(args)
        return json.loads(output)
```

**Centralized Queries** (`clients/network/graphql_queries.py`):

```python
GET_PR_REVIEW_THREADS = '''
query($owner: String!, $repo: String!, $prNumber: Int!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $prNumber) {
      reviewThreads(first: 100) {
        nodes { ... }
      }
    }
  }
}
'''
```

### Services Layer (Business Logic)

**Example** (`clients/services/pr_service.py`):

```python
class PRService:
    """Business logic for PR operations."""

    def __init__(self, rest_network: RESTNetwork):
        self.rest = rest_network

    def get_pull_request(self, pr_number: int) -> UIPullRequest:
        """Get PR and return UI model."""
        # 1. Fetch from network
        output = self.rest.run_command(["pr", "view", str(pr_number), "--json", "..."])
        data = json.loads(output)

        # 2. Parse to network model
        rest_pr = RESTPullRequest.from_json(data)

        # 3. Map to view model
        ui_pr = from_rest_pr(rest_pr)

        return ui_pr
```

**Rules:**
- ✅ Uses network layer for API calls
- ✅ Parses to network models
- ✅ Maps to view models
- ✅ Returns UI-ready data
- ❌ No subprocess calls (use network layer)
- ❌ No UI logic (no widgets, no display)

### Client Facade (Public API)

**Example** (`clients/github_client.py`):

```python
class GitHubClient:
    """Public facade for GitHub operations."""

    def __init__(self, config, secrets, git_client, repo_owner, repo_name):
        # Initialize network layers
        self._rest_network = RESTNetwork(repo_owner, repo_name)
        self._graphql_network = GraphQLNetwork(self._rest_network)

        # Initialize services
        self._pr_service = PRService(self._rest_network)
        self._review_service = ReviewService(self._rest_network, self._graphql_network)

    # Delegate to services
    def get_pull_request(self, pr_number: int) -> UIPullRequest:
        return self._pr_service.get_pull_request(pr_number)

    def get_pr_review_threads(self, pr_number: int) -> List[UICommentThread]:
        return self._review_service.get_pr_review_threads(pr_number)
```

---

## Implementation Guide

### Step 1: Plan Your Models

**Identify data sources:**
- REST API endpoints?
- GraphQL API?
- CLI commands with JSON output?

**For each resource, create:**
1. Network model (REST or GraphQL)
2. View model (UI-optimized)
3. Mapper function

### Step 2: Create Network Models

```bash
# Example for JIRA plugin
models/network/rest/
├── issue.py         # JiraIssue from REST API
├── project.py       # JiraProject
└── user.py          # JiraUser
```

**Template:**

```python
@dataclass
class RESTResource:
    """Faithful to API response."""
    field1: str
    field2: int

    @classmethod
    def from_json(cls, data: Dict) -> 'RESTResource':
        return cls(field1=data["field1"], field2=data["field2"])
```

### Step 3: Create View Models

```python
@dataclass
class UIResource:
    """UI-optimized model."""
    id: int
    display_name: str
    status_icon: str
    formatted_date: str
```

### Step 4: Create Mappers

```python
def from_rest_resource(rest: RESTResource) -> UIResource:
    return UIResource(
        id=rest.field1,
        display_name=format_name(rest.field2),
        status_icon=get_icon(rest.field3),
        formatted_date=format_date(rest.created_at)
    )
```

### Step 5: Create Network Layer

```python
class ResourceNetwork:
    def fetch_resource(self, id: int) -> str:
        """Returns raw JSON string"""
        ...
```

### Step 6: Create Services

```python
class ResourceService:
    def get_resource(self, id: int) -> UIResource:
        # Fetch → Parse → Map
        json_str = self.network.fetch_resource(id)
        rest_obj = RESTResource.from_json(json.loads(json_str))
        return from_rest_resource(rest_obj)
```

### Step 7: Create Facade

```python
class MyPluginClient:
    def __init__(self, ...):
        self._network = ResourceNetwork()
        self._service = ResourceService(self._network)

    def get_resource(self, id: int) -> UIResource:
        return self._service.get_resource(id)
```

### Step 8: Update Steps

```python
def list_resources_step(ctx: WorkflowContext) -> WorkflowResult:
    # Steps use view models directly
    resources = ctx.my_plugin.list_resources()  # Returns List[UIResource]

    for resource in resources:
        ctx.textual.text(f"{resource.status_icon} {resource.display_name}")
```

---

## Testing Strategy

### Unit Tests for Mappers

```python
def test_from_rest_pr():
    # Arrange
    rest_pr = RESTPullRequest(
        number=123,
        title="Test",
        state="OPEN",
        isDraft=False,
        # ...
    )

    # Act
    ui_pr = from_rest_pr(rest_pr)

    # Assert
    assert ui_pr.number == 123
    assert ui_pr.status_icon == "🟢"  # OPEN + not draft
```

### Unit Tests for Services (with Mocks)

```python
def test_pr_service_get_pull_request(mocker):
    # Mock network layer
    mock_network = mocker.Mock(spec=RESTNetwork)
    mock_network.run_command.return_value = '{"number": 123, ...}'

    # Test service
    service = PRService(mock_network)
    pr = service.get_pull_request(123)

    assert pr.number == 123
    assert isinstance(pr, UIPullRequest)
```

---

## Migration from Old Plugins

### Before (Monolithic)

```python
# Old: Everything in one file
class GitHubClient:
    def get_pull_request(self, pr_number):
        # 1. API call
        result = subprocess.run(["gh", "pr", "view", ...])
        # 2. Parse JSON
        data = json.loads(result.stdout)
        # 3. Transform
        pr = PullRequest(...)  # Mixed network/view model
        # 4. Add UI fields
        pr.icon = "🟢" if pr.state == "OPEN" else "🔴"
        return pr
```

### After (Layered)

```python
# Network layer
class RESTNetwork:
    def run_command(self, args): ...

# Service layer
class PRService:
    def get_pull_request(self, pr_number):
        json_str = self.network.run_command([...])
        rest_pr = RESTPullRequest.from_json(json.loads(json_str))
        return from_rest_pr(rest_pr)

# Facade
class GitHubClient:
    def get_pull_request(self, pr_number):
        return self._pr_service.get_pull_request(pr_number)
```

---

## Real-World Examples

### GitHub Plugin (titan-plugin-github)

- **Network models**: REST (gh CLI) + GraphQL
- **19 model files**: 4 REST, 4 GraphQL, 2 view, 4 mappers, 1 formatting
- **12 client files**: 3 network, 4 services, 1 protocol, 1 facade
- **Result**: 1452 → 281 lines in facade (~80% reduction)

### JIRA Plugin (titan-plugin-jira)

- **Network models**: REST (JIRA API)
- **Pattern**: Same 5-layer architecture
- **Benefit**: Easy to test with mocked API responses

### Git Plugin (titan-plugin-git)

- **Simpler**: No API models (direct command execution)
- **Pattern**: Operations + steps only
- **Note**: Not all plugins need full 5 layers

---

## Summary Checklist

When creating a new plugin:

- [ ] Create `models/network/` with API-faithful models
- [ ] Create `models/view/` with UI-optimized models
- [ ] Create `models/mappers/` for conversion logic
- [ ] Create `models/formatting.py` for shared utilities
- [ ] Create `clients/network/` for low-level API calls
- [ ] Create `clients/services/` for business logic
- [ ] Create `clients/protocols.py` for testing
- [ ] Create `clients/{name}_client.py` facade
- [ ] Update steps to use view models
- [ ] Write unit tests for mappers
- [ ] Write unit tests for services (with mocks)
- [ ] Document in plugin README

---

**Questions?** See existing plugins:
- `titan-plugin-github` - Full example (REST + GraphQL)
- `titan-plugin-jira` - REST API example
- `titan-plugin-git` - Simplified example (no API models)
