---
name: titan-plugin-architecture
description: Understand the 5-layer architecture for Titan CLI official plugins. Learn layer responsibilities, data flow, Result wrapper pattern, and when to use full architecture vs simple pattern. Essential for building maintainable, testable plugins.
keywords:
  - architecture
  - 5-layer
  - plugin structure
  - client result
  - pattern matching
  - separation of concerns
  - network models
  - ui models
  - services
  - operations
---

# Titan Plugin Architecture

**Core principles and layer responsibilities for building official Titan CLI plugins**

## Overview

The 5-layer architecture provides clean separation of concerns for official Titan plugins (Git, GitHub, Jira). It enables:

- **Testability**: Each layer independently testable with mocks
- **Maintainability**: Clear responsibilities prevent coupling
- **Type Safety**: Strong typing with Result wrapper pattern
- **API Stability**: Network models isolate UI from API changes

## Architecture Layers

```
Steps → Operations → Client → Services → Network
  ↓         ↓          ↓         ↓          ↓
 UI    Business    Public   Data Access   HTTP/CLI
       Logic       API
```

### Layer Responsibilities

| Layer | Returns | Responsibility |
|-------|---------|----------------|
| **Steps** | `WorkflowResult` | UI orchestration, user interaction |
| **Operations** | `UIModel` or raises | Business logic, pure functions |
| **Client** | `ClientResult[UIModel]` | Public API facade |
| **Services** | `ClientResult[UIModel]` | Data access (Network → UI mapping) |
| **Network** | `dict`/`list`/`str` | HTTP/CLI communication |

## When to Use Each Layer

### Layer 1: Steps (UI/UX)

**Use for:**
- Displaying information to users
- Collecting user input
- Orchestrating workflow execution
- Managing step lifecycle

**Example:**
```python
def list_resources_step(ctx: WorkflowContext) -> WorkflowResult:
    """Display resources with UI orchestration."""
    ctx.textual.begin_step("List Resources")

    # Call client or operation
    result = ctx.client.list_resources()

    # Pattern matching is MANDATORY
    match result:
        case ClientSuccess(data=resources):
            for resource in resources:
                ctx.textual.text(f"{resource.status_icon} {resource.name}")
            ctx.textual.end_step("success")
            return Success(f"Found {len(resources)} resources")

        case ClientError(error_message=err):
            ctx.textual.error_text(f"Failed: {err}")
            ctx.textual.end_step("error")
            return Error(err)
```

**MUST:**
- Use `ctx.textual.begin_step()` and `ctx.textual.end_step()`
- Use pattern matching for `ClientResult` (NO try/except)
- Return `WorkflowResult` (Success/Error/Skip/Exit)

**MUST NOT:**
- Import Services or Network directly
- Implement business logic
- Access `.data` without pattern matching

### Layer 2: Operations (Business Logic)

**Use for:**
- Complex filtering, sorting, validation
- Multi-step business processes
- UI-agnostic logic that needs testing

**Example:**
```python
def fetch_active_resources(client: ResourceClient) -> List[UIResource]:
    """
    Fetch and filter active resources.

    Business logic:
    - Fetch all resources
    - Filter by status = "active"
    - Sort by name

    Returns:
        List of active UIResource objects

    Raises:
        OperationError: If fetch fails
    """
    result = client.list_resources()

    match result:
        case ClientSuccess(data=resources):
            active = [r for r in resources if r.status_display == "Active"]
            return sorted(active, key=lambda r: r.name)

        case ClientError(error_message=msg):
            raise OperationError(f"Failed to fetch resources: {msg}")
```

**MUST:**
- Be pure functions (no side effects)
- Work with UI models, NOT dicts
- Return `T` or raise exceptions (NOT `ClientResult[T]`)
- Use pattern matching for `ClientResult`

**MUST NOT:**
- Use `ctx.textual` or any UI
- Import Services or Network
- Return `ClientResult` (operations work at a higher level)

### Layer 3: Client (Public Facade)

**Use for:**
- Public API entry point for plugin
- Simple delegation to services

**Example:**
```python
class ResourceClient:
    """
    Resource Client Facade.

    Public API for resource plugin.
    """

    def __init__(self, base_url: str, api_token: str):
        # Internal (private) dependencies
        self._network = ResourceAPI(base_url, api_token)
        self._resource_service = ResourceService(self._network)

    # Public API - simple delegation
    def get_resource(self, resource_id: str) -> ClientResult[UIResource]:
        """Get resource by ID."""
        return self._resource_service.get_resource(resource_id)

    def list_resources(self) -> ClientResult[List[UIResource]]:
        """List all resources."""
        return self._resource_service.list_resources()
```

**MUST:**
- Return `ClientResult[UIModel]`
- Delegate to services (no business logic)
- Keep methods simple (one-liners)

**MUST NOT:**
- Implement business logic (search, filter, validate → Service/Operation)
- Do Network → UI mapping (that's Service's job)
- Call Operations (Operations call Client, not vice versa)

### Layer 4: Services (Data Access)

**Use for:**
- Converting Network models → UI models
- Wrapping results in `ClientResult`
- Error handling and recovery

**Example:**
```python
class ResourceService:
    """
    Resource Service (PRIVATE - only used by Client).

    Handles: Network call → Parse → Map → Wrap Result
    """

    def __init__(self, network: ResourceAPI):
        self.network = network

    def get_resource(self, resource_id: str) -> ClientResult[UIResource]:
        """
        Get resource by ID.

        Returns:
            ClientSuccess with UIResource or ClientError
        """
        try:
            # 1. Network call (returns raw dict)
            data = self.network.make_request("GET", f"resources/{resource_id}")

            # 2. Parse to Network model
            network_resource = NetworkResource(**data)

            # 3. Map to UI model
            ui_resource = from_network_resource(network_resource)

            # 4. Wrap in Result
            return ClientSuccess(
                data=ui_resource,
                message=f"Resource {resource_id} retrieved"
            )

        except ResourceAPIError as e:
            error_code = "NOT_FOUND" if e.status_code == 404 else "API_ERROR"
            return ClientError(
                error_message=str(e),
                error_code=error_code
            )
```

**MUST:**
- Return `ClientResult[UIModel]`
- Catch BASE exception class (e.g., `ResourceAPIError`, not subclasses)
- Follow pattern: Network call → Parse → Map → Wrap
- Be PRIVATE (only Client imports Services)

**MUST NOT:**
- Implement business logic (filtering, sorting → Operation)
- Be called by Operations or Steps directly
- Return Network models (always convert to UI models)

### Layer 5: Network (HTTP/CLI)

**Use for:**
- Pure HTTP/CLI communication
- Raw data extraction

**Example:**
```python
class ResourceAPIError(Exception):
    """Exception raised for Resource API errors."""
    def __init__(self, message: str, status_code: int = None):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class ResourceAPI:
    """
    Resource API client.

    Low-level HTTP communication. Returns raw JSON.
    """

    def __init__(self, base_url: str, api_token: str):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "Authorization": f"Bearer {api_token}",
        })

    def make_request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> Dict[str, Any] | List[Any]:
        """
        Make HTTP request to API.

        Returns:
            Raw JSON response (dict or list)

        Raises:
            ResourceAPIError: On HTTP error
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        try:
            response = self.session.request(method, url, timeout=30, **kwargs)
            response.raise_for_status()
            return response.json() if response.content else {}

        except requests.exceptions.RequestException as e:
            status_code = e.response.status_code if hasattr(e, 'response') else None
            raise ResourceAPIError(str(e), status_code=status_code)
```

**MUST:**
- Return raw data (dict/list/str)
- Raise exceptions on errors
- Handle timeouts and network failures

**MUST NOT:**
- Parse to models (return raw JSON)
- Implement business logic (filtering, sorting)
- Transform or rename fields

## Result Wrapper Pattern

All Client and Service methods use `ClientResult[T]` for type-safe error handling.

### Result Types

```python
from titan_cli.core.result import ClientSuccess, ClientError, ClientResult

# Success
ClientSuccess(data=T, message="Success message")

# Error
ClientError(error_message="Error description", error_code="ERROR_CODE")
```

### Pattern Matching (MANDATORY)

**Steps MUST use pattern matching:**

```python
# ✅ CORRECT
result = ctx.client.get_resource("123")
match result:
    case ClientSuccess(data=resource):
        ctx.textual.text(f"Found: {resource.name}")
        return Success("Done")
    case ClientError(error_message=err):
        ctx.textual.error_text(f"Failed: {err}")
        return Error(err)

# ❌ WRONG - Never access .data directly
if isinstance(result, ClientSuccess):
    resource = result.data  # DON'T DO THIS
```

**Operations also use pattern matching:**

```python
# ✅ CORRECT in Operations
result = client.list_resources()
match result:
    case ClientSuccess(data=resources):
        return [r for r in resources if r.status_display == "Active"]
    case ClientError(error_message=msg):
        raise OperationError(f"Failed: {msg}")
```

## Data Models

### Network Models (Faithful to API)

```python
"""models/network/resource.py"""
from dataclasses import dataclass

@dataclass
class NetworkResource:
    """
    Network model for Resource (faithful to API response).

    Matches the API structure exactly.
    """
    id: str
    name: str
    status: str
    created_at: str
    # ... exactly as API returns
```

### UI Models (Optimized for Display)

```python
"""models/view/view.py"""
from dataclasses import dataclass

@dataclass
class UIResource:
    """
    UI model for Resource (optimized for display).

    Pre-formatted fields for rendering.
    """
    id: str
    name: str
    status_icon: str      # ✅, ⏸️, ❌
    status_display: str   # "Active", "Paused", "Failed"
    created_display: str  # "2 hours ago"
```

### Mappers (Network → UI)

```python
"""models/mappers/resource_mapper.py"""
from ..network import NetworkResource
from ..view import UIResource
from ..formatting import format_timestamp, get_status_icon

def from_network_resource(network: NetworkResource) -> UIResource:
    """
    Convert NetworkResource to UIResource.

    Args:
        network: Network model from API

    Returns:
        UI model optimized for display
    """
    return UIResource(
        id=network.id,
        name=network.name,
        status_icon=get_status_icon(network.status),
        status_display=network.status.capitalize(),
        created_display=format_timestamp(network.created_at),
    )
```

## Layer Interaction Rules

### Import Rules

| Layer | Can Import | Cannot Import |
|-------|-----------|---------------|
| Steps | `operations/`, Client facade | Services, Network |
| Operations | Client facade only | Services, Network, Steps |
| Client | Services, Network | Operations, Steps |
| Services | Network, Models | Client, Operations, Steps |
| Network | Standard libs | Everything else |

### Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                        USER REQUEST                          │
└─────────────────────────────┬───────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  STEPS                                                       │
│  - ctx.textual.begin_step()                                 │
│  - result = ctx.client.method() OR operation(ctx.client)    │
│  - match result: (pattern matching MANDATORY)               │
│  - ctx.textual.end_step()                                   │
│  - return Success/Error/Skip/Exit                           │
└─────────────────────────────┬───────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  OPERATIONS (optional)                                       │
│  - Pure functions (no UI)                                   │
│  - Business logic                                           │
│  - Returns UIModel or raises                                │
└─────────────────────────────┬───────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  CLIENT (facade)                                            │
│  - Simple delegation to services                            │
│  - Returns ClientResult[UIModel]                            │
└─────────────────────────────┬───────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  SERVICES (private)                                         │
│  - Network call → Parse → Map → Wrap Result                │
│  - Returns ClientResult[UIModel]                            │
│  - Catches BASE exception class                             │
└─────────────────────────────┬───────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  NETWORK                                                    │
│  - Pure HTTP/CLI                                            │
│  - Returns dict/list/str                                    │
│  - Raises API exceptions                                    │
└─────────────────────────────┬───────────────────────────────┘
                              ↓
                         API / CLI
```

## When to Use 5-Layer vs Simple Pattern

### Use Full 5-Layer Architecture When:

✅ Building **official plugins** (Git, GitHub, Jira)
✅ Plugin will have **external API** integration
✅ Need **100% test coverage** with mocks
✅ Multiple developers will maintain code
✅ API responses need **transformation** for UI
✅ Complex **business logic** needs isolation

### Use Simple Pattern When:

✅ Creating **custom project steps** (`.titan/steps/`)
✅ **One-off automation** for specific project
✅ Simple logic (no external APIs)
✅ Quick prototyping

**Simple pattern example:**

```python
"""Custom project step - simple pattern allowed."""
from titan_cli.engine import WorkflowContext, WorkflowResult, Success

def my_custom_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Custom step for project-specific logic.

    Only requirement: WorkflowContext → WorkflowResult
    """
    ctx.textual.begin_step("My Custom Step")

    # Your logic here (can be inline for simple steps)
    value = ctx.get("param", "default")

    # Do something...

    ctx.textual.end_step("success")
    return Success("Done")
```

## Quick Reference Table

### What Each Layer Returns

| Layer | Return Type | Example |
|-------|-------------|---------|
| Network | `dict` / `list` / `str` | `{"id": "123", "name": "Resource"}` |
| Services | `ClientResult[UIModel]` | `ClientSuccess(data=UIResource(...))` |
| Client | `ClientResult[UIModel]` | `ClientSuccess(data=UIResource(...))` |
| Operations | `UIModel` or raises | `UIResource(...)` or `raise OperationError()` |
| Steps | `WorkflowResult` | `Success("Done")` or `Error("Failed")` |

### Layer Decision Tree

```
Need to build functionality?
│
├─ Official plugin (Git/GitHub/Jira)? → Use 5-layer architecture
│  └─ Where does it belong?
│     ├─ User interaction? → Step
│     ├─ Complex business logic? → Operation
│     ├─ Public API method? → Client
│     ├─ Data transformation? → Service
│     └─ HTTP/CLI call? → Network
│
└─ Custom project step? → Simple pattern (just WorkflowContext → WorkflowResult)
```

## Critical Rules

1. **Official plugins MUST follow 5-layer architecture**
2. **Custom steps CAN use any pattern** (only need `WorkflowContext → WorkflowResult`)
3. **Pattern matching MANDATORY** for all `ClientResult` in Steps and Operations
4. **Services catch BASE exception class**, not specific subclasses
5. **Operations return `T` or raise**, NOT `ClientResult[T]`
6. **Client returns `ClientResult[UIModel]`**, NOT Network models
7. **Network returns raw data**, no parsing or transformation
8. **Steps use `ctx.textual`** for ALL user interaction
9. **Services are PRIVATE**, only Client imports them
10. **Operations are UI-agnostic**, no `ctx.textual` allowed

## Complete Example

**Network Layer:**
```python
class ResourceAPI:
    def make_request(self, method: str, endpoint: str) -> dict:
        response = requests.request(method, f"{self.base_url}/{endpoint}")
        response.raise_for_status()
        return response.json()  # Raw dict
```

**Service Layer:**
```python
class ResourceService:
    def get_resource(self, id: str) -> ClientResult[UIResource]:
        try:
            data = self.network.make_request("GET", f"resources/{id}")
            network = NetworkResource(**data)
            ui = from_network_resource(network)
            return ClientSuccess(data=ui)
        except ResourceAPIError as e:
            return ClientError(error_message=str(e))
```

**Client Layer:**
```python
class ResourceClient:
    def get_resource(self, id: str) -> ClientResult[UIResource]:
        return self._resource_service.get_resource(id)
```

**Operation Layer (optional):**
```python
def fetch_active_resources(client: ResourceClient) -> List[UIResource]:
    result = client.list_resources()
    match result:
        case ClientSuccess(data=resources):
            return [r for r in resources if r.status_display == "Active"]
        case ClientError(error_message=msg):
            raise OperationError(msg)
```

**Step Layer:**
```python
def list_resources_step(ctx: WorkflowContext) -> WorkflowResult:
    ctx.textual.begin_step("List Resources")

    result = ctx.client.list_resources()

    match result:
        case ClientSuccess(data=resources):
            for r in resources:
                ctx.textual.text(f"{r.status_icon} {r.name}")
            ctx.textual.end_step("success")
            return Success(f"Found {len(resources)} resources")

        case ClientError(error_message=err):
            ctx.textual.error_text(err)
            ctx.textual.end_step("error")
            return Error(err)
```

## Benefits of This Architecture

### Testability
Each layer can be tested in isolation with simple mocks:
- Network: Mock HTTP responses
- Services: Mock Network layer
- Client: Mock Services
- Operations: Mock Client facade
- Steps: Mock Client/Operations

### Maintainability
Clear responsibilities prevent coupling:
- API changes only affect Network and Services
- Business logic changes only affect Operations
- UI changes only affect Steps

### Type Safety
Strong typing with Result wrapper pattern catches errors at compile time:
- Pattern matching forces handling both success and error cases
- UI models guarantee correct field types for display

### API Stability
Network models isolate UI from API changes:
- API adds field → Only update Network model and mapper
- API renames field → Only update mapper
- UI needs different format → Only update UI model

---

**Remember**: The 5-layer architecture is **MANDATORY for official plugins**, but custom project steps can use any pattern as long as they follow `WorkflowContext → WorkflowResult`.
